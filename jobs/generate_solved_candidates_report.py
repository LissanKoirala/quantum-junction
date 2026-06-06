#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_candidates(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    for row in rows:
        label = row.get("challenge", "")
        try:
            row["challenge_id"] = int(label.rsplit("_", 1)[1])
        except Exception:
            row["challenge_id"] = 0
        try:
            row["qubits_i"] = int(row.get("qubits") or 0)
        except Exception:
            row["qubits_i"] = 0
        try:
            row["probability_f"] = float(row.get("top_fraction") or "")
        except Exception:
            row["probability_f"] = None
    return rows


def fmt_probability(value: Any) -> str:
    if value is None:
        return ""
    value_f = float(value)
    if value_f >= 0.01:
        return f"{value_f:.6f}".rstrip("0").rstrip(".")
    return f"{value_f:.3e}"


def difficulty_color(difficulty: str) -> str:
    return {
        "very easy": "#2f7d32",
        "easy": "#1976a2",
        "moderate": "#9a6a00",
        "hard": "#b03a2e",
        "very_hard": "#6f3fb3",
    }.get(difficulty, "#555555")


def svg_probability_plot(solved: list[dict[str, Any]], path: Path) -> None:
    rows = [row for row in solved if row.get("probability_f") is not None and float(row["probability_f"]) > 0.0]
    width = max(1200, 26 * len(rows) + 180)
    height = 620
    left = 80
    right = 30
    top = 42
    bottom = 150
    plot_w = width - left - right
    plot_h = height - top - bottom
    min_v = min(float(row["probability_f"]) for row in rows) if rows else 1e-3
    max_v = max(float(row["probability_f"]) for row in rows) if rows else 1.0
    min_log = math.floor(math.log10(max(min_v, 1e-12)))
    max_log = math.ceil(math.log10(max_v))
    if min_log == max_log:
        min_log -= 1
        max_log += 1

    def y_for(value: float) -> float:
        log_v = math.log10(max(value, 10 ** min_log))
        return top + (max_log - log_v) / (max_log - min_log) * plot_h

    tick_logs = list(range(min_log, max_log + 1))
    bar_gap = 4
    bar_w = max(8, (plot_w - bar_gap * max(0, len(rows) - 1)) / max(1, len(rows)))
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" '
        'aria-labelledby="title desc">',
        "<title id=\"title\">Solved candidate bitstring probability</title>",
        "<desc id=\"desc\">Log-scale bar chart of reported candidate probabilities or top fractions.</desc>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{left}" y="24" font-family="Arial, sans-serif" font-size="18" font-weight="700">'
        "Solved candidate bitstring probability / top fraction</text>",
    ]
    for tick in tick_logs:
        value = 10 ** tick
        y = y_for(value)
        parts.append(f'<line x1="{left}" x2="{width - right}" y1="{y:.2f}" y2="{y:.2f}" stroke="#e6e6e6"/>')
        parts.append(
            f'<text x="{left - 10}" y="{y + 4:.2f}" text-anchor="end" '
            'font-family="Arial, sans-serif" font-size="12" fill="#333">'
            f"1e{tick}</text>"
        )
    parts.append(f'<line x1="{left}" x2="{left}" y1="{top}" y2="{height - bottom}" stroke="#333"/>')
    parts.append(f'<line x1="{left}" x2="{width - right}" y1="{height - bottom}" y2="{height - bottom}" stroke="#333"/>')
    for idx, row in enumerate(rows):
        x = left + idx * (bar_w + bar_gap)
        value = float(row["probability_f"])
        y = y_for(value)
        h = height - bottom - y
        label = html.escape(row["challenge"])
        prob = html.escape(fmt_probability(value))
        source = html.escape(row.get("source") or "")
        color = difficulty_color(row.get("difficulty") or "")
        parts.append(f"<g><title>{label}: {prob} ({source})</title>")
        parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="{color}"/>')
        parts.append(
            f'<text x="{x + bar_w / 2:.2f}" y="{height - bottom + 16}" transform="rotate(65 {x + bar_w / 2:.2f} {height - bottom + 16})" '
            'font-family="Arial, sans-serif" font-size="11" fill="#222">'
            f"{label}</text>"
        )
        parts.append("</g>")
    legend_x = left
    legend_y = height - 32
    for difficulty in ["very easy", "easy", "moderate", "hard", "very_hard"]:
        color = difficulty_color(difficulty)
        label = html.escape(difficulty)
        parts.append(f'<rect x="{legend_x}" y="{legend_y - 10}" width="12" height="12" fill="{color}"/>')
        parts.append(
            f'<text x="{legend_x + 18}" y="{legend_y}" font-family="Arial, sans-serif" '
            f'font-size="12" fill="#222">{label}</text>'
        )
        legend_x += 120
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n")


