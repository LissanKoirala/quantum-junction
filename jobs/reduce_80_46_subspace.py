#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import csv
import itertools
import json
import math
from pathlib import Path
from typing import Any


N = 80


def qiskit_to_logical(bits: str) -> list[int]:
    bits = bits.strip().replace(" ", "")
    if len(bits) != N:
        raise ValueError(f"expected {N}-bit string, got {len(bits)} bits: {bits}")
    return [int(b) for b in reversed(bits)]


def logical_to_qiskit(bits: list[int]) -> str:
    if len(bits) != N:
        raise ValueError(f"expected {N} logical bits, got {len(bits)}")
    return "".join(str(int(b)) for b in reversed(bits))


def load_counts(path: Path) -> collections.Counter[str]:
    if path.suffix.lower() in {".json", ".jsonl"}:
        text = path.read_text().strip()
        if not text:
            return collections.Counter()
        if path.suffix.lower() == ".jsonl":
            counts: collections.Counter[str] = collections.Counter()
            for line in text.splitlines():
                row = json.loads(line)
                counts[str(row["bitstring"])] += int(row.get("count", 1))
            return counts
        data = json.loads(text)
        if isinstance(data, dict) and "counts" in data:
            data = data["counts"]
        if isinstance(data, dict):
            return collections.Counter({str(k): int(v) for k, v in data.items()})
        if isinstance(data, list):
            counts = collections.Counter()
            for row in data:
                if isinstance(row, str):
                    counts[row] += 1
                else:
                    counts[str(row["bitstring"])] += int(row.get("count", 1))
            return counts
    counts: collections.Counter[str] = collections.Counter()
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            bitstring = row.get("bitstring") or row.get("bits") or row.get("sample")
            count = row.get("count") or row.get("counts") or 1
            if bitstring:
                counts[str(bitstring)] += int(count)
    return counts


def add_counts_source(
    sources: list[dict[str, Any]],
    name: str,
    counts: collections.Counter[str],
    weight: float,
) -> None:
    total = sum(counts.values())
    if total <= 0:
        return
    p1 = [0.0] * N
    for bitstring, count in counts.items():
        logical = qiskit_to_logical(bitstring)
        for q, bit in enumerate(logical):
            p1[q] += weight * count * bit / total
    sources.append(
        {
            "name": name,
            "kind": "counts",
            "weight": weight,
            "p1": p1,
            "counts": counts,
            "total": total,
        }
    )


def add_json_sources(root: Path, sources: list[dict[str, Any]], weight: float) -> collections.Counter[str]:
    aggregate_counts: collections.Counter[str] = collections.Counter()
    for path in sorted(root.glob("*/json/*.json")):
        data = json.loads(path.read_text())
        label = path.parts[-3]
        marginal = data.get("marginal") or {}
        p0s = marginal.get("p0s_raw_site_order")
        permuted = (marginal.get("variants") or {}).get("permuted_measurement_order_reversed")
        if p0s and permuted and len(p0s) == N:
            # The MPO runner's preferred candidate variant is already Qiskit order.
            # Its p0s are raw site order; use the candidate for sign, and p0s only
            # for confidence magnitudes if no better permutation-specific p1 exists.
            cand_logical = qiskit_to_logical(permuted)
            p1 = []
            for p0, bit in zip(p0s, cand_logical):
                conf = abs(float(p0) - 0.5)
                p1.append((0.5 + conf) if bit else (0.5 - conf))
            sources.append({"name": f"{label}:marginal", "kind": "marginal", "weight": weight, "p1": p1})

        sampling = data.get("sampling") or {}
        sample_counts = sampling.get("counts_qiskit_order") or sampling.get("top_counts_qiskit_order")
        if isinstance(sample_counts, dict):
            counts = collections.Counter({str(k): int(v) for k, v in sample_counts.items()})
            aggregate_counts.update(counts)
            add_counts_source(sources, f"{label}:samples", counts, weight)
        elif isinstance(sampling.get("top"), list):
            counts = collections.Counter()
            for row in sampling["top"]:
                bits = row.get("permuted_measurement_order_reversed")
                if not bits and row.get("permuted_measurement_order"):
                    bits = str(row["permuted_measurement_order"])[::-1]
                if bits:
                    counts[str(bits)] += int(row.get("count", 1))
            aggregate_counts.update(counts)
            add_counts_source(sources, f"{label}:sample_top", counts, weight)
        top = data.get("final_candidate_qiskit_order")
        if top and len(top) == N:
            aggregate_counts[top] += 1
    return aggregate_counts


