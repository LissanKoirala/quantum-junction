from __future__ import annotations

import csv
import json
import math
import re
import statistics as stats
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
CHALLENGES = ROOT / "challenges"
OUT = ROOT / "agent_work" / "static_forensics"

GATE_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9_]*)\s*(?:\(([^)]*)\))?\s+(.*);$")
Q_RE = re.compile(r"q\[(\d+)\]")
QREG_RE = re.compile(r"qreg\s+q\[(\d+)\];")
NAME_RE = re.compile(r"challenge-(\d+)_(\d+)\.qasm$")

DIFFICULTY_ORDER = {
    "very easy": 0,
    "easy": 1,
    "moderate": 2,
    "hard": 3,
    "very_hard": 4,
}


@dataclass(frozen=True)
class Gate:
    op: str
    qubits: tuple[int, ...]
    angle_expr: str | None
    angle: float | None
    line_no: int


def difficulty_key(name: str) -> tuple[int, str]:
    return (DIFFICULTY_ORDER.get(name, 99), name)


def file_key(path: Path) -> tuple[int, str, int]:
    info = parse_name(path.name)
    return (
        DIFFICULTY_ORDER.get(path.parent.name, 99),
        path.parent.name,
        info["challenge_id"],
    )


def parse_name(name: str) -> dict[str, int]:
    match = NAME_RE.match(name)
    if not match:
        return {"challenge_n": -1, "challenge_id": -1}
    return {"challenge_n": int(match.group(1)), "challenge_id": int(match.group(2))}


def safe_angle(expr: str | None) -> float | None:
    if expr is None:
        return None
    cleaned = expr.strip().replace(" ", "")
    # The challenge files only use numeric constants and simple pi fractions.
    try:
        return float(eval(cleaned, {"__builtins__": {}}, {"pi": math.pi}))
    except Exception:
        return None


def nearest_pi_fraction(value: float, max_den: int = 16) -> tuple[float, int, int, float]:
    ratio = value / math.pi
    best: tuple[float, int, int, float] | None = None
    for den in range(1, max_den + 1):
        num = round(ratio * den)
        err = abs(ratio - num / den)
        approx = num / den
        if best is None or err < best[0]:
            best = (err, num, den, approx)
    assert best is not None
    err, num, den, approx = best
    common = math.gcd(abs(num), den)
    return err, num // common, den // common, approx


def fraction_label(num: int, den: int) -> str:
    if den == 1:
        return str(num)
    return f"{num}/{den}"


def angle_bucket(value: float | None, expr: str | None) -> tuple[str, str | None, float | None]:
    if value is None:
        return ("none", None, None)
    err, num, den, _ = nearest_pi_fraction(value)
    label = fraction_label(num, den)
    if expr is not None and "pi" in expr:
        return ("symbolic_pi_expr", label, err)
    if err <= 1e-9:
        return ("numeric_exact_pi_fraction", label, err)
    if err <= 1e-6:
        return ("numeric_very_close_pi_fraction", label, err)
    if err <= 1e-4:
        return ("numeric_close_pi_fraction", label, err)
    if err <= 1e-2:
        return ("numeric_loose_pi_fraction", label, err)
    return ("numeric_noisy_non_fraction", label, err)


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "p25": None, "median": None, "p75": None, "max": None}
    values = sorted(values)
    return {
        "min": values[0],
        "p25": values[int(0.25 * (len(values) - 1))],
        "median": values[int(0.50 * (len(values) - 1))],
        "p75": values[int(0.75 * (len(values) - 1))],
        "max": values[-1],
    }


def parse_qasm(path: Path) -> tuple[int, list[Gate]]:
    text = path.read_text()
    qreg_match = QREG_RE.search(text)
    if not qreg_match:
        raise ValueError(f"missing qreg in {path}")
    n_qubits = int(qreg_match.group(1))
    gates: list[Gate] = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.split("//", 1)[0].strip()
        if not line or line.startswith(("OPENQASM", "include", "qreg", "creg", "measure", "barrier")):
            continue
        match = GATE_RE.match(line)
        if not match:
            raise ValueError(f"unparsed line {path}:{line_no}: {raw}")
        op, angle_expr, args = match.groups()
        qubits = tuple(int(x) for x in Q_RE.findall(args))
        gates.append(Gate(op=op, qubits=qubits, angle_expr=angle_expr, angle=safe_angle(angle_expr), line_no=line_no))
    return n_qubits, gates


