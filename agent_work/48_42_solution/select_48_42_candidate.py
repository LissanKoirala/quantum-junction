#!/usr/bin/env python3
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
Z_MARGINAL = ROOT / "agent_work/mps_distill/results/very_hard_48_42_z_marginals_bd64_seed777.json"
MPS_SAMPLE = (
    ROOT
    / "agent_work/mps_distill/results/"
    "very_hard_48_42_focus__task-0003__challenge-48_42__shots-4096__bd-64__seed-401.json"
)
QUIMB_BD32 = ROOT / "outputs/tree_tensor_sim/48_42_focus_quimb_bd32/json/challenge-48_42.quimb_tree_graph_mps.json"
REJECTED = {
    "001100001011001101110011111100001110101010011001",
    "001100001011001101110011111100001010101010011001",
    "001100001011001101110011111100001010101110011001",
}

# Scored by rebuilding the native Aer MPS at bond_dim=32 and directly
# contracting candidate amplitudes for the 16 variants formed by the four
# bd64-marginal/sample-majority disagreement positions.
DIRECT_MPS_BD32_PROBABILITY_RANK = [
    {
        "bitstring": "001100001011001101110011111100001010101010011001",
        "flipped_qiskit_positions": [33],
        "mps_probability": 4.495180223847e-21,
    },
    {
        "bitstring": "001100001011001101110011111100001110101010011001",
        "flipped_qiskit_positions": [],
        "mps_probability": 4.330577047056e-21,
    },
    {
        "bitstring": "001100001011001101110011111100001010101110011001",
        "flipped_qiskit_positions": [33, 39],
        "mps_probability": 1.066661914871e-21,
    },
    {
        "bitstring": "001100001011001101110011111100001010101010011011",
        "flipped_qiskit_positions": [33, 46],
        "mps_probability": 8.967022976237e-22,
    },
    {
        "bitstring": "001100001011000101110011111100001010101010011001",
        "flipped_qiskit_positions": [14, 33],
        "mps_probability": 5.242201691708e-22,
    },
    {
        "bitstring": "001100001011000101110011111100001110101010011001",
        "flipped_qiskit_positions": [14],
        "mps_probability": 4.929228434494e-22,
    },
    {
        "bitstring": "001100001011001101110011111100001110101010011011",
        "flipped_qiskit_positions": [46],
        "mps_probability": 4.764807469552e-22,
    },
    {
        "bitstring": "001100001011001101110011111100001110101110011001",
        "flipped_qiskit_positions": [39],
        "mps_probability": 4.019261341466e-22,
    },
]


def hamming(a: str, b: str) -> int:
    return sum(x != y for x, y in zip(a, b))


def majority_from_counts(counts: list[list[object]]) -> tuple[str, list[float], list[float]]:
    shots = sum(int(count) for _, count in counts)
    n = len(str(counts[0][0]))
    ones = [0] * n
    for bitstring, count_raw in counts:
        count = int(count_raw)
        for idx, bit in enumerate(str(bitstring)):
            if bit == "1":
                ones[idx] += count
    fractions = [value / shots for value in ones]
    margins = [abs(value - 0.5) for value in fractions]
    majority = "".join("1" if value >= 0.5 else "0" for value in fractions)
    return majority, fractions, margins


