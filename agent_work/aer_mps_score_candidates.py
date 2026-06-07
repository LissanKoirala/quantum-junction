#!/usr/bin/env python3
from __future__ import annotations

import argparse
import itertools
import json
import math
import resource
import sys
import time
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_work.aer_mps_marginals import mps_to_b_mats, p1s_from_aer_mps  # noqa: E402
from jobs.aer_tree_tensor_runner import (  # noqa: E402
    build_interaction_graph,
    make_orders,
    relabel_circuit,
    strip_to_unitary,
)


KNOWN_40_35 = "0101100110111111101000011101001010001001"

BASE_CANDIDATES = {
    "40_35": {
        "known_correct": KNOWN_40_35,
        "quimb_high_marginal": "0101100110111111101000001101001010001001",
        "failed_selected_sample": "0101100110101111111000010101001110001001",
        "aer_native_bd64": "0101100111101111111000010101000110001001",
        "aer_rcm_bd64": "0101100110111111001100000101010110001001",
        "aer_spectral_bd64": "0111100110111011101100011101001010001001",
        "aer_mincut_bd64": "0111100110111110101100010101001010001001",
        "aer_greedy_bd64": "0101100111100110111100110101001001001001",
    },
    "48_37": {
        "failed_sample_top": "100101001010001101010100100101001001000101010001",
        "failed_high_marginal": "100101101110101101010100100100001011010100001010",
        "failed_consensus_mlr": "101101111110101101010100110100001011010100011010",
        "failed_mincut_highcorr": "100101101110101101010100100100001011010100011010",
        "failed_spectral_highcorr": "101111111110101101010100100100000011010100001010",
        "failed_raw_spectral": "101111111110101101001100100100000001010100001000",
        "aer_spectral_bd64": "101111111110101101001100100100000001010100001000",
        "aer_mincut_bd64": "100101001110101101000100100100011011010101011010",
        "aer_bd32_native": "100111110110111101011100100110001011100101001010",
        "aer_bd32_rcm": "110101011110111101010100100000000011110100011000",
        "aer_bd32_spectral": "101111111110101100000100101100001001110100001010",
        "aer_bd32_mincut": "101101011110101101000100110110010001010100111010",
        "aer_bd32_greedy": "100101011110111101010100100100000010010000101000",
        "local_bd64_majority": "101101111110101101010100110100000011010100011010",
        "rcm_marginal": "101101111110101100011100110100001001110110011010",
        "rcm_sample": "001110010010111100111010100101011000100000001000",
        "degree_bd64": "001010111111101001000110000100011011111100011010",
        "aer_tree_top": "101101100100100101010000110000000001010100110010",
        "algebraic_exact": "111000011010011001010111100111011100010111101001",
        "spectral_low_k1": "001111111110101101001100100100000001010100001000",
        "spectral_low_k2": "001111111110101101001100100100000001010100001010",
        "spectral_low_k3": "001111111110101101001100100100000011010100001010",
        "spectral_low_k4": "001111111110101101011100100100000011010100001010",
        "spectral_low_k5": "001111111110101101010100100100000011010100001010",
        "spectral_low_k6": "001111111110101101010100100110000011010100001010",
        "spectral_low_k7": "001111111110101101010100110110000011010100001010",
        "spectral_low_k8": "001111111110101101010100110110001011010100001010",
        "spectral_low_k9": "000111111110101101010100110110001011010100001010",
    },
    "64_41": {
        "old_rejected": "0001000111010011100110010011110111000000100011010001101010110010",
        "native_rejected": "1011001100010011000101010011110111000000000011010001100011110010",
        "spectral_marginal": "1011001100010011000101010011110111001000000011010001100011110010",
        "rcm_marginal": "1011001100010011000101010011110111001000000011010001000011110010",
        "tree_rejected": "1011001100010011000101011011110101001000000011010000100011110010",
    },
}


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


def hamming(a: str, b: str) -> int:
    return sum(x != y for x, y in zip(a, b))


def qiskit_to_site_bits(qiskit_bits: str, order: list[int]) -> str:
    logical_q0_first = qiskit_bits[::-1]
    return "".join(logical_q0_first[original_i] for original_i in order)