def connected_components(n_qubits: int, pairs: Counter[tuple[int, int]]) -> list[list[int]]:
    graph: list[set[int]] = [set() for _ in range(n_qubits)]
    for (a, b), count in pairs.items():
        if count <= 0:
            continue
        graph[a].add(b)
        graph[b].add(a)
    seen = [False] * n_qubits
    comps: list[list[int]] = []
    for start in range(n_qubits):
        if seen[start]:
            continue
        seen[start] = True
        q = deque([start])
        comp = []
        while q:
            node = q.popleft()
            comp.append(node)
            for nb in graph[node]:
                if not seen[nb]:
                    seen[nb] = True
                    q.append(nb)
        comps.append(sorted(comp))
    return sorted(comps, key=lambda c: (-len(c), c[0]))


def greedy_layers(gates: list[Gate]) -> list[dict[str, object]]:
    layers: list[dict[str, object]] = []
    used: set[int] = set()
    for gate in gates:
        touched = set(gate.qubits)
        if layers and touched.isdisjoint(used):
            layer = layers[-1]
        else:
            layer = {"ops": Counter(), "gates": [], "qubits": set()}
            layers.append(layer)
            used = set()
        layer["ops"][gate.op] += 1
        layer["gates"].append(gate)
        layer["qubits"].update(touched)
        used.update(touched)
    return layers


def layer_summary(layers: list[dict[str, object]]) -> dict[str, int | None]:
    first_ent_layer = None
    last_ent_layer = None
    for i, layer in enumerate(layers):
        ops: Counter[str] = layer["ops"]  # type: ignore[assignment]
        if ops.get("cx", 0) + ops.get("swap", 0):
            if first_ent_layer is None:
                first_ent_layer = i
            last_ent_layer = i
    if first_ent_layer is None:
        return {
            "layer_count": len(layers),
            "first_entangling_layer": None,
            "last_entangling_layer": None,
            "leading_oneq_layers": len(layers),
            "trailing_oneq_layers": len(layers),
        }
    return {
        "layer_count": len(layers),
        "first_entangling_layer": first_ent_layer,
        "last_entangling_layer": last_ent_layer,
        "leading_oneq_layers": first_ent_layer,
        "trailing_oneq_layers": len(layers) - last_ent_layer - 1,
    }


def ngram_counter(seq: list[str], n: int = 5) -> Counter[tuple[str, ...]]:
    if len(seq) < n:
        return Counter()
    return Counter(tuple(seq[i : i + n]) for i in range(len(seq) - n + 1))


