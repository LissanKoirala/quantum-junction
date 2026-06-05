#!/usr/bin/env python3
"""Smoke-test the bundled MPO unswapping code without editing shared sources."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import sys
import time
import traceback
from typing import Any, Callable


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


class Recorder:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []

    def step(self, name: str, fn: Callable[[], Any], fatal: bool = False) -> Any:
        t0 = time.perf_counter()
        try:
            result = fn()
        except BaseException as exc:  # noqa: BLE001 - diagnostic harness
            row = {
                "name": name,
                "status": "error",
                "seconds": time.perf_counter() - t0,
                "rss_mb": rss_mb(),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
            self.steps.append(row)
            print(f"[ERROR] {name}: {type(exc).__name__}: {exc}", flush=True)
            if fatal:
                raise
            return None
        else:
            row = {
                "name": name,
                "status": "ok",
                "seconds": time.perf_counter() - t0,
                "rss_mb": rss_mb(),
                "result": json_safe(result),
            }
            self.steps.append(row)
            print(f"[OK] {name}: {json_safe(result)}", flush=True)
            return result


def package_versions() -> dict[str, str]:
    names = ["qiskit", "quimb", "qiskit-quimb", "torch", "numpy", "scipy"]
    out = {}
    for name in names:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = "not-installed"
    return out


def load_qasm(path: Path):
    from qiskit import QuantumCircuit

    return QuantumCircuit.from_qasm_file(str(path))


def compact_counts(qc) -> dict[str, Any]:
    return {
        "num_qubits": qc.num_qubits,
        "num_clbits": qc.num_clbits,
        "len": len(qc),
        "ops": dict(qc.count_ops()),
    }


def install_compat_patches(unswap_mod, circuit_mpo_mod, utils_mod, rewire_trials: int) -> None:
    import numpy as np
    from qiskit import QuantumCircuit
    from qiskit_quimb import quimb_circuit
    from qiskit.transpiler import CouplingMap
    from qiskit.transpiler.passes import ElidePermutations, SabreSwap
    from quimb.tensor import Circuit, CircuitMPS

    def bit_index(bit):
        # Qiskit 2 CircuitInstruction objects do not expose their parent
        # circuit. For this smoke shim, fall back to the bit's stored index
        # when the original helper signature does not provide a circuit.
        if hasattr(bit, "_index"):
            return bit._index
        if hasattr(bit, "index"):
            return bit.index
        raise AttributeError(f"Cannot recover index for bit {bit!r}")

    def bit_indices(bits):
        return [bit_index(bit) for bit in bits]

    def merge_gates_public(gates, num_qubits=None):
        gates = list(gates)
        if num_qubits is None:
            max_q = -1
            for inst in gates:
                if inst.qubits:
                    max_q = max(max_q, *bit_indices(inst.qubits))
            num_qubits = max_q + 1
        qc = QuantumCircuit(num_qubits, num_qubits)
        for inst in gates:
            qargs = bit_indices(inst.qubits)
            cargs = bit_indices(inst.clbits)
            qc.append(inst.operation, qargs=qargs, cargs=cargs)
        return qc

    def merge_layers_public(layers, barrier=False):
        layers = list(layers)
        if not layers:
            raise ValueError("merge_layers requires at least one layer")
        qc = layers[0].copy()
        for layer in layers[1:]:
            if barrier:
                qc.barrier()
            qc = qc.compose(layer)
        return qc

    def rewire_layers_smoke(layers, perm, seed=None):
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

    def is_nonunitary_layer(layer):
        ops = layer.count_ops()
        return "measure" in ops or "barrier" in ops

    def final_perm_from_measure_layers(measure_layers, nq):
        for layer in reversed(measure_layers):
            ops = layer.count_ops()
            if "measure" in ops:
                return [bit_index(inst.qubits[0]) for inst in layer if inst.operation.name == "measure"]
        return list(range(nq))

    def mpo_to_mps_measure_safe(mpo_core, layers_left, layers_right, max_bond=4096, cutoff=0.001, to_backend=None):
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

    def extract_bitstring_canonical(tne):
        p0s = []
        pred_bs = ""
        for ii in range(len(tne.sites)):
            if tne[0].backend == "numpy":
                Pi0 = np.array([[1.0, 0.0], [0.0, 0.0]])
            else:
                import torch

                Pi0 = torch.tensor(
                    np.array([[1.0, 0.0], [0.0, 0.0]]),
                    device=utils_mod.DEVICE,
                    dtype=torch.cfloat,
                )
            if hasattr(tne, "local_expectation_canonical"):
                p0 = tne.local_expectation_canonical(Pi0, where=ii, normalized=True).real.item()
            else:
                p0 = tne.local_expectation(
                    Pi0,
                    where=[ii],
                    max_bond=2,
                    optimize="auto",
                    normalized=True,
                ).real.item()
            p0s.append(p0)
            pred_bs += "1" if p0 < 0.5 else "0"
        return pred_bs, p0s

    utils_mod.merge_gates = merge_gates_public
    utils_mod.merge_layers = merge_layers_public
    utils_mod.extract_bitstring = extract_bitstring_canonical
    unswap_mod.merge_gates = merge_gates_public
    unswap_mod.merge_layers = merge_layers_public
    unswap_mod.rewire_layers = rewire_layers_smoke
    unswap_mod.mpo_to_mps = mpo_to_mps_measure_safe
    circuit_mpo_mod.merge_gates = merge_gates_public


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--qasm", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", choices=["raw", "compat"], default="raw")
    parser.add_argument("--max-bond", type=int, default=32)
    parser.add_argument("--cutoff", type=float, default=1e-8)
    parser.add_argument("--rewire-trials", type=int, default=8)
    parser.add_argument("--unswap-threshold", type=float, default=1_000_000_000)
    parser.add_argument("--early-stopping-gates", type=int, default=0)
    parser.add_argument("--run-compress", action="store_true")
    parser.add_argument("--run-mps", action="store_true")
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    root = args.root.resolve()
    src = root / "peaked-circuit-simulation"
    sys.path.insert(0, str(src))

    rec = Recorder()
    report: dict[str, Any] = {
        "mode": args.mode,
        "root": str(root),
        "qasm": str(args.qasm),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "env": {
            key: os.environ.get(key)
            for key in [
                "SLURM_JOB_ID",
                "SLURM_JOB_PARTITION",
                "SLURM_CPUS_PER_TASK",
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
            ]
        },
    }

    report["versions"] = rec.step("package_versions", package_versions)

    imported = rec.step(
        "import_bundled_modules",
        lambda: __import__("unswap") and __import__("circuit_mpo") and __import__("utils"),
        fatal=True,
    )
    import unswap as unswap_mod
    import circuit_mpo as circuit_mpo_mod
    import utils as utils_mod

    if args.mode == "compat":
        rec.step(
            "install_compat_patches",
            lambda: install_compat_patches(
                unswap_mod, circuit_mpo_mod, utils_mod, args.rewire_trials
            )
            or {"rewire_trials": args.rewire_trials},
            fatal=True,
        )

    qc = rec.step("load_qasm", lambda: load_qasm(args.qasm), fatal=True)
    report["circuit"] = rec.step("circuit_counts", lambda: compact_counts(qc), fatal=True)
    rec.step(
        "qiskit_private_bit_attrs",
        lambda: {
            "qubit_has_index": hasattr(qc.data[0].qubits[0], "_index"),
            "qubit_has_register": hasattr(qc.data[0].qubits[0], "_register"),
        },
    )

    layers = rec.step("iter_layers", lambda: list(utils_mod.iter_layers(qc)), fatal=True)
    rec.step(
        "merge_first_three_gates",
        lambda: compact_counts(utils_mod.merge_gates(qc[: min(3, len(qc))], qc.num_qubits)),
    )
    rec.step(
        "rewire_first_six_layers",
        lambda: {
            "layers": len(
                unswap_mod.rewire_layers(
                    layers[: min(6, len(layers))],
                    list(range(qc.num_qubits)),
                    seed=123,
                )
            )
        },
    )

    from qiskit import QuantumCircuit
    from qiskit_quimb import quimb_circuit
    from quimb.tensor import Circuit

    rec.step(
        "qiskit_quimb_empty_to_mpo",
        lambda: circuit_mpo_mod.mpo_from_circuit(
            quimb_circuit(QuantumCircuit(qc.num_qubits), Circuit)
        )
        and {"num_qubits": qc.num_qubits},
    )

    def build_core_from_prefix(prefix_layers=8):
        core = circuit_mpo_mod.mpo_from_circuit(
            quimb_circuit(QuantumCircuit(qc.num_qubits), Circuit)
        )
        used = 0
        for layer in layers[: min(prefix_layers, len(layers))]:
            qcirc = quimb_circuit(layer, Circuit)
            core = circuit_mpo_mod.apply_circuit(
                core,
                qcirc,
                side="left",
                max_bond=args.max_bond,
                cutoff=args.cutoff,
            )
            used += len(layer)
        return core, used

    core_info = rec.step(
        "apply_prefix_layers_to_mpo",
        lambda: (lambda core_used: {
            "used_layer_ops": core_used[1],
            **utils_mod.get_tn_info(core_used[0]),
        })(build_core_from_prefix()),
    )

    def unswap_prefix_once():
        core, used = build_core_from_prefix()
        core2, perms, stats = unswap_mod.unswap(
            core,
            hows=("both", "left", "right"),
            max_bond=args.max_bond,
            cutoff=args.cutoff,
            max_its=2,
            equal=False,
        )
        return {
            "used_layer_ops": used,
            "perm_left_head": perms[0][: min(8, len(perms[0]))],
            "perm_right_head": perms[1][: min(8, len(perms[1]))],
            "stats_rows": len(stats),
            **utils_mod.get_tn_info(core2),
        }

    rec.step("unswap_prefix_mpo", unswap_prefix_once)

    compressed: dict[str, Any] = {}
    if args.run_compress:
        def compress_small():
            core, left, right, stats = unswap_mod.mpo_compress_unswap(
                qc,
                max_bond=args.max_bond,
                cutoff=args.cutoff,
                unswap_threshold=args.unswap_threshold,
                early_stopping_gates=args.early_stopping_gates,
                center_ratio=0.5,
                equal=False,
                max_its=2,
                seed=123,
                hows=("both", "left", "right"),
            )
            compressed.update({"core": core, "left": left, "right": right})
            return {
                "leftover_left_layers": len(left),
                "leftover_right_layers": len(right),
                "stats_rows": len(stats),
                **utils_mod.get_tn_info(core),
            }

        rec.step("mpo_compress_unswap_high_threshold", compress_small)

    if args.run_mps:
        def mps_small():
            if not compressed:
                raise RuntimeError("--run-mps requires successful --run-compress")
            mps, final_perm = unswap_mod.mpo_to_mps(
                compressed["core"],
                compressed["left"],
                compressed["right"],
                max_bond=args.max_bond,
                cutoff=args.cutoff,
            )
            pred, p0s = utils_mod.extract_bitstring(mps)
            return {
                "final_perm": final_perm,
                "pred_bitstring": pred,
                "p0_min": min(p0s),
                "p0_max": max(p0s),
                **utils_mod.get_tn_info(mps),
            }

        rec.step("mpo_to_mps_extract_bitstring", mps_small)

    report["steps"] = rec.steps
    report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    report["max_rss_mb"] = rss_mb()
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    errors = [s for s in rec.steps if s["status"] != "ok"]
    print(f"Wrote {args.out}", flush=True)
    print(f"Errors: {len(errors)}", flush=True)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
