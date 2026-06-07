#!/usr/bin/env python3
"""Rank peaked-circuit cracking methods from static QASM features.

The tool is intentionally dependency-free. It does not run the expensive
Kremer/Dupuis simulations; instead it decides which of the three methods is
most plausible for a circuit and explains the evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Iterable


ONE_QUBIT_GATES = {"rx", "rz", "x", "y", "z", "h", "sx", "sxdg", "u", "u1", "u2", "u3"}
ENTANGLING_GATES = {"cx", "cz", "swap", "iswap", "ecr", "rxx", "ryy", "rzz"}
IGNORED_STATEMENTS = {
    "openqasm",
    "include",
    "qreg",
    "creg",
    "qubit",
    "bit",
    "barrier",
    "reset",
}

GATE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(?:\((.*?)\))?\s+(.+);$")
QREG_RE = re.compile(r"\bqreg\s+([A-Za-z_][A-Za-z0-9_]*)\[(\d+)\]\s*;")
QUBIT_RE = re.compile(r"\bqubit\[(\d+)\]\s+([A-Za-z_][A-Za-z0-9_]*)\s*;")
QUBIT_ARG_RE = re.compile(r"\[[ \t]*(\d+)[ \t]*\]")


@dataclass(frozen=True)
class Operation:
    gate: str
    qubits: tuple[int, ...]
    angle: float | None
    raw_angle: str | None
    line_no: int


@dataclass
class CircuitFeatures:
    path: str
    difficulty_group: str
    num_qubits: int
    total_ops: int
    one_qubit_ops: int
    entangling_ops: int
    measurements: int
    gate_counts: dict[str, int]
    approx_depth: int
    first_entangler_at: int | None
    leading_one_qubit_ops: int
    trailing_one_qubit_ops: int
    unique_entangling_pairs: int
    graph_density: float
    connected_components: int
    max_pair_repetition: int
    repeated_pair_count: int
    swap_count: int
    rx_count: int
    rz_count: int
    angle_count: int
    rx_pi_like_count: int
    rx_zero_like_count: int
    fraction_grid_angle_frac: float
    noisy_angle_frac: float
    estimated_band: str


@dataclass
class MethodScore:
    method_id: str
    name: str
    score: int
    fit: str
    reasons: list[str]
    caveats: list[str]
    next_steps: list[str]


@dataclass
class Recommendation:
    path: str
    features: CircuitFeatures
    exact_baseline: dict[str, str]
    methods: list[MethodScore]
    best_method_id: str
    best_method_name: str


def strip_comment(line: str) -> str:
    return line.split("//", 1)[0].strip()


def safe_angle_eval(expr: str | None) -> float | None:
    if expr is None:
        return None
    clean = expr.strip().replace("^", "**")
    if not clean:
        return None
    if not re.fullmatch(r"[0-9eEpiPI+\-*/(). \t]+", clean):
        return None
    try:
        value = eval(clean, {"__builtins__": {}}, {"pi": math.pi, "PI": math.pi})
    except Exception:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def angle_distance_to_pi_grid(angle: float, max_denominator: int = 16) -> float:
    if not math.isfinite(angle) or math.pi == 0:
        return math.inf
    ratio = angle / math.pi
    nearest = Fraction(ratio).limit_denominator(max_denominator)
    return abs(ratio - float(nearest))


def is_near_zero_rotation(angle: float, tol: float = 1e-6) -> bool:
    return min(abs(angle), abs((angle % (2 * math.pi)))) <= tol


def is_near_pi_rotation(angle: float, tol: float = 1e-6) -> bool:
    wrapped = (angle + math.pi) % (2 * math.pi) - math.pi
    return abs(abs(wrapped) - math.pi) <= tol or abs(abs(angle / math.pi) - 1.0) <= tol


def parse_qasm(path: Path) -> tuple[int, list[Operation]]:
    text = path.read_text(encoding="utf-8")
    num_qubits = 0
    operations: list[Operation] = []

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = strip_comment(raw_line)
        if not line:
            continue

        qreg_match = QREG_RE.search(line)
        if qreg_match:
            num_qubits = max(num_qubits, int(qreg_match.group(2)))
            continue

        qubit_match = QUBIT_RE.search(line)
        if qubit_match:
            num_qubits = max(num_qubits, int(qubit_match.group(1)))
            continue

        first_word = line.split(None, 1)[0].lower().rstrip(";")
        if first_word in IGNORED_STATEMENTS:
            continue

        if line.startswith("measure "):
            qubits = tuple(int(q) for q in QUBIT_ARG_RE.findall(line))
            operations.append(Operation("measure", qubits[:1], None, None, line_no))
            continue

        match = GATE_RE.match(line)
        if not match:
            continue

        gate = match.group(1).lower()
        raw_angle = match.group(2)
        args = match.group(3)
        qubits = tuple(int(q) for q in QUBIT_ARG_RE.findall(args))
        if qubits:
            num_qubits = max(num_qubits, max(qubits) + 1)
        operations.append(Operation(gate, qubits, safe_angle_eval(raw_angle), raw_angle, line_no))

    if num_qubits <= 0:
        raise ValueError(f"Could not determine qubit count for {path}")
    return num_qubits, operations


def approx_depth(ops: Iterable[Operation], num_qubits: int) -> int:
    depths = [0] * num_qubits
    for op in ops:
        if not op.qubits:
            continue
        layer = max(depths[q] for q in op.qubits) + 1
        for q in op.qubits:
            depths[q] = layer
    return max(depths, default=0)


def connected_components(num_qubits: int, pairs: Iterable[tuple[int, int]]) -> int:
    parent = list(range(num_qubits))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b in pairs:
        union(a, b)
    return len({find(i) for i in range(num_qubits)})


def estimate_band(num_qubits: int, total_ops: int, density: float, leading_1q: int) -> str:
    if num_qubits <= 28 and total_ops < 2500:
        return "exact-friendly"
    if total_ops < 2500 and density < 0.45:
        return "light or moderate"
    if total_ops < 8000 and density < 0.65:
        return "simulation-heavy"
    if leading_1q >= num_qubits and density >= 0.55:
        return "obfuscation-heavy"
    return "hard or very-hard"


def infer_difficulty_group(path: Path) -> str:
    for part in path.parts:
        normalized = part.lower().replace("-", "_").replace(" ", "_")
        if normalized in {"very_easy", "easy", "moderate", "hard", "very_hard"}:
            return normalized
    return "unknown"


def analyze_qasm(path: Path) -> CircuitFeatures:
    num_qubits, operations = parse_qasm(path)
    gate_counts = Counter(op.gate for op in operations)
    total_ops = sum(1 for op in operations if op.gate != "measure")
    one_qubit_ops = sum(1 for op in operations if len(op.qubits) == 1 and op.gate != "measure")
    entangling_ops = sum(1 for op in operations if op.gate in ENTANGLING_GATES and len(op.qubits) >= 2)
    measurements = gate_counts.get("measure", 0)

    first_entangler_at = None
    leading_one_qubit_ops = 0
    for idx, op in enumerate(operations):
        if op.gate == "measure":
            continue
        if op.gate in ENTANGLING_GATES and len(op.qubits) >= 2:
            first_entangler_at = idx
            break
        if len(op.qubits) == 1:
            leading_one_qubit_ops += 1
        else:
            break

    trailing_one_qubit_ops = 0
    for op in reversed(operations):
        if op.gate == "measure":
            continue
        if len(op.qubits) == 1:
            trailing_one_qubit_ops += 1
        else:
            break

    pair_counts: Counter[tuple[int, int]] = Counter()
    for op in operations:
        if op.gate in ENTANGLING_GATES and len(op.qubits) >= 2:
            pair = tuple(sorted(op.qubits[:2]))
            pair_counts[pair] += 1

    unique_pairs = len(pair_counts)
    possible_pairs = max(num_qubits * (num_qubits - 1) // 2, 1)
    graph_density = unique_pairs / possible_pairs
    max_pair_repetition = max(pair_counts.values(), default=0)
    repeated_pair_count = sum(1 for count in pair_counts.values() if count > 1)

    rx_angles = [op.angle for op in operations if op.gate == "rx" and op.angle is not None]
    all_angles = [op.angle for op in operations if op.angle is not None]
    grid_close = [a for a in all_angles if angle_distance_to_pi_grid(a) <= 1e-2]

    features = CircuitFeatures(
        path=str(path),
        difficulty_group=infer_difficulty_group(path),
        num_qubits=num_qubits,
        total_ops=total_ops,
        one_qubit_ops=one_qubit_ops,
        entangling_ops=entangling_ops,
        measurements=measurements,
        gate_counts=dict(sorted(gate_counts.items())),
        approx_depth=approx_depth((op for op in operations if op.gate != "measure"), num_qubits),
        first_entangler_at=first_entangler_at,
        leading_one_qubit_ops=leading_one_qubit_ops,
        trailing_one_qubit_ops=trailing_one_qubit_ops,
        unique_entangling_pairs=unique_pairs,
        graph_density=round(graph_density, 4),
        connected_components=connected_components(num_qubits, pair_counts.keys()),
        max_pair_repetition=max_pair_repetition,
        repeated_pair_count=repeated_pair_count,
        swap_count=gate_counts.get("swap", 0),
        rx_count=gate_counts.get("rx", 0),
        rz_count=gate_counts.get("rz", 0),
        angle_count=len(all_angles),
        rx_pi_like_count=sum(1 for a in rx_angles if is_near_pi_rotation(a)),
        rx_zero_like_count=sum(1 for a in rx_angles if is_near_zero_rotation(a)),
        fraction_grid_angle_frac=round(len(grid_close) / len(all_angles), 4) if all_angles else 0.0,
        noisy_angle_frac=round(1.0 - (len(grid_close) / len(all_angles)), 4) if all_angles else 0.0,
        estimated_band=estimate_band(num_qubits, total_ops, graph_density, leading_one_qubit_ops),
    )
    return features


def clamp_score(score: float) -> int:
    return int(max(0, min(100, round(score))))


def fit_label(score: int) -> str:
    if score >= 75:
        return "strong"
    if score >= 55:
        return "usable"
    if score >= 35:
        return "weak"
    return "poor"


def score_low_bond_mps(f: CircuitFeatures) -> MethodScore:
    score = 35.0
    reasons: list[str] = []
    caveats: list[str] = []

    if f.num_qubits <= 64:
        score += 15
        reasons.append(f"{f.num_qubits} qubits is inside the practical range for MPS trials.")
    else:
        score -= 10
        caveats.append(f"{f.num_qubits} qubits may still be possible, but shot-based MPS gets expensive.")

    if f.total_ops <= 6000:
        score += 18
        reasons.append(f"{f.total_ops} operations is a reasonable first-pass simulation size.")
    else:
        score -= 18
        caveats.append(f"{f.total_ops} operations makes repeated MPS shots slow.")

    if f.graph_density <= 0.45:
        score += 14
        reasons.append("The entangling graph is not too dense, so low bond dimensions are more plausible.")
    else:
        score -= 14
        caveats.append("Dense entangling connectivity can inflate MPS bond dimension.")

    if f.estimated_band in {"exact-friendly", "light or moderate", "simulation-heavy"}:
        score += 8
        reasons.append(f"The static size band is {f.estimated_band}, so a heuristic sampler is worth trying.")

    if f.difficulty_group == "hard":
        score -= 18
        caveats.append("The problem is labeled hard, so MPS should be treated as a candidate generator.")
    elif f.difficulty_group == "very_hard":
        score -= 35
        caveats.append("The problem is labeled very-hard; low-bond MPS is unlikely to resolve the peak by itself.")

    if f.swap_count > 0:
        score -= 4
        caveats.append(f"{f.swap_count} explicit swaps can scramble bit positions; track bit order carefully.")

    if f.num_qubits <= 28:
        score -= 10
        caveats.append("Exact statevector is simpler for this size; use MPS only as a cross-check.")

    final = clamp_score(score)
    return MethodScore(
        method_id="low_bond_mps_distillation",
        name="Low-bond MPS with bitstring distillation",
        score=final,
        fit=fit_label(final),
        reasons=reasons,
        caveats=caveats,
        next_steps=[
            "Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.",
            "Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.",
            "Increase shots before increasing bond dimension when top candidates are unstable.",
        ],
    )


def score_tno(f: CircuitFeatures) -> MethodScore:
    score = 30.0
    reasons: list[str] = []
    caveats: list[str] = []

    if f.swap_count == 0:
        score += 15
        reasons.append("No explicit swaps were found, matching the cleaner TNO target case.")
    elif f.swap_count <= max(2, f.num_qubits // 8):
        score += 4
        caveats.append(f"{f.swap_count} swaps is low, but still weakens the no-permutation assumption.")
    else:
        score -= 15
        caveats.append(f"{f.swap_count} swaps suggest permutation structure that TNO alone may not control.")

    if f.graph_density <= 0.35:
        score += 22
        reasons.append("Sparse or structured entangling connectivity favors midpoint TNO contraction.")
    elif f.graph_density <= 0.55:
        score += 6
        reasons.append("Moderate graph density keeps TNO plausible if bond growth stays bounded.")
    else:
        score -= 20
        caveats.append("Dense all-to-all-like connectivity is a bad sign for plain TNO contraction.")

    if f.repeated_pair_count > 0:
        score += min(18, 4 + f.max_pair_repetition)
        reasons.append(
            f"Repeated two-qubit pairs exist; max repetition is {f.max_pair_repetition}, which can indicate inverse blocks."
        )

    if f.leading_one_qubit_ops >= f.num_qubits:
        score -= 10
        caveats.append("A full-width leading one-qubit dressing layer looks like heavier obfuscation.")

    if f.total_ops > 10000:
        score -= 12
        caveats.append("The circuit is large enough that TNO compression needs careful cutoff/bond tuning.")

    if f.difficulty_group == "hard" and f.swap_count <= 2 and f.graph_density <= 0.55:
        score += 8
        reasons.append("The file is hard but does not show strong explicit permutation evidence.")
    elif f.difficulty_group == "very_hard":
        score -= 10
        caveats.append("Very-hard instances usually need permutation-aware cancellation, not plain TNO alone.")

    final = clamp_score(score)
    return MethodScore(
        method_id="tno_contraction",
        name="Tensor Network Operator midpoint contraction",
        score=final,
        fit=fit_label(final),
        reasons=reasons,
        caveats=caveats,
        next_steps=[
            "Layer the circuit and absorb gates from the temporal midpoint outward.",
            "Track max bond and total tensor elements after each chunk.",
            "Abandon this path if bond dimension grows before many layers are absorbed.",
        ],
    )


def score_mpo_unswapping(f: CircuitFeatures) -> MethodScore:
    score = 25.0
    reasons: list[str] = []
    caveats: list[str] = []

    if f.num_qubits > 28:
        score += 10
        reasons.append("Exact statevector is not a safe default, so a structure-aware method is needed.")
    else:
        score -= 18
        caveats.append("This is small enough that MPO unswapping is likely overkill.")

    if f.total_ops >= 5000:
        score += 18
        reasons.append(f"{f.total_ops} operations is large enough to justify cancellation plus unswapping.")
    elif f.total_ops < 1500:
        score -= 12
        caveats.append("The circuit is small enough that simpler simulation should come first.")

    if f.graph_density >= 0.55:
        score += 24
        reasons.append("Dense entangling connectivity suggests hidden permutation/ordering trouble.")
    elif f.graph_density >= 0.35:
        score += 10
        reasons.append("Moderate-to-dense connectivity could still benefit from adaptive rewiring.")

    if f.leading_one_qubit_ops >= f.num_qubits:
        score += 14
        reasons.append("A full-width leading one-qubit prefix is a strong obfuscation signal.")

    if f.swap_count == 0 and f.graph_density >= 0.55:
        score += 10
        reasons.append("Dense connectivity without explicit swaps can mean the permutation is hidden in rewrites.")
    elif f.swap_count > 0:
        score += 4
        reasons.append(f"{f.swap_count} explicit swaps give the unswapping path concrete permutation evidence.")

    if f.repeated_pair_count > f.num_qubits:
        score += 8
        reasons.append("Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.")

    if f.difficulty_group == "hard" and f.total_ops >= 2500 and f.graph_density >= 0.35:
        score += 12
        reasons.append("The hard label plus size/density makes a structural deobfuscation path worth prioritizing.")
    elif f.difficulty_group == "very_hard":
        score += 20
        reasons.append("The very-hard label is a strong prior for MPO unswapping or a similar global method.")

    final = clamp_score(score)
    return MethodScore(
        method_id="mpo_unswapping",
        name="MPO iterative cancellation with unswapping",
        score=final,
        fit=fit_label(final),
        reasons=reasons,
        caveats=caveats,
        next_steps=[
            "Split the circuit near the midpoint and absorb left/right layers into a central MPO.",
            "When bond growth spikes, greedily test nearest-neighbor swaps and keep swaps that reduce MPO size.",
            "Use the resulting MPO/MPS to sample or extract per-qubit marginals for candidate bitstrings.",
        ],
    )


def exact_baseline_advice(f: CircuitFeatures) -> dict[str, str]:
    if f.num_qubits <= 24:
        return {
            "status": "recommended",
            "reason": "Exact statevector should be the first solve and the verification baseline.",
        }
    if f.num_qubits <= 28:
        return {
            "status": "possible",
            "reason": "Exact statevector is memory-heavy but still plausible on a strong machine.",
        }
    return {
        "status": "not-first-choice",
        "reason": "Statevector memory scales as 2^n, so use it only for reduced circuits or validation.",
    }


def recommend(path: Path) -> Recommendation:
    features = analyze_qasm(path)
    methods = [
        score_low_bond_mps(features),
        score_tno(features),
        score_mpo_unswapping(features),
    ]
    methods.sort(key=lambda m: m.score, reverse=True)
    return Recommendation(
        path=str(path),
        features=features,
        exact_baseline=exact_baseline_advice(features),
        methods=methods,
        best_method_id=methods[0].method_id,
        best_method_name=methods[0].name,
    )


def discover_qasm(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix.lower() == ".qasm":
            found.append(path)
        elif path.is_dir():
            found.extend(sorted(path.rglob("*.qasm")))
    return sorted(dict.fromkeys(found))


def recommendation_to_dict(rec: Recommendation) -> dict:
    return {
        "path": rec.path,
        "features": asdict(rec.features),
        "exact_baseline": rec.exact_baseline,
        "first_action": first_action(rec),
        "best_method_id": rec.best_method_id,
        "best_method_name": rec.best_method_name,
        "methods": [asdict(method) for method in rec.methods],
    }


def first_action(rec: Recommendation) -> str:
    status = rec.exact_baseline["status"]
    if status == "recommended":
        return "Exact statevector baseline"
    if status == "possible":
        return "Exact if memory allows, then compare paper methods"
    return rec.best_method_name


def render_markdown(recs: list[Recommendation], detail_limit: int | None = None) -> str:
    lines = [
        "# Quantum Peak Method Recommendations",
        "",
        "This report ranks the three Kremer/Dupuis peaked-circuit methods from static QASM features.",
        "Scores are triage signals, not correctness guarantees.",
        "",
        "| circuit | group | q | ops | entanglers | density | swaps | exact baseline | first action | best paper method | score |",
        "|---|---|---:|---:|---:|---:|---:|---|---|---|---:|",
    ]

    for rec in recs:
        f = rec.features
        best = rec.methods[0]
        circuit = Path(rec.path).name
        lines.append(
            f"| `{circuit}` | {f.difficulty_group} | {f.num_qubits} | {f.total_ops} | {f.entangling_ops} | "
            f"{f.graph_density:.4f} | {f.swap_count} | {rec.exact_baseline['status']} | "
            f"{first_action(rec)} | {best.name} | {best.score} |"
        )

    limit = len(recs) if detail_limit is None else min(detail_limit, len(recs))
    if limit:
        lines.extend(["", "## Details", ""])

    for rec in recs[:limit]:
        f = rec.features
        lines.extend(
            [
                f"### {Path(rec.path).name}",
                "",
                f"- Static band: `{f.estimated_band}`",
                f"- Difficulty group: `{f.difficulty_group}`",
                f"- Features: q={f.num_qubits}, ops={f.total_ops}, depth~{f.approx_depth}, "
                f"entanglers={f.entangling_ops}, density={f.graph_density:.4f}, swaps={f.swap_count}",
                f"- Exact baseline: `{rec.exact_baseline['status']}` because {rec.exact_baseline['reason']}",
                f"- First action: {first_action(rec)}",
                "",
            ]
        )
        top = rec.methods[0]
        lines.append(f"Suggested next steps for `{top.method_id}`:")
        lines.append("")
        for step in top.next_steps:
            lines.append(f"- {step}")
        lines.append("")
        for method in rec.methods:
            lines.append(f"**{method.name}**: {method.fit} fit, score {method.score}/100")
            if method.reasons:
                lines.append("")
                for reason in method.reasons[:4]:
                    lines.append(f"- {reason}")
            if method.caveats:
                lines.append("")
                for caveat in method.caveats[:3]:
                    lines.append(f"- Caveat: {caveat}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_csv(recs: list[Recommendation], fp) -> None:
    writer = csv.DictWriter(
        fp,
        lineterminator="\n",
        fieldnames=[
            "path",
            "difficulty_group",
            "num_qubits",
            "total_ops",
            "entangling_ops",
            "graph_density",
            "swap_count",
            "leading_one_qubit_ops",
            "estimated_band",
            "exact_baseline",
            "first_action",
            "best_method_id",
            "best_method_name",
            "best_score",
            "mps_score",
            "tno_score",
            "mpo_unswapping_score",
        ],
    )
    writer.writeheader()
    for rec in recs:
        scores = {method.method_id: method.score for method in rec.methods}
        f = rec.features
        writer.writerow(
            {
                "path": rec.path,
                "difficulty_group": f.difficulty_group,
                "num_qubits": f.num_qubits,
                "total_ops": f.total_ops,
                "entangling_ops": f.entangling_ops,
                "graph_density": f.graph_density,
                "swap_count": f.swap_count,
                "leading_one_qubit_ops": f.leading_one_qubit_ops,
                "estimated_band": f.estimated_band,
                "exact_baseline": rec.exact_baseline["status"],
                "first_action": first_action(rec),
                "best_method_id": rec.best_method_id,
                "best_method_name": rec.best_method_name,
                "best_score": rec.methods[0].score,
                "mps_score": scores.get("low_bond_mps_distillation", ""),
                "tno_score": scores.get("tno_contraction", ""),
                "mpo_unswapping_score": scores.get("mpo_unswapping", ""),
            }
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recommend a peaked-circuit cracking method for QASM files."
    )
    parser.add_argument("paths", nargs="+", type=Path, help="QASM file or directory to analyze")
    parser.add_argument(
        "--format",
        choices=("markdown", "json", "csv"),
        default="markdown",
        help="Output format",
    )
    parser.add_argument("--out", type=Path, help="Write output to this file")
    parser.add_argument(
        "--detail-limit",
        type=int,
        default=12,
        help="Maximum detailed circuits in markdown output; use -1 for all",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    qasm_paths = discover_qasm(args.paths)
    if not qasm_paths:
        print("No .qasm files found.", file=sys.stderr)
        return 2

    recs = [recommend(path) for path in qasm_paths]

    if args.format == "json":
        output = json.dumps([recommendation_to_dict(rec) for rec in recs], indent=2)
    elif args.format == "csv":
        if args.out:
            with args.out.open("w", encoding="utf-8", newline="") as fp:
                write_csv(recs, fp)
            return 0
        import io

        fp = io.StringIO()
        write_csv(recs, fp)
        output = fp.getvalue()
    else:
        detail_limit = None if args.detail_limit < 0 else args.detail_limit
        output = render_markdown(recs, detail_limit=detail_limit)

    if args.out:
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