def cosine(a: Counter[tuple[str, ...]], b: Counter[tuple[str, ...]]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(count * b.get(key, 0) for key, count in a.items())
    norm_a = math.sqrt(sum(x * x for x in a.values()))
    norm_b = math.sqrt(sum(x * x for x in b.values()))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def analyze_file(path: Path) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], Counter[tuple[str, ...]]]:
    n_qubits, gates = parse_qasm(path)
    info = parse_name(path.name)
    difficulty = path.parent.name
    ops = Counter(g.op for g in gates)
    directed_pairs: Counter[tuple[int, int]] = Counter()
    undirected_pairs: Counter[tuple[int, int]] = Counter()
    swap_pairs: Counter[tuple[int, int]] = Counter()
    pair_first_last: dict[tuple[int, int], list[int]] = {}
    swap_positions: list[int] = []
    ent_positions: list[int] = []
    oneq_counts = [0] * n_qubits
    rx_counts = [0] * n_qubits
    rz_counts = [0] * n_qubits
    ent_touch = [0] * n_qubits
    cx_touch = [0] * n_qubits
    swap_touch = [0] * n_qubits
    angle_rows: list[dict[str, object]] = []
    angle_bucket_counts = Counter()
    pi_fraction_counts = Counter()
    noisy_errors: list[float] = []
    first_ent_gate = None
    last_ent_gate = None

    for index, gate in enumerate(gates, 1):
        if len(gate.qubits) == 1:
            q = gate.qubits[0]
            oneq_counts[q] += 1
            if gate.op == "rx":
                rx_counts[q] += 1
            elif gate.op == "rz":
                rz_counts[q] += 1
        if gate.angle is not None:
            bucket, frac, err = angle_bucket(gate.angle, gate.angle_expr)
            angle_bucket_counts[(gate.op, bucket)] += 1
            if frac is not None:
                pi_fraction_counts[(gate.op, frac, bucket)] += 1
            if err is not None and bucket == "numeric_noisy_non_fraction":
                noisy_errors.append(err)
            angle_rows.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "difficulty": difficulty,
                    "file": path.name,
                    "op": gate.op,
                    "bucket": bucket,
                    "nearest_pi_fraction": frac,
                    "nearest_pi_error": "" if err is None else f"{err:.12g}",
                    "angle_expr": gate.angle_expr,
                    "angle_value": f"{gate.angle:.17g}",
                }
            )
        if gate.op in {"cx", "swap"} and len(gate.qubits) == 2:
            a, b = gate.qubits
            directed_pairs[(a, b)] += 1
            u = (a, b) if a < b else (b, a)
            undirected_pairs[u] += 1
            if u not in pair_first_last:
                pair_first_last[u] = [index, index]
            else:
                pair_first_last[u][1] = index
            ent_positions.append(index)
            if first_ent_gate is None:
                first_ent_gate = index
            last_ent_gate = index
            for q in (a, b):
                ent_touch[q] += 1
            if gate.op == "cx":
                for q in (a, b):
                    cx_touch[q] += 1
            else:
                swap_positions.append(index)
                swap_pairs[u] += 1
                for q in (a, b):
                    swap_touch[q] += 1

    layers = greedy_layers(gates)
    layers_info = layer_summary(layers)
    prefix = gates[: (first_ent_gate - 1 if first_ent_gate else len(gates))]
    suffix = gates[last_ent_gate:] if last_ent_gate else []
    prefix_counts = Counter(q for g in prefix for q in g.qubits)
    suffix_counts = Counter(q for g in suffix for q in g.qubits)
    comps = connected_components(n_qubits, undirected_pairs)
    degrees = [0] * n_qubits
    weighted_degrees = [0] * n_qubits
    for (a, b), count in undirected_pairs.items():
        degrees[a] += 1
        degrees[b] += 1
        weighted_degrees[a] += count
        weighted_degrees[b] += count
    pair_reps = list(undirected_pairs.values())
    pair_distances = [abs(a - b) for a, b in undirected_pairs]
    reciprocal_pair_count = 0
    for a, b in undirected_pairs:
        if directed_pairs.get((a, b), 0) and directed_pairs.get((b, a), 0):
            reciprocal_pair_count += 1

    pair_rows: list[dict[str, object]] = []
    for (a, b), count in undirected_pairs.most_common():
        first, last = pair_first_last[(a, b)]
        pair_rows.append(
            {
                "path": str(path.relative_to(ROOT)),
                "difficulty": difficulty,
                "file": path.name,
                "q0": a,
                "q1": b,
                "distance": abs(a - b),
                "count_undirected_entangling": count,
                "cx_forward": directed_pairs.get((a, b), 0),
                "cx_reverse": directed_pairs.get((b, a), 0),
                "swap_count": swap_pairs.get((a, b), 0),
                "first_gate_index": first,
                "last_gate_index": last,
                "span_fraction": f"{(last - first) / max(1, len(gates)):.8f}",
            }
        )

    top_pairs = [
        f"{a}-{b}:{count}"
        for (a, b), count in undirected_pairs.most_common(8)
    ]
    top_swap_pairs = [
        f"{a}-{b}:{count}"
        for (a, b), count in swap_pairs.most_common(8)
    ]
    symbolic_pi_angles = sum(c for (op, bucket), c in angle_bucket_counts.items() if bucket == "symbolic_pi_expr")
    numeric_fractionish_angles = sum(
        c
        for (op, bucket), c in angle_bucket_counts.items()
        if bucket
        in {
            "numeric_exact_pi_fraction",
            "numeric_very_close_pi_fraction",
            "numeric_close_pi_fraction",
            "numeric_loose_pi_fraction",
        }
    )
    noisy_angles = sum(c for (op, bucket), c in angle_bucket_counts.items() if bucket == "numeric_noisy_non_fraction")

    row: dict[str, object] = {
        "path": str(path.relative_to(ROOT)),
        "difficulty": difficulty,
        "file": path.name,
        "challenge_n": info["challenge_n"],
        "challenge_id": info["challenge_id"],
        "qreg": n_qubits,
        "file_bytes": path.stat().st_size,
        "gate_count": len(gates),
        "op_rx": ops.get("rx", 0),
        "op_rz": ops.get("rz", 0),
        "op_cx": ops.get("cx", 0),
        "op_swap": ops.get("swap", 0),
        "op_set": ",".join(sorted(ops)),
        "oneq_count": ops.get("rx", 0) + ops.get("rz", 0),
        "entangling_count": ops.get("cx", 0) + ops.get("swap", 0),
        "first_entangling_gate_index": first_ent_gate,
        "last_entangling_gate_index": last_ent_gate,
        "leading_oneq_gate_count": (first_ent_gate - 1) if first_ent_gate else len(gates),
        "trailing_oneq_gate_count": (len(gates) - last_ent_gate) if last_ent_gate else 0,
        "leading_oneq_unique_qubits": len(prefix_counts),
        "trailing_oneq_unique_qubits": len(suffix_counts),
        "leading_oneq_per_qubit_min": min(prefix_counts.get(q, 0) for q in range(n_qubits)),
        "leading_oneq_per_qubit_max": max(prefix_counts.get(q, 0) for q in range(n_qubits)),
        "trailing_oneq_per_qubit_min": min(suffix_counts.get(q, 0) for q in range(n_qubits)),
        "trailing_oneq_per_qubit_max": max(suffix_counts.get(q, 0) for q in range(n_qubits)),
        "layer_count_greedy": layers_info["layer_count"],
        "first_entangling_layer_greedy": layers_info["first_entangling_layer"],
        "last_entangling_layer_greedy": layers_info["last_entangling_layer"],
        "leading_oneq_layers_greedy": layers_info["leading_oneq_layers"],
        "trailing_oneq_layers_greedy": layers_info["trailing_oneq_layers"],
        "unique_undirected_entangling_pairs": len(undirected_pairs),
        "unique_directed_entangling_pairs": len(directed_pairs),
        "repeated_undirected_pairs": sum(1 for c in pair_reps if c > 1),
        "max_pair_repetitions": max(pair_reps) if pair_reps else 0,
        "mean_pair_repetitions": f"{mean(pair_reps):.6f}",
        "median_pair_repetitions": f"{stats.median(pair_reps):.6f}" if pair_reps else "0",
        "graph_density": f"{len(undirected_pairs) / max(1, n_qubits * (n_qubits - 1) / 2):.8f}",
        "component_count": len(comps),
        "largest_component": len(comps[0]) if comps else 0,
        "degree_min": min(degrees) if degrees else 0,
        "degree_max": max(degrees) if degrees else 0,
        "degree_mean": f"{mean(degrees):.6f}",
        "weighted_degree_min": min(weighted_degrees) if weighted_degrees else 0,
        "weighted_degree_max": max(weighted_degrees) if weighted_degrees else 0,
        "weighted_degree_mean": f"{mean(weighted_degrees):.6f}",
        "reciprocal_undirected_pairs": reciprocal_pair_count,
        "adjacent_pair_fraction": f"{sum(1 for d in pair_distances if d == 1) / max(1, len(pair_distances)):.8f}",
        "mean_pair_distance": f"{mean(pair_distances):.6f}",
        "max_pair_distance": max(pair_distances) if pair_distances else 0,
        "qubits_touched_by_entangling": sum(1 for c in ent_touch if c),
        "qubits_touched_by_cx": sum(1 for c in cx_touch if c),
        "qubits_touched_by_swap": sum(1 for c in swap_touch if c),
        "oneq_per_qubit_min": min(oneq_counts),
        "oneq_per_qubit_max": max(oneq_counts),
        "rx_per_qubit_min": min(rx_counts),
        "rx_per_qubit_max": max(rx_counts),
        "rz_per_qubit_min": min(rz_counts),
        "rz_per_qubit_max": max(rz_counts),
        "symbolic_pi_angles": symbolic_pi_angles,
        "numeric_fractionish_angles": numeric_fractionish_angles,
        "noisy_non_fraction_angles": noisy_angles,
        "angle_noise_error_median": f"{stats.median(noisy_errors):.8f}" if noisy_errors else "",
        "angle_noise_error_max": f"{max(noisy_errors):.8f}" if noisy_errors else "",
        "swap_position_fractions": ";".join(f"{pos / len(gates):.6f}" for pos in swap_positions),
        "top_pairs": ";".join(top_pairs),
        "top_swap_pairs": ";".join(top_swap_pairs),
        "first_20_ops": "".join(g.op[0].upper() if g.op != "swap" else "S" for g in gates[:20]),
        "last_20_ops": "".join(g.op[0].upper() if g.op != "swap" else "S" for g in gates[-20:]),
    }

    opseq = [g.op for g in gates]
    return row, angle_rows, pair_rows, ngram_counter(opseq)


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    if not rows:
        path.write_text("")
        return
    if fieldnames is None:
        seen: list[str] = []
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.append(key)
        fieldnames = seen
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def summarize_by_difficulty(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["difficulty"])].append(row)

    out_rows: list[dict[str, object]] = []
    for difficulty in sorted(grouped, key=difficulty_key):
        group = grouped[difficulty]
        numeric_keys = [
            "qreg",
            "gate_count",
            "op_rx",
            "op_rz",
            "op_cx",
            "op_swap",
            "oneq_count",
            "entangling_count",
            "leading_oneq_gate_count",
            "trailing_oneq_gate_count",
            "leading_oneq_layers_greedy",
            "trailing_oneq_layers_greedy",
            "unique_undirected_entangling_pairs",
            "repeated_undirected_pairs",
            "max_pair_repetitions",
            "component_count",
            "largest_component",
            "degree_min",
            "degree_max",
            "symbolic_pi_angles",
            "numeric_fractionish_angles",
            "noisy_non_fraction_angles",
        ]
        summary: dict[str, object] = {
            "difficulty": difficulty,
            "file_count": len(group),
            "qreg_min": min(int(r["qreg"]) for r in group),
            "qreg_max": max(int(r["qreg"]) for r in group),
            "op_sets": "|".join(sorted(set(str(r["op_set"]) for r in group))),
        }
        for key in numeric_keys:
            vals = [float(r[key]) for r in group if r[key] not in (None, "")]
            summary[f"{key}_mean"] = f"{mean(vals):.6f}"
            summary[f"{key}_min"] = f"{min(vals):.6f}" if vals else ""
            summary[f"{key}_max"] = f"{max(vals):.6f}" if vals else ""
        total_angles = sum(
            int(r["symbolic_pi_angles"]) + int(r["numeric_fractionish_angles"]) + int(r["noisy_non_fraction_angles"])
            for r in group
        )
        total_fractionish = sum(int(r["symbolic_pi_angles"]) + int(r["numeric_fractionish_angles"]) for r in group)
        summary["fractionish_angle_fraction"] = f"{total_fractionish / max(1, total_angles):.8f}"
        summary["noisy_angle_fraction"] = f"{sum(int(r['noisy_non_fraction_angles']) for r in group) / max(1, total_angles):.8f}"
        out_rows.append(summary)
    return out_rows


