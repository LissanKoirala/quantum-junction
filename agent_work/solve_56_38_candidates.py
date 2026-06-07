#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobs.quimb_tree_tensor_runner import (  # noqa: E402
    choose_backend,
    derive_order,
    graph_from_circuit,
    p0s_from_mps,
    remap_circuit,
    strip_measure,
    tn_info,
)


DEFAULT_CANDIDATES = {
    "historical_rcm_sample_top": "10011001011110000000010011010101100001001001110110110001",
    "historical_rcm_marginal": "11001101111010101110010101100110101001111001100100101001",
    "local_rcm_bd16_marginal": "10001100010000001001000001001001011111110000101111111111",
    "local_rcm_bd32_marginal": "10011101011000010010010101000000000001011101100010100001",
    "local_weighted_bd32_marginal": "00000000010011000111110010010111000011010111000111000001",
    "local_degree_bd32_marginal": "00011001011111100101010111000000100101001111001111000100",
    "local_mpo_early_marginal": "11011101010110111101010011001100010011111100100111101101",
    "local_mpo_early_sample": "00011101011000001001100011011110101001100100001111101101",
    "algebraic_rx_angle_top": "01000110100110101001111110001110101111011000101011010000",
    "algebraic_greedy_top": "01110111000010010011000100100100000001000111110000000000",
    "consensus_all_sources": "01001101011011100100010111000110010001111100000110100001",
    "consensus_flip_q5": "01001101011011100100010111000110010001111100000110000001",
    "consensus_flip_q17": "01001101011011100100010111000110010001011100000110100001",
    "consensus_flip_q22": "01001101011011100100010111000110000001111100000110100001",
    "consensus_flip_q5_q17_q22": "01001101011011100100010111000110000001011100000110000001",
    "historical_rcm_marginal_flip_q29": "11001101111010101110010101000110101001111001100100101001",
    "historical_rcm_marginal_flip_q23": "11001101111010101110010101100110001001111001100100101001",
    "historical_rcm_marginal_flip_q21": "11001101111010101110010101100110100001111001100100101001",
}


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


def hamming(a: str, b: str) -> int:
    return sum(x != y for x, y in zip(a, b))


def qiskit_to_site_order(qiskit_bits: str, site_to_logical: list[int]) -> str:
    logical_bits = qiskit_bits[::-1]
    return "".join(logical_bits[logical] for logical in site_to_logical)


def site_to_qiskit_order(site_bits: str, site_to_logical: list[int]) -> str:
    logical = ["0"] * len(site_bits)
    for site, bit in enumerate(site_bits):
        logical[site_to_logical[site]] = bit
    return "".join(logical)[::-1]


def mps_bitstring_probability(psi: Any, site_bits: str, optimize: str) -> float:
    tn = psi.isel({psi.site_ind(site): int(bit) for site, bit in zip(psi.sites, site_bits)})
    amp = tn.contract(all, optimize=optimize)
    return float(abs(complex(amp)) ** 2)


def marginal_log_likelihood(qiskit_bits: str, p1_logical: list[float]) -> float:
    logical_bits = qiskit_bits[::-1]
    total = 0.0
    for bit, p1 in zip(logical_bits, p1_logical):
        p = p1 if bit == "1" else 1.0 - p1
        total += math.log(max(1e-15, min(1.0, p)))
    return total


