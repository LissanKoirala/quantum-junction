#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import re
import resource
import sys
import textwrap
import time
import traceback
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CHALLENGE_RE = re.compile(r"challenge-(\d+)_(\d+)\.qasm$")


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def package_versions() -> dict[str, str]:
    names = ["qiskit", "qiskit-aer", "qiskit-quimb", "quimb", "torch", "numpy", "scipy"]
    out = {}
    for name in names:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = "not-installed"
    return out


def challenge_paths(root: Path) -> list[Path]:
    return sorted((root / "challenges").glob("*/*.qasm"), key=lambda p: (p.parent.name, p.name))


def resolve_challenge(root: Path, challenge_id: int | None, qasm: Path | None) -> Path:
    if qasm is not None:
        path = qasm if qasm.is_absolute() else root / qasm
        return path.resolve()
    if challenge_id is None:
        raise ValueError("provide either --challenge-id or --qasm")
    matches = []
    for path in challenge_paths(root):
        match = CHALLENGE_RE.match(path.name)
        if match and int(match.group(2)) == challenge_id:
            matches.append(path)
    if len(matches) != 1:
        raise ValueError(f"expected one challenge for id {challenge_id}, found {matches}")
    return matches[0].resolve()


def rel_path(path: Path) -> str:
    path = path.resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def bit_index(bit: Any) -> int:
    if hasattr(bit, "_index"):
        return int(bit._index)
    if hasattr(bit, "index"):
        return int(bit.index)
    raise AttributeError(f"cannot recover circuit bit index for {bit!r}")


def bit_indices(bits: Any) -> list[int]:
    return [bit_index(bit) for bit in bits]