def summarize_angle_rows(angle_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped = Counter(
        (str(row["difficulty"]), str(row["op"]), str(row["bucket"]), str(row["nearest_pi_fraction"]))
        for row in angle_rows
    )
    out = []
    for (difficulty, op, bucket, frac), count in sorted(grouped.items(), key=lambda x: (difficulty_key(x[0][0]), x[0][1], x[0][2], x[0][3])):
        out.append(
            {
                "difficulty": difficulty,
                "op": op,
                "bucket": bucket,
                "nearest_pi_fraction": frac,
                "count": count,
            }
        )
    return out


def summarize_angle_precision(angle_summary: list[dict[str, object]]) -> list[dict[str, object]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in angle_summary:
        counts[str(row["difficulty"])][str(row["bucket"])] += int(row["count"])

    out: list[dict[str, object]] = []
    for difficulty in sorted(counts, key=difficulty_key):
        c = counts[difficulty]
        total = sum(c.values())
        strict = (
            c["symbolic_pi_expr"]
            + c["numeric_exact_pi_fraction"]
            + c["numeric_very_close_pi_fraction"]
        )
        close = c["numeric_close_pi_fraction"]
        loose = c["numeric_loose_pi_fraction"]
        non_fraction = c["numeric_noisy_non_fraction"]
        out.append(
            {
                "difficulty": difficulty,
                "total_angles": total,
                "symbolic_pi_expr": c["symbolic_pi_expr"],
                "numeric_exact_plus_veryclose_pi_fraction": c["numeric_exact_pi_fraction"] + c["numeric_very_close_pi_fraction"],
                "strict_pi_count": strict,
                "strict_pi_fraction": f"{strict / max(1, total):.8f}",
                "numeric_close_pi_fraction": close,
                "close_fraction": f"{close / max(1, total):.8f}",
                "numeric_loose_pi_fraction": loose,
                "loose_fraction": f"{loose / max(1, total):.8f}",
                "numeric_non_fraction": non_fraction,
                "non_fraction": f"{non_fraction / max(1, total):.8f}",
            }
        )
    return out


def pairwise_similarity(rows: list[dict[str, object]], ngrams_by_path: dict[str, Counter[tuple[str, ...]]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    pairs: list[dict[str, object]] = []
    agg: dict[tuple[str, str], list[float]] = defaultdict(list)
    for i, a in enumerate(rows):
        for b in rows[i + 1 :]:
            sim = cosine(ngrams_by_path[str(a["path"])], ngrams_by_path[str(b["path"])])
            da = str(a["difficulty"])
            db = str(b["difficulty"])
            key = tuple(sorted((da, db), key=lambda x: difficulty_key(x)))
            agg[key].append(sim)
            pairs.append(
                {
                    "file_a": a["path"],
                    "difficulty_a": da,
                    "file_b": b["path"],
                    "difficulty_b": db,
                    "op_5gram_cosine": f"{sim:.8f}",
                }
            )
    agg_rows = []
    for (da, db), vals in sorted(agg.items(), key=lambda x: (difficulty_key(x[0][0]), difficulty_key(x[0][1]))):
        q = quantiles(vals)
        agg_rows.append(
            {
                "difficulty_a": da,
                "difficulty_b": db,
                "pair_count": len(vals),
                "mean_op_5gram_cosine": f"{mean(vals):.8f}",
                "min": f"{q['min']:.8f}",
                "p25": f"{q['p25']:.8f}",
                "median": f"{q['median']:.8f}",
                "p75": f"{q['p75']:.8f}",
                "max": f"{q['max']:.8f}",
            }
        )
    return pairs, agg_rows


def build_markdown_report(rows: list[dict[str, object]], diff_rows: list[dict[str, object]], sim_rows: list[dict[str, object]]) -> str:
    total_gates = sum(int(r["gate_count"]) for r in rows)
    total_ops = Counter()
    for r in rows:
        for op in ("rx", "rz", "cx", "swap"):
            total_ops[op] += int(r[f"op_{op}"])
    all_op_sets = sorted(set(str(r["op_set"]) for r in rows))
    swap_files = [r for r in rows if int(r["op_swap"]) > 0]
    no_swap_files = [r for r in rows if int(r["op_swap"]) == 0]
    full_component_files = [r for r in rows if int(r["largest_component"]) == int(r["qreg"])]
    leading_layer_examples = sorted(rows, key=lambda r: int(r["leading_oneq_gate_count"]), reverse=True)[:8]
    high_repeat_examples = sorted(rows, key=lambda r: int(r["max_pair_repetitions"]), reverse=True)[:8]
    non_fraction_by_diff = {
        r["difficulty"]: r["noisy_angle_fraction"]
        for r in diff_rows
    }

    lines: list[str] = []
    lines.append("# Static QASM Forensics")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Files analyzed: {len(rows)}")
    lines.append(f"Total gates parsed: {total_gates}")
    lines.append(f"Operation sets observed: {', '.join(all_op_sets)}")
    lines.append(f"Total operations: {dict(total_ops)}")
    lines.append("")
    lines.append("## Difficulty summary")
    lines.append("")
    lines.append("| difficulty | files | qubits | gates mean | rx mean | rz mean | cx mean | swaps total | noisy angle frac | graph density mean | leading 1q gates mean |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in diff_rows:
        difficulty = str(r["difficulty"])
        rows_in_diff = [x for x in rows if x["difficulty"] == difficulty]
        swaps_total = sum(int(x["op_swap"]) for x in rows_in_diff)
        graph_density = mean(float(x["graph_density"]) for x in rows_in_diff)
        lines.append(
            f"| {difficulty} | {r['file_count']} | {r['qreg_min']}-{r['qreg_max']} | "
            f"{float(r['gate_count_mean']):.1f} | {float(r['op_rx_mean']):.1f} | "
            f"{float(r['op_rz_mean']):.1f} | {float(r['op_cx_mean']):.1f} | {swaps_total} | "
            f"{float(r['noisy_angle_fraction']):.3f} | {graph_density:.3f} | "
            f"{float(r['leading_oneq_gate_count_mean']):.1f} |"
        )
    lines.append("")
    lines.append("## Structural observations")
    lines.append("")
    lines.append(f"- Every file uses only `{', '.join(sorted(total_ops))}` gates; there are no measurements, barriers, H/S/T, or parameterized two-qubit rotations.")
    lines.append(f"- `swap` is sparse: {len(swap_files)} files contain swaps and {len(no_swap_files)} contain none. Total swaps across the full set: {total_ops['swap']}.")
    lines.append(f"- The entangling graph is connected in {len(full_component_files)}/{len(rows)} files. Very small files can be disconnected or weakly connected, but moderate through very_hard are generally fully connected.")
    lines.append(f"- The non-fraction angle bucket, defined as farther than 1e-2 from the nearest pi fraction with denominator <= 16, is {non_fraction_by_diff} by difficulty.")
    lines.append("- The very_hard files have large dense RX/RZ prefixes before the first entangler; this looks like a distinct obfuscation pass rather than just scaled-up easy circuits.")
    lines.append("- Repeated undirected CX pairs are common, supporting an inverse-composition/cancellation family rather than arbitrary one-pass random circuits.")
    lines.append("")
    lines.append("## Leading single-qubit prefixes")
    lines.append("")
    for r in leading_layer_examples:
        lines.append(
            f"- {r['path']}: q={r['qreg']}, leading one-qubit gates={r['leading_oneq_gate_count']}, "
            f"greedy leading layers={r['leading_oneq_layers_greedy']}, first ops={r['first_20_ops']}"
        )
    lines.append("")
    lines.append("## Highest pair repetitions")
    lines.append("")
    for r in high_repeat_examples:
        lines.append(
            f"- {r['path']}: max pair repetitions={r['max_pair_repetitions']}, "
            f"repeated pairs={r['repeated_undirected_pairs']}, top pairs={r['top_pairs']}"
        )
    lines.append("")
    lines.append("## Operation-sequence similarity")
    lines.append("")
    lines.append("The table below is based only on operation 5-gram cosine similarity, not qubit indices or angles.")
    lines.append("")
    lines.append("| diff A | diff B | pairs | mean | median | max |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for r in sim_rows:
        lines.append(
            f"| {r['difficulty_a']} | {r['difficulty_b']} | {r['pair_count']} | "
            f"{float(r['mean_op_5gram_cosine']):.3f} | {float(r['median']):.3f} | {float(r['max']):.3f} |"
        )
    lines.append("")
    lines.append("## Cracking hints from static structure")
    lines.append("")
    lines.append("- Treat symbolic and near-pi RX angles as high-value clues, especially on very easy/easy files where many RX(pi) remnants survive.")
    lines.append("- Track swaps explicitly before reading candidate bits; final Qiskit bitstrings are high-index to low-index, so q0 is the right-most bit.")
    lines.append("- Repeated opposite-direction CX pairs and repeated undirected pairs are plausible cancellation targets. A symbolic pass that merges adjacent RX/RZ and cancels CX pairs after commuting one-qubit gates should be cheap before simulation.")
    lines.append("- For very_hard, start by peeling complete leading/trailing RX/RZ layers and looking for inverse blocks or pair-repetition symmetry. The dense all-qubit prefixes are not random measurements; they are static unitary dressing.")
    lines.append("- RZ-only layers on computational basis states are invisible until conjugated by RX/CX structure; for peak extraction, prioritize RX parity after reducing identity-like blocks.")
    lines.append("")
    lines.append("## Output files")
    lines.append("")
    for name in [
        "per_file_metrics.csv",
        "difficulty_summary.csv",
        "angle_bucket_summary.csv",
        "angle_precision_summary.csv",
        "pair_repetitions.csv",
        "operation_similarity.csv",
        "operation_similarity_by_difficulty.csv",
        "qasm_static_features.json",
    ]:
        lines.append(f"- `{name}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    qasm_paths = sorted(CHALLENGES.glob("*/*.qasm"), key=file_key)
    rows: list[dict[str, object]] = []
    all_angle_rows: list[dict[str, object]] = []
    all_pair_rows: list[dict[str, object]] = []
    ngrams_by_path: dict[str, Counter[tuple[str, ...]]] = {}

    for path in qasm_paths:
        row, angle_rows, pair_rows, ngrams = analyze_file(path)
        rows.append(row)
        all_angle_rows.extend(angle_rows)
        all_pair_rows.extend(pair_rows)
        ngrams_by_path[str(row["path"])] = ngrams

    diff_rows = summarize_by_difficulty(rows)
    angle_summary = summarize_angle_rows(all_angle_rows)
    angle_precision = summarize_angle_precision(angle_summary)
    sim_pairs, sim_summary = pairwise_similarity(rows, ngrams_by_path)

    write_csv(OUT / "per_file_metrics.csv", rows)
    write_csv(OUT / "difficulty_summary.csv", diff_rows)
    write_csv(OUT / "angle_bucket_summary.csv", angle_summary)
    write_csv(OUT / "angle_precision_summary.csv", angle_precision)
    write_csv(OUT / "pair_repetitions.csv", all_pair_rows)
    write_csv(OUT / "operation_similarity.csv", sim_pairs)
    write_csv(OUT / "operation_similarity_by_difficulty.csv", sim_summary)

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
        "qasm_file_count": len(rows),
        "per_file": rows,
        "difficulty_summary": diff_rows,
        "angle_bucket_summary": angle_summary,
        "angle_precision_summary": angle_precision,
        "operation_similarity_by_difficulty": sim_summary,
    }
    (OUT / "qasm_static_features.json").write_text(json.dumps(payload, indent=2))
    (OUT / "static_forensics_report.md").write_text(build_markdown_report(rows, diff_rows, sim_summary))

    print(f"Wrote outputs to {OUT}")
    print(f"Parsed {len(rows)} QASM files")
    for r in diff_rows:
        print(
            f"{r['difficulty']:10s} files={r['file_count']} "
            f"q={r['qreg_min']}-{r['qreg_max']} "
            f"gates_mean={float(r['gate_count_mean']):.1f} "
            f"cx_mean={float(r['op_cx_mean']):.1f} "
            f"noisy_angle_fraction={float(r['noisy_angle_fraction']):.3f}"
        )


if __name__ == "__main__":
    main()
