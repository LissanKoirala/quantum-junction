#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pickle
import resource
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PEAKED_SIM = ROOT / "peaked-circuit-simulation"
if str(PEAKED_SIM) not in sys.path:
    sys.path.insert(0, str(PEAKED_SIM))


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def json_safe(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [json_safe(v) for v in x]
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    return repr(x)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for row in rows:
            f.write(json.dumps(json_safe(row), sort_keys=True) + "\n")


def count_quantum_ops(circuit: Any) -> int:
    ignored = {"barrier", "measure", "delay"}
    return sum(int(v) for k, v in circuit.count_ops().items() if k not in ignored)


def bit_index(bit: Any) -> int:
    if hasattr(bit, "_index"):
        return int(bit._index)
    if hasattr(bit, "index"):
        return int(bit.index)
    raise AttributeError(f"cannot recover index for {bit!r}")


def is_nonunitary_layer(layer: Any) -> bool:
    ops = layer.count_ops()
    return "measure" in ops or "barrier" in ops


def tn_info(tn: Any) -> dict[str, Any]:
    shapes = [tuple(int(v) for v in t.shape) for t in tn]
    elem_counts = [int(np.prod(s)) for s in shapes]
    return {
        "max_bond": int(tn.max_bond()) if hasattr(tn, "max_bond") else None,
        "num_tensors": int(getattr(tn, "num_tensors", len(shapes))),
        "total_elems": int(sum(elem_counts)),
        "max_tensor_elems": int(max(elem_counts)) if elem_counts else 0,
        "max_links": int(max((len(s) for s in shapes), default=0)),
    }


def bit_variants(raw_bits: str | None, perm: list[int]) -> dict[str, str]:
    if not raw_bits:
        return {}
    out = {
        "raw_site_order": raw_bits,
        "raw_site_order_reversed": raw_bits[::-1],
    }
    if perm and len(perm) == len(raw_bits):
        permuted = "".join(raw_bits[i] for i in perm)
        out["permuted_measurement_order"] = permuted
        out["permuted_measurement_order_reversed"] = permuted[::-1]
    return out


def extract_marginal_bitstring(mps: Any) -> tuple[str, list[float]]:
    pi0 = np.array([[1.0, 0.0], [0.0, 0.0]], dtype=np.complex128)
    p0s: list[float] = []
    bits: list[str] = []
    for site in range(len(mps.sites)):
        try:
            value = mps.local_expectation_canonical(pi0, where=site, normalized=True)
        except AttributeError:
            value = mps.local_expectation(pi0, where=[site], max_bond=2, optimize="auto", normalized=True)
        p0 = float(np.real(value.item() if hasattr(value, "item") else value))
        p0 = max(0.0, min(1.0, p0))
        p0s.append(p0)
        bits.append("1" if p0 < 0.5 else "0")
    return "".join(bits), p0s


def sample_mps(mps: Any, count: int, perm: list[int]) -> dict[str, Any]:
    import collections

    if count <= 0:
        return {"status": "skipped", "samples": 0}
    counts: collections.Counter[str] = collections.Counter()
    for item in list(mps.sample(count)):
        bits = item[0] if isinstance(item, tuple) else item
        raw = "".join(str(int(b)) for b in bits)
        variants = bit_variants(raw, perm)
        counts[variants.get("permuted_measurement_order_reversed", raw[::-1])] += 1
    top = counts.most_common(20)
    return {
        "status": "ok",
        "samples": count,
        "top_qiskit_order": [{"bitstring": b, "count": c, "fraction": c / count} for b, c in top],
        "top_bitstring_qiskit_order": top[0][0] if top else None,
        "top_count": top[0][1] if top else 0,
        "top_fraction": top[0][1] / count if top else 0.0,
    }


def final_perm_from_measure_layers(measure_layers: list[Any], nq: int) -> list[int]:
    for layer in reversed(measure_layers):
        if "measure" in layer.count_ops():
            return [bit_index(inst.qubits[0]) for inst in layer if inst.operation.name == "measure"]
    return list(range(nq))


def mpo_to_mps_measure_safe(
    mpo_core: Any,
    layers_left: list[Any],
    layers_right: list[Any],
    max_bond: int,
    cutoff: float,
) -> tuple[Any, list[int]]:
    from qiskit import QuantumCircuit
    from qiskit_quimb import quimb_circuit
    from quimb.tensor import Circuit, CircuitMPS
    import circuit_mpo
    import utils

    q2c = lambda qc: quimb_circuit(qc.decompose("unitary"), Circuit, to_backend=None)
    nq = len(mpo_core.sites)
    final_mps = quimb_circuit(QuantumCircuit(nq), quimb_circuit_class=CircuitMPS, to_backend=None).psi

    left_unitary = [layer for layer in layers_left if not is_nonunitary_layer(layer)]
    if left_unitary:
        left_layers = list(utils.iter_layers(utils.merge_layers(left_unitary).inverse()))
        for layer in left_layers:
            layer_mpo = circuit_mpo.mpo_from_circuit(q2c(layer))
            final_mps = layer_mpo.apply(final_mps, compress=True, max_bond=max_bond, cutoff=cutoff)

    final_mps = mpo_core.apply(final_mps, compress=True, max_bond=max_bond, cutoff=cutoff)

    final_meas = []
    for layer in layers_right:
        if is_nonunitary_layer(layer):
            final_meas.append(layer)
            continue
        layer_mpo = circuit_mpo.mpo_from_circuit(q2c(layer))
        final_mps = layer_mpo.apply(final_mps, compress=True, max_bond=max_bond, cutoff=cutoff)

    return final_mps, final_perm_from_measure_layers(final_meas, nq)


def checkpoint_path(out_dir: Path) -> Path:
    return out_dir / "checkpoint.pkl"


def save_checkpoint(out_dir: Path, state: dict[str, Any]) -> None:
    path = checkpoint_path(out_dir)
    tmp = path.with_suffix(".tmp")
    with tmp.open("wb") as f:
        pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)