def install_compat_patches(unswap_mod: Any, circuit_mpo_mod: Any, utils_mod: Any, rewire_trials: int) -> list[str]:
    from qiskit import QuantumCircuit
    from qiskit.transpiler import CouplingMap
    from qiskit.transpiler.passes import ElidePermutations, SabreSwap
    from qiskit_quimb import quimb_circuit
    from quimb.tensor import Circuit, CircuitMPS

    def merge_gates_public(gates: Any, num_qubits: int | None = None) -> QuantumCircuit:
        gates = list(gates)
        if num_qubits is None:
            max_q = -1
            for inst in gates:
                if inst.qubits:
                    max_q = max(max_q, *bit_indices(inst.qubits))
            num_qubits = max_q + 1
        qc = QuantumCircuit(num_qubits, num_qubits)
        for inst in gates:
            qc.append(
                inst.operation,
                qargs=bit_indices(inst.qubits),
                cargs=bit_indices(inst.clbits),
            )
        return qc

    def merge_layers_public(layers: Any, barrier: bool = False) -> QuantumCircuit:
        layers = list(layers)
        if not layers:
            raise ValueError("merge_layers requires at least one layer")
        qc = layers[0].copy()
        for layer in layers[1:]:
            if barrier:
                qc.barrier()
            qc = qc.compose(layer)
        return qc

    def rewire_layers_bounded(layers: Any, perm: Any, seed: int | None = None) -> list[Any]:
        layers = list(layers)
        if not layers:
            return []
        nq = len(perm)
        qc = merge_layers_public(layers)
        qc = QuantumCircuit(nq, qc.num_clbits).compose(qc, qubits=np.argsort(perm))
        qc = ElidePermutations()(qc)
        ss = SabreSwap(
            coupling_map=CouplingMap.from_line(nq),
            heuristic="decay",
            trials=rewire_trials,
            seed=seed,
        )
        qc = ss(qc)
        return list(utils_mod.iter_layers(qc))

    def is_nonunitary_layer(layer: Any) -> bool:
        ops = layer.count_ops()
        return "measure" in ops or "barrier" in ops

    def final_perm_from_measure_layers(measure_layers: list[Any], nq: int) -> list[int]:
        for layer in reversed(measure_layers):
            if "measure" in layer.count_ops():
                return [bit_index(inst.qubits[0]) for inst in layer if inst.operation.name == "measure"]
        return list(range(nq))

    def mpo_to_mps_measure_safe(
        mpo_core: Any,
        layers_left: list[Any],
        layers_right: list[Any],
        max_bond: int = 4096,
        cutoff: float = 0.001,
        to_backend: Any = None,
    ) -> tuple[Any, list[int]]:
        q2c = lambda qc: quimb_circuit(qc.decompose("unitary"), Circuit, to_backend=to_backend)
        nq = len(mpo_core.sites)
        final_mps = quimb_circuit(
            QuantumCircuit(nq),
            quimb_circuit_class=CircuitMPS,
            to_backend=to_backend,
        ).psi

        left_unitary = [layer for layer in layers_left if not is_nonunitary_layer(layer)]
        if left_unitary:
            left_layers = list(utils_mod.iter_layers(merge_layers_public(left_unitary).inverse()))
            for layer in left_layers:
                layer_mpo = circuit_mpo_mod.mpo_from_circuit(q2c(layer))
                final_mps = layer_mpo.apply(
                    final_mps,
                    compress=True,
                    max_bond=max_bond,
                    cutoff=cutoff,
                )

        final_mps = mpo_core.apply(final_mps, compress=True, max_bond=max_bond, cutoff=cutoff)

        final_meas = []
        for layer in layers_right:
            if is_nonunitary_layer(layer):
                final_meas.append(layer)
                continue
            layer_mpo = circuit_mpo_mod.mpo_from_circuit(q2c(layer))
            final_mps = layer_mpo.apply(
                final_mps,
                compress=True,
                max_bond=max_bond,
                cutoff=cutoff,
            )

        return final_mps, final_perm_from_measure_layers(final_meas, nq)

    def extract_bitstring_canonical(tne: Any) -> tuple[str, list[float]]:
        p0s = []
        pred_bs = ""
        for site in range(len(tne.sites)):
            if tne[0].backend == "numpy":
                pi0 = np.array([[1.0, 0.0], [0.0, 0.0]])
            else:
                import torch

                dtype = getattr(tne[0].data, "dtype", torch.complex128)
                pi0 = torch.tensor(
                    np.array([[1.0, 0.0], [0.0, 0.0]]),
                    device=utils_mod.DEVICE,
                    dtype=dtype,
                )
            if hasattr(tne, "local_expectation_canonical"):
                p0 = tne.local_expectation_canonical(pi0, where=site, normalized=True).real.item()
            else:
                p0 = tne.local_expectation(
                    pi0,
                    where=[site],
                    max_bond=2,
                    optimize="auto",
                    normalized=True,
                ).real.item()
            p0s.append(float(p0))
            pred_bs += "1" if p0 < 0.5 else "0"
        return pred_bs, p0s

    utils_mod.merge_gates = merge_gates_public
    utils_mod.merge_layers = merge_layers_public
    utils_mod.extract_bitstring = extract_bitstring_canonical
    unswap_mod.merge_gates = merge_gates_public
    unswap_mod.merge_layers = merge_layers_public
    unswap_mod.rewire_layers = rewire_layers_bounded
    unswap_mod.mpo_to_mps = mpo_to_mps_measure_safe
    circuit_mpo_mod.merge_gates = merge_gates_public

    return [
        "No bundled peaked-circuit-simulation source files were edited.",
        "Runtime shim: Qiskit 2 public bit-index recovery for merge_gates/merge_layers.",
        f"Runtime shim: bounded SabreSwap rewire_layers with trials={rewire_trials}.",
        "Runtime shim: measure-safe mpo_to_mps that skips measure/barrier layers and records final permutation.",
        "Runtime shim: extract_bitstring uses canonical one-site expectations when available.",
    ]