def combine_p1(sources: list[dict[str, Any]]) -> tuple[list[float], list[int]]:
    weighted = [0.0] * N
    denom = [0.0] * N
    votes = [0] * N
    for src in sources:
        p1 = src["p1"]
        weight = float(src.get("weight", 1.0))
        for q, p in enumerate(p1):
            if p is None or math.isnan(float(p)):
                continue
            weighted[q] += weight * float(p)
            denom[q] += weight
            votes[q] += 1
    out = [weighted[q] / denom[q] if denom[q] else 0.5 for q in range(N)]
    return out, votes


def hamming(a: str, b: str) -> int:
    return sum(x != y for x, y in zip(a, b))


def neighborhood_score(candidate: str, counts: collections.Counter[str], radius: int) -> float:
    score = 0.0
    for bitstring, count in counts.items():
        d = hamming(candidate, bitstring)
        if d <= radius:
            score += count / (1 + d)
    return score


def enumerate_candidates(base_logical: list[int], uncertain: list[int], max_enum: int) -> list[str]:
    if len(uncertain) > max_enum:
        return [logical_to_qiskit(base_logical)]
    out = []
    for values in itertools.product([0, 1], repeat=len(uncertain)):
        bits = list(base_logical)
        for q, value in zip(uncertain, values):
            bits[q] = value
        out.append(logical_to_qiskit(bits))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep-root", type=Path, default=Path("outputs/tree_tensor_sim/solve_80_46_centers"))
    parser.add_argument("--qpu-counts", type=Path, action="append", default=[])
    parser.add_argument("--freeze-threshold", type=float, default=0.85)
    parser.add_argument("--min-source-votes", type=int, default=2)
    parser.add_argument("--max-enumerate-uncertain", type=int, default=24)
    parser.add_argument("--hamming-radius", type=int, default=2)
    parser.add_argument("--out", type=Path, default=Path("outputs/tree_tensor_sim/solve_80_46_centers/SUBSPACE.md"))
    args = parser.parse_args()

    sources: list[dict[str, Any]] = []
    aggregate_counts = add_json_sources(args.sweep_root, sources, weight=1.0)
    for path in args.qpu_counts:
        counts = load_counts(path)
        aggregate_counts.update(counts)
        add_counts_source(sources, f"qpu:{path.name}", counts, weight=2.0)

    p1, source_votes = combine_p1(sources)
    base_logical = [1 if p >= 0.5 else 0 for p in p1]
    fixed: dict[int, int] = {}
    uncertain = []
    for q, p in enumerate(p1):
        confident = p >= args.freeze_threshold or p <= (1.0 - args.freeze_threshold)
        if confident and source_votes[q] >= args.min_source_votes:
            fixed[q] = 1 if p >= 0.5 else 0
        else:
            uncertain.append(q)

    candidates = enumerate_candidates(base_logical, uncertain, args.max_enumerate_uncertain)
    ranked = sorted(
        (
            {
                "candidate": cand,
                "score": neighborhood_score(cand, aggregate_counts, args.hamming_radius),
                "exact_count": aggregate_counts.get(cand, 0),
            }
            for cand in candidates
        ),
        key=lambda row: (-row["score"], -row["exact_count"], row["candidate"]),
    )

    lines = [
        "# 80_46 Subspace Reduction",
        "",
        f"Sources: {len(sources)}",
        f"Fixed bits: {len(fixed)}",
        f"Uncertain bits: {len(uncertain)}",
        f"Reduced search size: 2^{len(uncertain)}",
        "",
        "Bit order note: q0 is the right-most bit in submitted Qiskit-order strings.",
        "",
        "## Fixed Bits",
        "",
        "| qubit | fixed bit | Pr(1) | source votes |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for q in sorted(fixed):
        lines.append(f"| {q} | {fixed[q]} | {p1[q]:.6f} | {source_votes[q]} |")
    lines.extend(["", "## Uncertain Qubits", "", "`" + ",".join(map(str, uncertain)) + "`", ""])
    lines.extend(["## Top Reduced-Subspace Candidates", "", "| rank | candidate | neighborhood score | exact count |", "| ---: | --- | ---: | ---: |"])
    for i, row in enumerate(ranked[:50], 1):
        lines.append(f"| {i} | `{row['candidate']}` | {row['score']:.6g} | {row['exact_count']} |")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n")
    counts_path = args.out.with_name("SUBSPACE_COUNTS.csv")
    with counts_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["bitstring", "count", "neighborhood_score", "rank"])
        writer.writeheader()
        for rank, row in enumerate(ranked[:500], 1):
            writer.writerow(
                {
                    "bitstring": row["candidate"],
                    "count": row["exact_count"],
                    "neighborhood_score": row["score"],
                    "rank": rank,
                }
            )
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