def load_checkpoint(out_dir: Path) -> dict[str, Any] | None:
    path = checkpoint_path(out_dir)
    if not path.exists():
        return None
    with path.open("rb") as f:
        return pickle.load(f)


def initialize(args: argparse.Namespace, out_dir: Path) -> dict[str, Any]:
    from qiskit import QuantumCircuit
    from qiskit_quimb import quimb_circuit
    from quimb.tensor import Circuit
    import circuit_mpo
    import unswap
    import utils

    qasm = (ROOT / args.qasm).resolve()
    qc = QuantumCircuit.from_qasm_file(str(qasm))
    if "measure" in qc.count_ops():
        qc = qc.remove_final_measurements(inplace=False)
    center = int(len(qc) * args.center_ratio) if isinstance(args.center_ratio, float) else int(args.center_ratio)
    circuit_left = utils.merge_gates(qc[:center], qc.num_qubits).inverse()
    circuit_right = utils.merge_gates(qc[center:], qc.num_qubits)
    circuit_left.measure_all()
    circuit_right.measure_all()

    layers_left = list(utils.iter_layers(circuit_left))
    layers_right = list(utils.iter_layers(circuit_right))
    layers_left = unswap.rewire_layers(layers_left, np.arange(qc.num_qubits, dtype=int), seed=args.seed, sabre_trials=args.sabre_trials)
    layers_right = unswap.rewire_layers(layers_right, np.arange(qc.num_qubits, dtype=int), seed=args.seed, sabre_trials=args.sabre_trials)
    init_meas = layers_left[-2:]
    final_meas = layers_right[-2:]
    layers_left = layers_left[:-2]
    layers_right = layers_right[:-2]

    q2c = lambda circ: quimb_circuit(circ.decompose("unitary"), Circuit, to_backend=None)
    mpo_core = circuit_mpo.mpo_from_circuit(q2c(QuantumCircuit(qc.num_qubits)))

    return {
        "qasm": str(qasm.relative_to(ROOT)),
        "num_qubits": qc.num_qubits,
        "circuit_len": len(qc),
        "circuit_ops": dict(qc.count_ops()),
        "T_U": count_quantum_ops(qc),
        "T_UL": count_quantum_ops(circuit_left),
        "T_UR": count_quantum_ops(circuit_right),
        "mpo_core": mpo_core,
        "layers_left": layers_left,
        "layers_right": layers_right,
        "init_meas": init_meas,
        "final_meas": final_meas,
        "ii_left": 0,
        "ii_right": 0,
        "current_u_consumed": 0,
        "total_u_consumed": 0,
        "total_u_consumed_left": 0,
        "total_u_consumed_right": 0,
        "cycles": 0,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "out_dir": str(out_dir),
    }