def choose_backend(name: str, utils_mod: Any) -> tuple[Any, dict[str, Any]]:
    backend = {"requested": name, "selected": "numpy", "cuda_available": False}
    if name == "numpy":
        return None, backend
    try:
        import torch
    except Exception as exc:  # noqa: BLE001
        backend["torch_error"] = repr(exc)
        if name == "cuda":
            raise
        return None, backend
    backend["cuda_available"] = bool(torch.cuda.is_available())
    backend["torch_device_count"] = int(torch.cuda.device_count()) if backend["cuda_available"] else 0
    if backend["cuda_available"]:
        capability = torch.cuda.get_device_capability(0)
        arch = f"sm_{capability[0]}{capability[1]}"
        arch_list = list(torch.cuda.get_arch_list()) if hasattr(torch.cuda, "get_arch_list") else []
        backend["cuda_device_capability"] = f"{capability[0]}.{capability[1]}"
        backend["torch_cuda_arch"] = arch
        backend["torch_cuda_arch_list"] = arch_list
        backend["selected"] = "cuda"
        backend["cuda_device_name"] = torch.cuda.get_device_name(0)
        if arch_list and arch not in arch_list:
            backend["selected"] = "numpy"
            backend["fallback_reason"] = (
                f"device architecture {arch} is not in this PyTorch build's CUDA arch list"
            )
            if name == "cuda":
                raise RuntimeError(backend["fallback_reason"])
            return None, backend
        return utils_mod.to_backend_cuda, backend
    if name == "cuda":
        raise RuntimeError("requested CUDA backend but torch.cuda.is_available() is false")
    return None, backend


