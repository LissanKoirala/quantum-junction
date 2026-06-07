#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jobs.aer_tree_tensor_runner import (
    build_interaction_graph,
    make_orders,
    relabel_circuit,
    strip_to_unitary,
)


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def json_safe(value):
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


def mps_to_b_mats(mps) -> list[tuple[np.ndarray, np.ndarray]]:
    gammas, lambdas = mps
    mats = []
    for i, pair in enumerate(gammas):
        a0 = np.asarray(pair[0], dtype=np.complex128)
        a1 = np.asarray(pair[1], dtype=np.complex128)
        if i < len(lambdas):
            lam = np.asarray(lambdas[i], dtype=np.complex128)
            a0 = a0 @ np.diag(lam)
            a1 = a1 @ np.diag(lam)
        mats.append((a0, a1))
    return mats


def p1s_from_aer_mps(mps) -> tuple[list[float], float]:
    mats = mps_to_b_mats(mps)
    n = len(mats)
    left = [None] * (n + 1)
    right = [None] * (n + 1)
    left[0] = np.array([[1.0 + 0.0j]])
    for i, (a0, a1) in enumerate(mats):
        left[i + 1] = a0.conj().T @ left[i] @ a0 + a1.conj().T @ left[i] @ a1
    right[n] = np.array([[1.0 + 0.0j]])
    for i in reversed(range(n)):
        a0, a1 = mats[i]
        right[i] = a0 @ right[i + 1] @ a0.conj().T + a1 @ right[i + 1] @ a1.conj().T
    norm = float(np.real(np.trace(left[n])))
    p1s = []
    for i, (_a0, a1) in enumerate(mats):
        num = np.trace((a1.conj().T @ left[i] @ a1) @ right[i + 1])
        p1 = float(np.real(num) / norm) if norm else float("nan")
        p1s.append(max(0.0, min(1.0, p1)))
    return p1s, norm


def run_trial(
    unitary: QuantumCircuit,
    order: list[int],
    order_method: str,
    bond_dim: int,
    truncation_threshold: float,
    seed: int,
    max_parallel_threads: int,
) -> dict:
    start = time.perf_counter()
    mapped = relabel_circuit(unitary, order)
    mapped.save_matrix_product_state()
    sim = AerSimulator(
        method="matrix_product_state",
        matrix_product_state_max_bond_dimension=bond_dim,
        matrix_product_state_truncation_threshold=truncation_threshold,
        seed_simulator=seed,
        max_parallel_threads=max_parallel_threads,
    )
    result = sim.run(mapped).result()
    mps = result.data(0)["matrix_product_state"]
    p1_new, norm = p1s_from_aer_mps(mps)
    p1_original = [0.0] * len(order)
    for new_i, original_i in enumerate(order):
        p1_original[original_i] = p1_new[new_i]
    logical_q0_first = "".join("1" if p >= 0.5 else "0" for p in p1_original)
    qiskit_order = logical_q0_first[::-1]
    margins = [abs(p - 0.5) for p in p1_original]
    return {
        "event": "candidate",
        "order_method": order_method,
        "order": order,
        "bond_dim": bond_dim,
        "truncation_threshold": truncation_threshold,
        "candidate_logical_q0_first": logical_q0_first,
        "candidate_qiskit_order": qiskit_order,
        "p1_logical_q0_first": p1_original,
        "mps_norm": norm,
        "margin_min": float(min(margins)),
        "margin_mean": float(np.mean(margins)),
        "margin_max": float(max(margins)),
        "seconds": time.perf_counter() - start,
        "max_rss_mb": rss_mb(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qasm", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "solve_64_41" / "aer_mps_marginals.jsonl")
    parser.add_argument("--order-methods", nargs="+", default=["native"])
    parser.add_argument("--bond-dims", nargs="+", type=int, default=[64])
    parser.add_argument("--truncation-threshold", type=float, default=1e-12)
    parser.add_argument("--seed", type=int, default=20260607)
    parser.add_argument("--max-parallel-threads", type=int, default=1)
    args = parser.parse_args()

    qasm = args.qasm if args.qasm.is_absolute() else ROOT / args.qasm
    qc = QuantumCircuit.from_qasm_file(str(qasm))
    unitary = strip_to_unitary(qc)
    graph = build_interaction_graph(unitary)
    weights = graph.pop("weights")
    order_rows = make_orders(weights, args.order_methods)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "event": "start",
        "qasm": str(qasm),
        "qubits": unitary.num_qubits,
        "ops": len(unitary),
        "order_methods": args.order_methods,
        "bond_dims": args.bond_dims,
        "truncation_threshold": args.truncation_threshold,
    }
    print(json.dumps(json_safe(header), sort_keys=True), flush=True)
    with args.out.open("a") as f:
        f.write(json.dumps(json_safe(header), sort_keys=True) + "\n")
    for row in order_rows:
        if row.get("duplicate_of"):
            continue
        for bond_dim in args.bond_dims:
            try:
                trial = run_trial(
                    unitary,
                    row["order"],
                    row["method"],
                    bond_dim,
                    args.truncation_threshold,
                    args.seed,
                    args.max_parallel_threads,
                )
            except Exception as exc:  # noqa: BLE001
                import traceback

                trial = {
                    "event": "error",
                    "order_method": row["method"],
                    "bond_dim": bond_dim,
                    "truncation_threshold": args.truncation_threshold,
                    "error_type": type(exc).__name__,
                    "error": repr(exc),
                    "traceback_tail": traceback.format_exc()[-1800:],
                    "max_rss_mb": rss_mb(),
                }
            print(json.dumps(json_safe(trial), sort_keys=True), flush=True)
            with args.out.open("a") as f:
                f.write(json.dumps(json_safe(trial), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