def summarize_state(state: dict[str, Any], status: str, started: float, args: argparse.Namespace) -> dict[str, Any]:
    return {
        "status": status,
        "qasm": state.get("qasm"),
        "num_qubits": state.get("num_qubits"),
        "circuit_len": state.get("circuit_len"),
        "circuit_ops": state.get("circuit_ops"),
        "T_U": state.get("T_U"),
        "total_u_consumed": state.get("total_u_consumed"),
        "total_u_consumed_left": state.get("total_u_consumed_left"),
        "total_u_consumed_right": state.get("total_u_consumed_right"),
        "remaining_estimate": int(state.get("T_U", 0) - state.get("total_u_consumed", 0)),
        "layers_left": len(state.get("layers_left", [])),
        "layers_right": len(state.get("layers_right", [])),
        "ii_left": state.get("ii_left"),
        "ii_right": state.get("ii_right"),
        "cycles": state.get("cycles"),
        "mpo_info": tn_info(state["mpo_core"]),
        "elapsed_this_slice": time.perf_counter() - started,
        "max_rss_mb": rss_mb(),
        "parameters": vars(args),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def run(args: argparse.Namespace) -> int:
    from qiskit.transpiler.exceptions import TranspilerError
    from qiskit_quimb import quimb_circuit
    from quimb.tensor import Circuit
    import circuit_mpo
    import unswap
    import utils

    out_dir = (ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    status_path = out_dir / "status.json"
    result_path = out_dir / "result.json"
    stats_path = out_dir / "stats.jsonl"
    started = time.perf_counter()

    state = load_checkpoint(out_dir)
    if state is None:
        state = initialize(args, out_dir)
        save_checkpoint(out_dir, state)
        append_jsonl(stats_path, [{"stage": "initialize", "rss_mb": rss_mb(), **summarize_state(state, "checkpoint", started, args)}])

    q2c = lambda qc: quimb_circuit(qc.decompose("unitary"), Circuit, to_backend=None)
    stats: list[dict[str, Any]] = []

    try:
        while state["ii_left"] < len(state["layers_left"]) or state["ii_right"] < len(state["layers_right"]):
            if time.perf_counter() - started >= args.time_budget:
                save_checkpoint(out_dir, state)
                write_json(status_path, summarize_state(state, "checkpoint", started, args))
                append_jsonl(stats_path, stats)
                return 2

            ii_left = state["ii_left"]
            ii_right = state["ii_right"]
            layers_left = state["layers_left"]
            layers_right = state["layers_right"]
            mpo_core = state["mpo_core"]

            if ii_left < len(layers_left):
                try:
                    mpo_left = circuit_mpo.apply_circuit(
                        mpo_core,
                        q2c(layers_left[ii_left].inverse()),
                        side="right",
                        max_bond=args.max_bond,
                        cutoff=args.cutoff,
                    )
                    counts_left = utils.elem_counts(mpo_left)
                except (KeyboardInterrupt, TranspilerError):
                    raise
            else:
                mpo_left = None
                counts_left = 1e30

            if ii_right < len(layers_right):
                try:
                    mpo_right = circuit_mpo.apply_circuit(
                        mpo_core,
                        q2c(layers_right[ii_right]),
                        side="left",
                        max_bond=args.max_bond,
                        cutoff=args.cutoff,
                    )
                    counts_right = utils.elem_counts(mpo_right)
                except (KeyboardInterrupt, TranspilerError):
                    raise
            else:
                mpo_right = None
                counts_right = 1e30

            do_left = counts_left < counts_right
            selected_counts = counts_left if do_left else counts_right

            if selected_counts < args.unswap_threshold:
                if do_left:
                    layer = layers_left[ii_left]
                    state["mpo_core"] = mpo_left
                    state["ii_left"] += 1
                    state["total_u_consumed_left"] += count_quantum_ops(layer)
                    side = "L"
                else:
                    layer = layers_right[ii_right]
                    state["mpo_core"] = mpo_right
                    state["ii_right"] += 1
                    state["total_u_consumed_right"] += count_quantum_ops(layer)
                    side = "R"
                new_u = count_quantum_ops(layer)
                state["current_u_consumed"] += new_u
                state["total_u_consumed"] += new_u
                if state["total_u_consumed"] % 250 < new_u:
                    stats.append({"stage": "absorb", "side": side, "u": new_u, **summarize_state(state, "running", started, args)})
            else:
                mpo_core, (perm_left, perm_right), unswap_stats = unswap.unswap(
                    state["mpo_core"],
                    hows=tuple(args.hows),
                    max_bond=args.max_bond,
                    cutoff=args.cutoff,
                    max_its=args.max_its,
                    equal=args.equal,
                    to_backend=None,
                    t0=started,
                )
                stats.extend({"stage": "unswap_inner", **row} for row in unswap_stats)
                state["mpo_core"] = mpo_core

                if state["ii_left"] < len(state["layers_left"]):
                    new_left = state["layers_left"][state["ii_left"] :] + state["init_meas"]
                    rewired_left = unswap.rewire_layers(new_left, perm_left, seed=args.seed, sabre_trials=args.sabre_trials)
                    state["init_meas"] = rewired_left[-2:]
                    state["layers_left"] = rewired_left[:-2]
                else:
                    state["layers_left"] = []

                if state["ii_right"] < len(state["layers_right"]):
                    new_right = state["layers_right"][state["ii_right"] :] + state["final_meas"]
                    rewired_right = unswap.rewire_layers(new_right, perm_right, seed=args.seed, sabre_trials=args.sabre_trials)
                    state["final_meas"] = rewired_right[-2:]
                    state["layers_right"] = rewired_right[:-2]
                else:
                    state["layers_right"] = []

                state["ii_left"] = 0
                state["ii_right"] = 0
                state["current_u_consumed"] = 0
                state["cycles"] += 1
                save_checkpoint(out_dir, state)
                stats.append({"stage": "unswap_cycle", **summarize_state(state, "checkpoint", started, args)})
                write_json(status_path, summarize_state(state, "checkpoint", started, args))

                if (state["T_U"] - state["total_u_consumed"]) <= args.early_stopping_gates:
                    break

        left_remaining = state["layers_left"][state["ii_left"] :] if state["ii_left"] < len(state["layers_left"]) else []
        right_remaining = state["layers_right"][state["ii_right"] :] if state["ii_right"] < len(state["layers_right"]) else []
        left_final = left_remaining + state["init_meas"]
        right_final = right_remaining + state["final_meas"]

        mps, perm = mpo_to_mps_measure_safe(
            state["mpo_core"],
            left_final,
            right_final,
            max_bond=args.mps_max_bond,
            cutoff=args.cutoff,
        )
        marginal_raw, p0s = extract_marginal_bitstring(mps)
        marginal_variants = bit_variants(marginal_raw, perm)
        sampling = sample_mps(mps, args.samples, perm)
        final = sampling.get("top_bitstring_qiskit_order") or marginal_variants.get("permuted_measurement_order_reversed")
        result = {
            "status": "ok",
            "final_candidate_qiskit_order": final,
            "candidate_strategy": "sample_top_qiskit_order" if sampling.get("top_bitstring_qiskit_order") else "marginal_permuted_measurement_order_reversed",
            "marginal": {
                "raw_site_order": marginal_raw,
                "variants": marginal_variants,
                "p0s_raw_site_order": p0s,
            },
            "sampling": sampling,
            "final_measurement_permutation": perm,
            "mps_info": tn_info(mps),
            **summarize_state(state, "ok", started, args),
        }
        write_json(result_path, result)
        write_json(status_path, result)
        append_jsonl(stats_path, stats)
        return 0
    except Exception as exc:  # noqa: BLE001
        payload = {
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            **summarize_state(state, "error", started, args),
        }
        write_json(status_path, payload)
        append_jsonl(stats_path, stats)
        save_checkpoint(out_dir, state)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qasm", default="challenges/very_hard/challenge-48_42.qasm")
    parser.add_argument("--out-dir", default="agent_work/checkpoint_unswap_48_42")
    parser.add_argument("--time-budget", type=float, default=240.0)
    parser.add_argument("--max-bond", type=int, default=512)
    parser.add_argument("--mps-max-bond", type=int, default=512)
    parser.add_argument("--cutoff", type=float, default=0.002)
    parser.add_argument("--unswap-threshold", type=float, default=1_000_000.0)
    parser.add_argument("--early-stopping-gates", type=int, default=500)
    parser.add_argument("--center-ratio", type=float, default=0.5)
    parser.add_argument("--equal", action="store_true")
    parser.add_argument("--max-its", type=int, default=10)
    parser.add_argument("--hows", nargs="+", default=["both", "left", "right"])
    parser.add_argument("--sabre-trials", type=int, default=64)
    parser.add_argument("--samples", type=int, default=512)
    parser.add_argument("--seed", type=int, default=4242)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