def markdown_report(rows: list[dict[str, Any]], report_path: Path, plot_path: Path, source_path: Path) -> None:
    solved = [row for row in rows if row.get("candidate")]
    unsolved = [row for row in rows if not row.get("candidate")]
    solved_sorted = sorted(solved, key=lambda row: int(row.get("challenge_id") or 0))
    counts = Counter(row.get("difficulty") or "" for row in solved)
    generated = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    plot_rel = plot_path.relative_to(report_path.parent)
    source_rel = source_path.relative_to(ROOT)
    lines = [
        "# Solved Candidate Report",
        "",
        f"Generated: {generated}",
        "",
        f"Source rollup: `{source_rel}`",
        "",
        f"Solved candidates: {len(solved)}/{len(rows)}.",
        f"Open candidates: {len(unsolved)}.",
        "",
        "Solved by difficulty:",
    ]
    for difficulty, count in sorted(counts.items()):
        lines.append(f"- {difficulty}: {count}")
    if unsolved:
        lines.extend(
            [
                "",
                "Open labels:",
                "- " + ", ".join(row["challenge"] for row in sorted(unsolved, key=lambda row: int(row.get("challenge_id") or 0))),
            ]
        )
    lines.extend(
        [
            "",
            "## Probability Plot",
            "",
            "The chart uses the rollup `top_fraction` field. For exact statevector rows this is the exact peak probability; for sampled tensor-network rows this is the observed top fraction or candidate score reported by that run.",
            "",
            f"![Solved candidate bitstring probability]({plot_rel})",
            "",
            "## Solved Candidates",
            "",
            "| challenge | difficulty | qubits | bitstring | probability/top fraction | source | validation |",
            "| --- | --- | ---: | --- | ---: | --- | --- |",
        ]
    )
    for row in solved_sorted:
        probability = fmt_probability(row.get("probability_f"))
        lines.append(
            "| "
            + " | ".join(
                [
                    row.get("challenge", ""),
                    row.get("difficulty", ""),
                    row.get("qubits", ""),
                    f"`{row.get('candidate', '')}`",
                    probability,
                    row.get("source", ""),
                    row.get("validation", ""),
                ]
            )
            + " |"
        )
    if unsolved:
        lines.extend(
            [
                "",
                "## Not Yet Solved",
                "",
                "| challenge | difficulty | qubits | qasm |",
                "| --- | --- | ---: | --- |",
            ]
        )
        for row in sorted(unsolved, key=lambda row: int(row.get("challenge_id") or 0)):
            lines.append(
                "| "
                + " | ".join(
                    [
                        row.get("challenge", ""),
                        row.get("difficulty", ""),
                        row.get("qubits", ""),
                        f"`{row.get('qasm', '')}`",
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "Bit order: candidates are in Qiskit/counts order, with the right-most bit corresponding to qubit 0.",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate solved-candidate report and probability plot.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--candidates", type=Path, default=ROOT / "outputs" / "tree_tensor_sim" / "CANDIDATES.tsv")
    parser.add_argument("--report", type=Path, default=ROOT / "research" / "hard_problems" / "SOLVED_CANDIDATES_REPORT.md")
    parser.add_argument("--plot", type=Path, default=ROOT / "research" / "hard_problems" / "solved_bitstring_probability.svg")
    args = parser.parse_args()

    root = args.root.resolve()
    candidates = args.candidates if args.candidates.is_absolute() else root / args.candidates
    report = args.report if args.report.is_absolute() else root / args.report
    plot = args.plot if args.plot.is_absolute() else root / args.plot
    rows = load_candidates(candidates)
    solved = [row for row in rows if row.get("candidate")]
    svg_probability_plot(sorted(solved, key=lambda row: int(row.get("challenge_id") or 0)), plot)
    markdown_report(rows, report, plot, candidates)
    print(f"wrote {report.relative_to(root)}")
    print(f"wrote {plot.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