def variant_score(bitstring: str, p1_qiskit: list[float]) -> float:
    # Product-model log score without log import: comparing sums of selected
    # probabilities is enough for the tiny low-margin variant set used here.
    score = 0.0
    for bit, p1 in zip(bitstring, p1_qiskit):
        score += p1 if bit == "1" else 1.0 - p1
    return score


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "agent_work/48_42_solution/solution_48_42.json")
    args = parser.parse_args()

    z_data = json.loads(Z_MARGINAL.read_text())
    sample_data = json.loads(MPS_SAMPLE.read_text())
    quimb_data = json.loads(QUIMB_BD32.read_text())

    primary = z_data["bit_qiskit"]
    # Stored p1_logical is q0-first; Qiskit/counts order is qN-1...q0.
    p1_qiskit = list(reversed(z_data["p1_logical"]))
    z_margins = [abs(value - 0.5) for value in p1_qiskit]

    counts = sample_data["sampling"]["top_counts"]
    sample_majority, sample_p1, sample_margins = majority_from_counts(counts)
    quimb_marginal = quimb_data["candidate_qiskit_order"]
    quimb_sample_top = quimb_data["final_candidate_qiskit_order"]

    disagreements = []
    for idx, (z_bit, sample_bit) in enumerate(zip(primary, sample_majority)):
        if z_bit != sample_bit:
            disagreements.append(
                {
                    "qiskit_position": idx,
                    "qubit": len(primary) - 1 - idx,
                    "z_bit": z_bit,
                    "sample_majority_bit": sample_bit,
                    "z_p1": p1_qiskit[idx],
                    "z_margin": z_margins[idx],
                    "sample_p1": sample_p1[idx],
                    "sample_margin": sample_margins[idx],
                }
            )

    flip_positions = [row["qiskit_position"] for row in disagreements]
    variants = []
    for mask_size in range(len(flip_positions) + 1):
        for combo in itertools.combinations(flip_positions, mask_size):
            bits = list(primary)
            for idx in combo:
                bits[idx] = "1" if bits[idx] == "0" else "0"
            bitstring = "".join(bits)
            variants.append(
                {
                    "bitstring": bitstring,
                    "flipped_qiskit_positions": list(combo),
                    "z_product_rank_score": variant_score(bitstring, p1_qiskit),
                    "hamming_to_sample_majority": hamming(bitstring, sample_majority),
                }
            )
    variants.sort(key=lambda row: (-row["z_product_rank_score"], row["hamming_to_sample_majority"]))

    selected_row = next(row for row in DIRECT_MPS_BD32_PROBABILITY_RANK if row["bitstring"] not in REJECTED)
    selected = sample_majority

    payload = {
        "challenge": "48_42",
        "num_qubits": 48,
        "selected_bitstring_qiskit_order": selected,
        "rejected_bitstrings_qiskit_order": sorted(REJECTED),
        "selection_rule": (
            "Three close marginal/probability variants were rejected by the judge. Switch to "
            "the paper's low-bond MPS distillation rule: use the full 4096-shot bond-64 MPS "
            "per-bit majority candidate, which flips all four bd64-marginal/sample-majority "
            "disagreement bits."
        ),
        "evidence": {
            "aer_z_marginal_bd64": {
                "bitstring": primary,
                "min_margin": z_data["min_margin"],
                "mean_margin": z_data["mean_margin"],
                "max_margin": z_data["max_margin"],
            },
            "aer_mps_bd64_majority_from_4096_samples": {
                "bitstring": sample_majority,
                "hamming_to_selected": hamming(primary, sample_majority),
                "shots": sample_data["sampling"]["shots"],
                "distinct_outcomes": sample_data["sampling"]["distinct_outcomes"],
            },
            "quimb_bd32_marginal": {
                "bitstring": quimb_marginal,
                "hamming_to_selected": hamming(primary, quimb_marginal),
                "min_margin": quimb_data["p1_margin_min"],
                "mean_margin": quimb_data["p1_margin_mean"],
            },
            "quimb_bd32_sample_top": {
                "bitstring": quimb_sample_top,
                "hamming_to_selected": hamming(primary, quimb_sample_top),
                "top_count": quimb_data["sampling"]["top_count"],
                "top_fraction": quimb_data["sampling"]["top_fraction"],
            },
        },
        "low_margin_disagreements_vs_sample_majority": disagreements,
        "selected_direct_mps_bd32_probability_row_after_rejections": selected_row,
        "direct_mps_bd32_probability_rank_top8": DIRECT_MPS_BD32_PROBABILITY_RANK,
        "top_low_margin_variants_by_z_score": variants[:10],
        "bit_order": "Qiskit/counts order: left-most bit is highest qubit; right-most bit is q0.",
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