def save_result_figure(
    result: dict[str, Any],
    params: dict[str, Any],
    changes: list[str],
    image_path: Path,
) -> None:
    status = result.get("status", "unknown")
    p0s = result.get("p0s")
    width = 15
    height = 9.5

    fig = plt.figure(figsize=(width, height))
    gs = fig.add_gridspec(nrows=2, ncols=1, height_ratios=[3.0, 2.2])
    ax = fig.add_subplot(gs[0])
    text_ax = fig.add_subplot(gs[1])

    if status == "ok" and p0s:
        p1s = [1.0 - p for p in p0s]
        x = np.arange(len(p1s))
        colors = ["#287271" if p >= 0.5 else "#b14d34" for p in p1s]
        ax.bar(x, p1s, color=colors, width=0.85)
        ax.axhline(0.5, color="#222222", linewidth=1.0, linestyle="--")
        ax.set_ylim(-0.02, 1.02)
        ax.set_ylabel("P(qubit = 1) from MPS marginal")
        ax.set_xlabel("tensor/MPS site index")
        if len(p1s) <= 32:
            ax.set_xticks(x)
        else:
            step = max(1, len(p1s) // 24)
            ax.set_xticks(x[::step])
        ax.set_title(
            f"peaked-circuit-simulation pilot: challenge {result['challenge_label']} "
            f"({result['difficulty']}, {result['num_qubits']} qubits)"
        )
    else:
        ax.axis("off")
        err = result.get("error", "no probability data")
        ax.text(0.01, 0.96, f"Simulation status: {status}", va="top", ha="left", fontsize=14)
        ax.text(0.01, 0.84, textwrap.fill(str(err), width=120), va="top", ha="left", fontsize=10)

    lines = [
        f"QASM: {result.get('qasm')}",
        f"Simulation: bundled peaked-circuit-simulation MPO compression + unswapping, then MPO->MPS, then one-qubit marginals.",
        "Parameters: "
        + ", ".join(
            [
                f"backend={params['backend_requested']}->{result.get('backend', {}).get('selected')}",
                f"max_bond={params['max_bond']}",
                f"cutoff={params['cutoff']}",
                f"unswap_threshold={params['unswap_threshold']}",
                f"early_stopping_gates={params['early_stopping_gates']}",
                f"center_ratio={params['center_ratio']}",
                f"max_its={params['max_its']}",
                f"rewire_trials={params['rewire_trials']}",
                f"seed={params['seed']}",
                f"hows={params['hows']}",
            ]
        ),
    ]
    if status == "ok":
        lines.extend(
            [
                f"Candidate raw site order: {result.get('pred_bitstring_raw')}",
                f"Candidate after final permutation: {result.get('pred_bitstring_permuted')}",
                f"Candidate in Qiskit/counts display order: {result.get('pred_bitstring_qiskit_order')}",
                f"Confidence margins |P1-0.5|: min={result.get('p1_margin_min'):.6g}, mean={result.get('p1_margin_mean'):.6g}, max={result.get('p1_margin_max'):.6g}",
                f"MPO stats rows={result.get('stats_rows')}, leftover_layers_left={result.get('leftover_layers_left')}, leftover_layers_right={result.get('leftover_layers_right')}",
            ]
        )
    else:
        lines.append(f"Error type: {result.get('error_type')}")

    lines.append("Runtime changes/shims:")
    lines.extend([f"- {change}" for change in changes])
    if params.get("figure_note"):
        lines.append(f"Note: {params['figure_note']}")

    text_ax.axis("off")
    wrapped = []
    for line in lines:
        prefix = ""
        body = line
        if line.startswith("- "):
            prefix = "- "
            body = line[2:]
        wrapped.extend(textwrap.wrap(body, width=150, initial_indent=prefix, subsequent_indent="  "))
    text_ax.text(
        0.01,
        0.98,
        "\n".join(wrapped),
        va="top",
        ha="left",
        family="monospace",
        fontsize=8.4,
    )

    fig.tight_layout()
    fig.savefig(image_path, dpi=170)
    plt.close(fig)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(json_safe(data), indent=2, sort_keys=True) + "\n")


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out_dir = out_dir.resolve()
    dirs = {
        "json": out_dir / "json",
        "images": out_dir / "images",
        "stats": out_dir / "stats",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)

    qasm_path = resolve_challenge(root, args.challenge_id, args.qasm)
    match = CHALLENGE_RE.match(qasm_path.name)
    if not match:
        raise ValueError(f"unexpected challenge file name: {qasm_path.name}")
    num_from_name, challenge_id = int(match.group(1)), int(match.group(2))
    difficulty = qasm_path.parent.name
    label = f"{num_from_name}_{challenge_id}"
    base = f"challenge-{label}"
    json_path = dirs["json"] / f"{base}.peaked_mpo_mps.json"
    stats_path = dirs["stats"] / f"{base}.stats.jsonl"
    image_path = dirs["images"] / f"{base}.peaked_mpo_mps.png"

    params = {
        "backend_requested": args.backend,
        "max_bond": args.max_bond,
        "cutoff": args.cutoff,
        "unswap_threshold": args.unswap_threshold,
        "early_stopping_gates": args.early_stopping_gates,
        "center_ratio": args.center_ratio,
        "equal": args.equal,
        "max_its": args.max_its,
        "rewire_trials": args.rewire_trials,
        "seed": args.seed,
        "hows": list(args.hows),
        "figure_note": args.figure_note,
    }
    result: dict[str, Any] = {
        "method": "peaked_mpo_unswap_mps_marginals",
        "status": "started",
        "root": str(root),
        "qasm": rel_path(qasm_path),
        "difficulty": difficulty,
        "challenge_id": challenge_id,
        "challenge_label": label,
        "output_json": rel_path(json_path),
        "output_stats_jsonl": rel_path(stats_path),
        "output_image": rel_path(image_path),
        "parameters": params,
        "versions": package_versions(),
        "env": {
            key: os.environ.get(key)
            for key in [
                "SLURM_ARRAY_JOB_ID",
                "SLURM_ARRAY_TASK_ID",
                "SLURM_JOB_ID",
                "SLURM_JOB_PARTITION",
                "SLURM_CPUS_PER_TASK",
                "CUDA_VISIBLE_DEVICES",
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
            ]
        },
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_json(json_path, result)

    changes: list[str] = []
    t0 = time.perf_counter()
    try:
        sys.path.insert(0, str(root / "peaked-circuit-simulation"))
        from qiskit import QuantumCircuit
        import circuit_mpo as circuit_mpo_mod
        import unswap as unswap_mod
        import utils as utils_mod

        changes = install_compat_patches(
            unswap_mod,
            circuit_mpo_mod,
            utils_mod,
            rewire_trials=args.rewire_trials,
        )
        result["runtime_changes"] = changes
        to_backend, backend_info = choose_backend(args.backend, utils_mod)
        result["backend"] = backend_info

        qc = QuantumCircuit.from_qasm_file(str(qasm_path))
        result["num_qubits"] = qc.num_qubits
        result["num_clbits"] = qc.num_clbits
        result["circuit_len"] = len(qc)
        result["circuit_ops"] = dict(qc.count_ops())
        if "measure" in result["circuit_ops"]:
            qc = qc.remove_final_measurements(inplace=False)
            result["removed_final_measurements"] = True
            result["unitary_circuit_len"] = len(qc)
            result["unitary_circuit_ops"] = dict(qc.count_ops())
        else:
            result["removed_final_measurements"] = False

        comp_start = time.perf_counter()
        mpo_core, layers_left, layers_right, stats = unswap_mod.mpo_compress_unswap(
            qc,
            max_bond=args.max_bond,
            cutoff=args.cutoff,
            unswap_threshold=args.unswap_threshold,
            early_stopping_gates=args.early_stopping_gates,
            center_ratio=args.center_ratio,
            equal=args.equal,
            flip_freq=None,
            max_its=args.max_its,
            to_backend=to_backend,
            seed=args.seed,
            hows=tuple(args.hows),
        )
        result["compression_seconds"] = time.perf_counter() - comp_start
        result["stats_rows"] = len(stats)
        result["leftover_layers_left"] = len(layers_left)
        result["leftover_layers_right"] = len(layers_right)
        result["mpo_core_info"] = utils_mod.get_tn_info(mpo_core)

        with stats_path.open("w") as f:
            for row in stats:
                f.write(json.dumps(json_safe(row), sort_keys=True) + "\n")

        mps_start = time.perf_counter()
        mps, final_perm = unswap_mod.mpo_to_mps(
            mpo_core,
            layers_left,
            layers_right,
            max_bond=args.max_bond,
            cutoff=args.cutoff,
            to_backend=to_backend,
        )
        pred_raw, p0s = utils_mod.extract_bitstring(mps)
        pred_permuted = "".join(pred_raw[i] for i in final_perm) if len(final_perm) == len(pred_raw) else None
        pred_qiskit = pred_permuted[::-1] if pred_permuted is not None else None
        p1_margins = [abs((1.0 - p0) - 0.5) for p0 in p0s]

        result.update(
            {
                "status": "ok",
                "mps_seconds": time.perf_counter() - mps_start,
                "final_perm": final_perm,
                "pred_bitstring_raw": pred_raw,
                "pred_bitstring_permuted": pred_permuted,
                "pred_bitstring_qiskit_order": pred_qiskit,
                "p0s": p0s,
                "p1s": [1.0 - p0 for p0 in p0s],
                "p1_margin_min": min(p1_margins) if p1_margins else None,
                "p1_margin_mean": float(np.mean(p1_margins)) if p1_margins else None,
                "p1_margin_max": max(p1_margins) if p1_margins else None,
                "mps_info": utils_mod.get_tn_info(mps),
            }
        )
    except Exception as exc:  # noqa: BLE001
        result.update(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
    finally:
        result["total_seconds"] = time.perf_counter() - t0
        result["max_rss_mb"] = rss_mb()
        result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        if not changes:
            changes = result.get("runtime_changes") or ["Runner did not reach compatibility shim installation."]
        save_result_figure(result, params, changes, image_path)
        write_json(json_path, result)
        print(json.dumps(json_safe(result), sort_keys=True), flush=True)

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--challenge-id", type=int, default=None)
    parser.add_argument("--qasm", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs" / "peaked_circuit_sim_pilot")
    parser.add_argument("--backend", choices=["auto", "cuda", "numpy"], default="auto")
    parser.add_argument("--max-bond", type=int, default=512)
    parser.add_argument("--cutoff", type=float, default=0.002)
    parser.add_argument("--unswap-threshold", type=float, default=1_000_000)
    parser.add_argument("--early-stopping-gates", type=int, default=-1)
    parser.add_argument("--center-ratio", type=float, default=0.5)
    parser.add_argument("--equal", action="store_true")
    parser.add_argument("--max-its", type=int, default=10)
    parser.add_argument("--rewire-trials", type=int, default=64)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--hows", nargs="+", default=["both", "left", "right"])
    parser.add_argument("--figure-note", default="")
    args = parser.parse_args()

    result = run(args)
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