def site_to_qiskit_bits(site_bits: str, order: list[int]) -> str:
    logical = ["0"] * len(order)
    for new_i, original_i in enumerate(order):
        logical[original_i] = site_bits[new_i]
    return "".join(logical[::-1])


def mps_probability(mats, norm: float, site_bits: str) -> float:
    vec = np.array([[1.0 + 0.0j]])
    for bit, (a0, a1) in zip(site_bits, mats):
        vec = vec @ (a1 if bit == "1" else a0)
    amp = complex(np.ravel(vec)[0])
    return float((abs(amp) ** 2) / max(norm, 1e-300))


def marginal_log_likelihood(qiskit_bits: str, p1_original: list[float]) -> float:
    total = 0.0
    for bit, p1 in zip(qiskit_bits[::-1], p1_original):
        p = p1 if bit == "1" else 1.0 - p1
        total += math.log(max(1e-15, min(1.0, p)))
    return total


def add_low_margin_variants(
    candidates: dict[str, str],
    p1_original: list[float],
    base_names: list[str],
    low_margin_count: int,
    max_flips: int,
) -> dict[str, str]:
    out = dict(candidates)
    n = len(p1_original)
    qiskit_positions = [
        n - 1 - q
        for q, _margin in sorted(
            enumerate(abs(p - 0.5) for p in p1_original),
            key=lambda item: (item[1], item[0]),
        )[:low_margin_count]
    ]
    for base_name in base_names:
        base = candidates.get(base_name)
        if not base or len(base) != n:
            continue
        for flips in range(1, max_flips + 1):
            for combo in itertools.combinations(qiskit_positions, flips):
                bits = list(base)
                for pos in combo:
                    bits[pos] = "1" if bits[pos] == "0" else "0"
                out[f"{base_name}__lmflip_{'-'.join(map(str, combo))}"] = "".join(bits)
    return out


