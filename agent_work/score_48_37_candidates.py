#!/usr/bin/env python3
from __future__ import annotations

import argparse
import itertools
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


BASE_CANDIDATES_48_37 = {
    "failed_quimb_sample_top": "100101001010001101010100100101001001000101010001",
    "failed_high_bond_marginal": "100101101110101101010100100100001011010100001010",
    "failed_consensus_mlr": "101101111110101101010100110100001011010100011010",
    "local_bd64_majority": "101101111110101101010100110100000011010100011010",
    "rcm_marginal": "101101111110101100011100110100001001110110011010",
    "degree_bd64_marginal": "001010111111101001000110000100011011111100011010",
    "algebraic_all_rx": "011101101011010110111111101111100011111000110011",
    "algebraic_trailing": "100000000000001000000000000000000000000000000000",
    "reverse_failed_high_bond_marginal": "010100001010110100001001001010101101011101101001",
    "reverse_failed_sample_top": "100010101000100100101001001010101100010100101001",
    "local_low_margin_override_001": "100101111110101101010100110100000011010100011010",
    "local_low_margin_override_002": "100101111110101101010100110100001011010100001010",
    "local_low_margin_override_005": "100101111110101101010100100100001011010100001010",
}


BASE_CANDIDATES_40_35 = {
    "known_correct": "0101100110111111101000011101001010001001",
    "failed_selected_sample": "0101100110101111111000010101001110001001",
    "quimb_gpu_marginal": "0101100110111111101000001101001010001001",
    "quimb_cpu_sample": "0111110111110111101000011110000100001011",
    "degree_bad": "0100000101011110011001001101010110100001",
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
    total = 0.0
    for bit, p1 in zip(qiskit_bits[::-1], p1_logical):
        p = p1 if bit == "1" else 1.0 - p1
        total += math.log(max(1e-15, min(1.0, p)))
    return total


def expand_low_margin_variants(candidates: dict[str, str], max_flips: int) -> dict[str, str]:
    if max_flips <= 0:
        return candidates
    seed = candidates.get("failed_high_bond_marginal")
    local = candidates.get("local_bd64_majority")
    rcm = candidates.get("rcm_marginal")
    if not seed or not local or not rcm:
        return candidates
    positions = sorted({i for i, (a, b, c) in enumerate(zip(seed, local, rcm)) if len({a, b, c}) > 1})
    out = dict(candidates)
    for size in range(1, min(max_flips, len(positions)) + 1):
        for combo in itertools.combinations(positions, size):
            bits = list(seed)
            for pos in combo:
                # Prefer local when it disagrees with the high-bond marginal,
                # otherwise use RCM. This enumerates the plausible disagreement set.
                bits[pos] = local[pos] if local[pos] != seed[pos] else rcm[pos]
            out[f"variant_from_highbond_pos_{'-'.join(map(str, combo))}"] = "".join(bits)
    return out


def run_setting(args: argparse.Namespace, candidates: dict[str, str], order_method: str, max_bond: int, cutoff: float) -> dict[str, Any]:
    from qiskit import QuantumCircuit
    from qiskit_quimb import quimb_circuit
    import quimb.tensor as qtn

    started = time.perf_counter()
    qc = QuantumCircuit.from_qasm_file(str(args.qasm))
    qc, removed = strip_measure(qc)
    to_backend, backend = choose_backend(args.backend)
    graph = graph_from_circuit(qc, set(args.graph_ops), args.recency_alpha)
    order = derive_order(graph["weights"], order_method)
    logical_to_site = [0] * len(order)
    for site, logical in enumerate(order):
        logical_to_site[logical] = site
    mapped = remap_circuit(qc, logical_to_site)

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
    p0s_site = p0s_from_mps(psi, qc.num_qubits)
    p1_site = [1.0 - p0 for p0 in p0s_site]
    p1_logical = [0.0] * len(p1_site)
    for site, p1 in enumerate(p1_site):
        p1_logical[order[site]] = p1
    site_candidate = "".join("1" if p0 < 0.5 else "0" for p0 in p0s_site)
    marginal_qiskit = site_to_qiskit_order(site_candidate, order)

    scores = []
    for label, bitstring in sorted(candidates.items()):
        if len(bitstring) != qc.num_qubits:
            continue
        site_bits = qiskit_to_site_order(bitstring, order)
        probability = mps_bitstring_probability(psi, site_bits, args.prob_optimize)
        ll = marginal_log_likelihood(bitstring, p1_logical)
        scores.append(
            {
                "label": label,
                "bitstring": bitstring,
                "hamming_to_setting_marginal": hamming(bitstring, marginal_qiskit),
                "mps_probability": probability,
                "marginal_log_likelihood": ll,
                "marginal_mean_log_likelihood": ll / qc.num_qubits,
            }
        )

    return {
        "status": "ok",
        "removed_measurements": removed,
        "parameters": {
            "backend": backend,
            "order_method": order_method,
            "max_bond": max_bond,
            "cutoff": cutoff,
            "gate_contract": args.gate_contract,
            "recency_alpha": args.recency_alpha,
            "prob_optimize": args.prob_optimize,
        },
        "mps_info": tn_info(psi),
        "marginal_candidate_qiskit_order": marginal_qiskit,
        "p1_margin_min": min(abs(p - 0.5) for p in p1_logical),
        "p1_margin_mean": float(np.mean([abs(p - 0.5) for p in p1_logical])),
        "p1_margin_max": max(abs(p - 0.5) for p in p1_logical),
        "scores_by_probability": sorted(scores, key=lambda row: (-row["mps_probability"], row["label"])),
        "scores_by_marginal_likelihood": sorted(scores, key=lambda row: (-row["marginal_log_likelihood"], row["label"])),
        "seconds": time.perf_counter() - started,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qasm", type=Path, default=ROOT / "challenges/hard/challenge-48_37.qasm")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/solve_48_37/candidate_scores.json")
    parser.add_argument("--challenge", choices=["48_37", "40_35"], default="48_37")
    parser.add_argument("--backend", choices=["auto", "cuda", "numpy"], default="numpy")
    parser.add_argument("--setting", action="append", default=[], help="order,max_bond,cutoff")
    parser.add_argument("--gate-contract", choices=["auto-mps", "swap+split", "nonlocal"], default="swap+split")
    parser.add_argument("--graph-ops", nargs="+", default=["cx", "swap"])
    parser.add_argument("--recency-alpha", type=float, default=0.15)
    parser.add_argument("--dtype", default="complex128")
    parser.add_argument("--prob-optimize", default="greedy")
    parser.add_argument("--max-variant-flips", type=int, default=2)
    args = parser.parse_args()

    candidates = BASE_CANDIDATES_40_35 if args.challenge == "40_35" else BASE_CANDIDATES_48_37
    candidates = expand_low_margin_variants(candidates, args.max_variant_flips)
    raw_settings = args.setting or ["rcm,32,0.0001"]
    payload = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "qasm": str(args.qasm),
        "challenge": args.challenge,
        "candidate_count": len(candidates),
        "settings": [],
    }
    for raw in raw_settings:
        order, bond, cutoff = raw.split(",", 2)
        payload["settings"].append(run_setting(args, candidates, order, int(bond), float(cutoff)))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n")
    for setting in payload["settings"]:
        params = setting["parameters"]
        best_prob = setting["scores_by_probability"][0]
        best_marg = setting["scores_by_marginal_likelihood"][0]
        print(
            f"{params['order_method']} bd={params['max_bond']} cutoff={params['cutoff']}: "
            f"marginal={setting['marginal_candidate_qiskit_order']} "
            f"best_prob={best_prob['label']}:{best_prob['bitstring']}:{best_prob['mps_probability']:.6g} "
            f"best_marg={best_marg['label']}:{best_marg['bitstring']}:{best_marg['marginal_mean_log_likelihood']:.6f}"
        )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