def run_setting(args: argparse.Namespace, order_method: str, max_bond: int, cutoff: float) -> dict[str, Any]:
    from qiskit import QuantumCircuit
    from qiskit_quimb import quimb_circuit
    import quimb.tensor as qtn

    started = time.perf_counter()
    qasm = args.qasm.resolve()
    qc = QuantumCircuit.from_qasm_file(str(qasm))
    qc, removed = strip_measure(qc)

    to_backend, backend = choose_backend(args.backend)
    graph = graph_from_circuit(qc, set(args.graph_ops), args.recency_alpha)
    order = derive_order(graph["weights"], order_method)
    logical_to_site = [0] * len(order)
    for site, logical in enumerate(order):
        logical_to_site[logical] = site

    mapped = remap_circuit(qc, logical_to_site)
    build_start = time.perf_counter()
    circ = quimb_circuit(
        mapped,
        quimb_circuit_class=qtn.CircuitMPS,
        max_bond=max_bond,
        cutoff=cutoff,
        gate_contract=args.gate_contract,
        dtype=args.dtype,
        to_backend=to_backend,
    )
    psi = circ.psi
    build_seconds = time.perf_counter() - build_start

    p0s_site = p0s_from_mps(psi, qc.num_qubits)
    site_candidate = "".join("1" if p0 < 0.5 else "0" for p0 in p0s_site)
    marginal_qiskit = site_to_qiskit_order(site_candidate, order)
    p1_site = [1.0 - p0 for p0 in p0s_site]
    p1_logical = [0.0] * len(p1_site)
    for site, p1 in enumerate(p1_site):
        p1_logical[order[site]] = p1

    scores = []
    for label, bitstring in sorted(DEFAULT_CANDIDATES.items()):
        if len(bitstring) != qc.num_qubits:
            continue
        site_bits = qiskit_to_site_order(bitstring, order)
        probability = mps_bitstring_probability(psi, site_bits, args.prob_optimize)
        log_likelihood = marginal_log_likelihood(bitstring, p1_logical)
        scores.append(
            {
                "label": label,
                "bitstring": bitstring,
                "hamming_to_setting_marginal": hamming(bitstring, marginal_qiskit),
                "mps_probability": probability,
                "marginal_log_likelihood": log_likelihood,
                "marginal_mean_log_likelihood": log_likelihood / qc.num_qubits,
            }
        )

    scores_by_probability = sorted(scores, key=lambda row: (-row["mps_probability"], row["label"]))
    scores_by_marginal = sorted(scores, key=lambda row: (-row["marginal_log_likelihood"], row["label"]))
    return {
        "status": "ok",
        "qasm": str(qasm),
        "num_qubits": qc.num_qubits,
        "removed_measurements": removed,
        "parameters": {
            "backend": backend,
            "order_method": order_method,
            "max_bond": max_bond,
            "cutoff": cutoff,
            "gate_contract": args.gate_contract,
            "graph_ops": args.graph_ops,
            "recency_alpha": args.recency_alpha,
            "prob_optimize": args.prob_optimize,
        },
        "mps_info": tn_info(psi),
        "mps_build_seconds": build_seconds,
        "total_seconds": time.perf_counter() - started,
        "marginal_candidate_qiskit_order": marginal_qiskit,
        "p1_margin_min": min(abs(p - 0.5) for p in p1_logical),
        "p1_margin_mean": float(np.mean([abs(p - 0.5) for p in p1_logical])),
        "p1_margin_max": max(abs(p - 0.5) for p in p1_logical),
        "scores_by_probability": scores_by_probability,
        "scores_by_marginal_likelihood": scores_by_marginal,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qasm", type=Path, default=ROOT / "challenges/hard/challenge-56_38.qasm")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/solve_56_38/candidate_scores.json")
    parser.add_argument("--backend", choices=["auto", "cuda", "numpy"], default="numpy")
    parser.add_argument("--setting", action="append", default=[], help="order,max_bond,cutoff")
    parser.add_argument("--gate-contract", choices=["auto-mps", "swap+split", "nonlocal"], default="swap+split")
    parser.add_argument("--graph-ops", nargs="+", default=["cx", "swap"])
    parser.add_argument("--recency-alpha", type=float, default=0.15)
    parser.add_argument("--dtype", default="complex128")
    parser.add_argument("--prob-optimize", default="greedy")
    args = parser.parse_args()

    raw_settings = args.setting or ["rcm,32,0.0001"]
    payload = {"created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "settings": []}
    for raw in raw_settings:
        order, bond, cutoff = raw.split(",", 2)
        payload["settings"].append(run_setting(args, order, int(bond), float(cutoff)))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n")

    for setting in payload["settings"]:
        params = setting["parameters"]
        best_prob = setting["scores_by_probability"][0]
        best_marginal = setting["scores_by_marginal_likelihood"][0]
        print(
            f"{params['order_method']} bd={params['max_bond']} cutoff={params['cutoff']}: "
            f"marginal={setting['marginal_candidate_qiskit_order']} "
            f"best_prob={best_prob['label']}:{best_prob['mps_probability']:.6g} "
            f"best_marginal={best_marginal['label']}:{best_marginal['marginal_mean_log_likelihood']:.6f}"
        )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