def run_setting(args, order_row: dict, bond_dim: int) -> dict:
    start = time.perf_counter()
    qc = QuantumCircuit.from_qasm_file(str(args.qasm))
    unitary = strip_to_unitary(qc)
    order = order_row["order"]
    mapped = relabel_circuit(unitary, order)
    mapped.save_matrix_product_state()
    sim = AerSimulator(
        method="matrix_product_state",
        matrix_product_state_max_bond_dimension=bond_dim,
        matrix_product_state_truncation_threshold=args.truncation_threshold,
        seed_simulator=args.seed,
        max_parallel_threads=args.max_parallel_threads,
    )
    result = sim.run(mapped).result()
    mps = result.data(0)["matrix_product_state"]
    mats = mps_to_b_mats(mps)
    p1_site, norm = p1s_from_aer_mps(mps)
    p1_original = [0.0] * len(order)
    for new_i, original_i in enumerate(order):
        p1_original[original_i] = p1_site[new_i]
    site_marginal = "".join("1" if p >= 0.5 else "0" for p in p1_site)
    qiskit_marginal = site_to_qiskit_bits(site_marginal, order)

    candidates = dict(BASE_CANDIDATES[args.challenge])
    if args.candidate_file:
        for raw in args.candidate_file.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" in line:
                name, bits = line.split("\t", 1)
            elif "," in line:
                name, bits = line.split(",", 1)
            elif ":" in line:
                name, bits = line.split(":", 1)
            else:
                name, bits = f"file_{len(candidates)}", line
            candidates[name.strip()] = bits.strip()
    if args.extra_candidate:
        for raw in args.extra_candidate:
            name, bits = raw.split("=", 1) if "=" in raw else (f"extra_{len(candidates)}", raw)
            candidates[name] = bits
    base_names = args.variant_base or [
        "aer_spectral_bd64",
        "aer_mincut_bd64",
        "failed_high_marginal",
        "local_bd64_majority",
        "rcm_marginal",
        "known_correct",
    ]
    candidates["trial_marginal"] = qiskit_marginal
    candidates = add_low_margin_variants(
        candidates,
        p1_original,
        base_names=base_names,
        low_margin_count=args.low_margin_count,
        max_flips=args.max_flips,
    )

    rows = []
    for label, bits in candidates.items():
        if len(bits) != unitary.num_qubits:
            continue
        site_bits = qiskit_to_site_bits(bits, order)
        prob = mps_probability(mats, norm, site_bits)
        ll = marginal_log_likelihood(bits, p1_original)
        row = {
            "label": label,
            "bitstring": bits,
            "probability": prob,
            "log_likelihood": ll,
            "mean_log_likelihood": ll / unitary.num_qubits,
            "hamming_to_trial_marginal": hamming(bits, qiskit_marginal),
        }
        known = BASE_CANDIDATES.get(args.challenge, {}).get("known_correct")
        if known and len(known) == len(bits):
            row["hamming_to_known"] = hamming(bits, known)
            row["is_known"] = bits == known
        rows.append(row)

    rows_by_probability = sorted(rows, key=lambda r: (-r["probability"], -r["log_likelihood"], r["label"]))
    rows_by_ll = sorted(rows, key=lambda r: (-r["log_likelihood"], -r["probability"], r["label"]))
    return {
        "event": "setting",
        "challenge": args.challenge,
        "qasm": str(args.qasm),
        "order_method": order_row["method"],
        "order": order,
        "bond_dim": bond_dim,
        "truncation_threshold": args.truncation_threshold,
        "mps_norm": norm,
        "trial_marginal": qiskit_marginal,
        "p1_original": p1_original,
        "margin_min": float(min(abs(p - 0.5) for p in p1_original)),
        "margin_mean": float(np.mean([abs(p - 0.5) for p in p1_original])),
        "margin_max": float(max(abs(p - 0.5) for p in p1_original)),
        "candidate_count": len(rows),
        "top_by_probability": rows_by_probability[: args.top_k],
        "top_by_log_likelihood": rows_by_ll[: args.top_k],
        "known_row": next((r for r in rows if r.get("is_known")), None),
        "seconds": time.perf_counter() - start,
        "rss_mb": rss_mb(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qasm", type=Path, required=True)
    parser.add_argument("--challenge", choices=sorted(BASE_CANDIDATES), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--candidate-file", type=Path)
    parser.add_argument("--order-methods", nargs="+", default=["spectral"])
    parser.add_argument("--bond-dims", nargs="+", type=int, default=[64])
    parser.add_argument("--truncation-threshold", type=float, default=1e-12)
    parser.add_argument("--seed", type=int, default=20260607)
    parser.add_argument("--max-parallel-threads", type=int, default=1)
    parser.add_argument("--low-margin-count", type=int, default=10)
    parser.add_argument("--max-flips", type=int, default=3)
    parser.add_argument("--variant-base", action="append", default=[])
    parser.add_argument("--extra-candidate", action="append", default=[])
    parser.add_argument("--top-k", type=int, default=30)
    args = parser.parse_args()

    args.qasm = args.qasm if args.qasm.is_absolute() else ROOT / args.qasm
    qc = QuantumCircuit.from_qasm_file(str(args.qasm))
    unitary = strip_to_unitary(qc)
    graph = build_interaction_graph(unitary)
    weights = graph.pop("weights")
    order_rows = make_orders(weights, args.order_methods)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "event": "start",
        "challenge": args.challenge,
        "qasm": str(args.qasm),
        "order_methods": args.order_methods,
        "bond_dims": args.bond_dims,
        "low_margin_count": args.low_margin_count,
        "max_flips": args.max_flips,
        "top_k": args.top_k,
    }
    with args.out.open("w") as f:
        f.write(json.dumps(json_safe(header), sort_keys=True) + "\n")
    print(json.dumps(json_safe(header), sort_keys=True), flush=True)

    for order_row in order_rows:
        if order_row.get("duplicate_of"):
            continue
        for bond_dim in args.bond_dims:
            row = run_setting(args, order_row, bond_dim)
            with args.out.open("a") as f:
                f.write(json.dumps(json_safe(row), sort_keys=True) + "\n")
            best = row["top_by_probability"][0]
            msg = {
                "event": "best",
                "challenge": args.challenge,
                "order_method": row["order_method"],
                "bond_dim": bond_dim,
                "best_label": best["label"],
                "best_bitstring": best["bitstring"],
                "best_probability": best["probability"],
                "trial_marginal": row["trial_marginal"],
                "known_ranked": bool(row.get("known_row")),
                "seconds": row["seconds"],
            }
            print(json.dumps(json_safe(msg), sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
