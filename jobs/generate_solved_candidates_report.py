#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
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


def attach_selected_evidence(rows: list[dict[str, Any]], evidence_path: Path) -> None:
    if not evidence_path.exists():
        return
    evidence_rows = json.loads(evidence_path.read_text())
    selected_by_label = {
        row.get("label"): row.get("selected") or {}
        for row in evidence_rows
        if row.get("selected")
    }
    for row in rows:
        selected = selected_by_label.get(row.get("challenge")) or {}
        row["selected_path"] = selected.get("path") or ""
        row["candidate_strategy"] = selected.get("candidate_strategy") or ""


def load_distribution_summary(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    rows = json.loads(path.read_text())
    return {row["challenge"]: row for row in rows}


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


def qiskit_from_sampling_entry(entry: dict[str, Any]) -> str:
    if entry.get("qiskit_order"):
        return str(entry["qiskit_order"])
    if entry.get("bitstring"):
        return str(entry["bitstring"])
    if entry.get("permuted_measurement_order"):
        return str(entry["permuted_measurement_order"])[::-1]
    return str(entry.get("raw_site_order") or "")


def selected_only_distribution(row: dict[str, Any], note: str) -> dict[str, Any]:
    value = row.get("probability_f")
    value_f = float(value) if value is not None else 0.0
    return {
        "kind": "selected",
        "note": note,
        "source_label": row.get("source") or "",
        "value_label": "probability/top fraction",
        "tail_value": max(0.0, 1.0 - value_f) if value_f > 0.0 else 0.0,
        "top": [
            {
                "bitstring": row.get("candidate") or "",
                "value": value_f,
            }
        ],
    }


def graph_tns_distribution(root: Path, row: dict[str, Any]) -> dict[str, Any] | None:
    selected_path = row.get("selected_path") or ""
    if not selected_path:
        return None
    path = Path(selected_path)
    if not path.is_absolute():
        path = root / path
    if not path.exists() or path.suffix != ".json":
        return None
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None
    sampling = data.get("sampling") or {}
    top = []
    samples = sampling.get("samples")
    for entry in sampling.get("top") or []:
        value = entry.get("fraction")
        count = entry.get("count")
        if value is None and count is not None and samples:
            try:
                value = int(count) / int(samples)
            except Exception:
                value = None
        if value is None:
            continue
        top.append(
            {
                "bitstring": qiskit_from_sampling_entry(entry),
                "value": float(value),
                "count": count,
            }
        )
    candidate = row.get("candidate") or ""
    if candidate and not any(item["bitstring"] == candidate for item in top):
        value = row.get("probability_f")
        top.insert(
            0,
            {
                "bitstring": candidate,
                "value": float(value) if value is not None else 0.0,
                "count": None,
            },
        )
    if not top:
        return None
    return {
        "kind": "sample",
        "note": "Sampled graph-TNS distribution; tail is all observed sample mass outside the plotted top ranks.",
        "source_label": row.get("source") or "peaked_mpo_graph_tns",
        "value_label": "sample fraction",
        "tail_value": max(0.0, 1.0 - sum(float(item["value"]) for item in top)),
        "top": top,
    }


def distribution_for_row(root: Path, row: dict[str, Any], summary_by_label: dict[str, dict[str, Any]]) -> dict[str, Any]:
    label = row.get("challenge") or ""
    candidate = row.get("candidate") or ""
    summary = summary_by_label.get(label) or {}
    dist = summary.get("distribution") or {}
    if summary.get("selected_candidate") == candidate and dist.get("top"):
        return dist
    graph_dist = graph_tns_distribution(root, row)
    if graph_dist:
        return graph_dist
    return selected_only_distribution(
        row,
        "No retained top-k distribution matched the selected candidate; plotting the selected bitstring from the rollup.",
    )


def wrap_text(text: str, width: int = 64) -> list[str]:
    return [text[index : index + width] for index in range(0, len(text), width)] or [""]


def svg_text(x: float, y: float, text: str, size: int = 16, weight: str = "400", family: str = "Arial") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" fill="#172033">{html.escape(text)}</text>'
    )


def make_bitstring_distribution_svg(row: dict[str, Any], dist: dict[str, Any], path: Path, top_limit: int) -> None:
    label = row["challenge"]
    top_rows = list(dist.get("top") or [])[:top_limit]
    tail_value = float(dist.get("tail_value") or 0.0)
    rows = [
        {
            "bitstring": item.get("bitstring") or "",
            "value": float(item.get("value") or 0.0),
            "count": item.get("count"),
            "is_tail": False,
        }
        for item in top_rows
    ]
    if tail_value > 0.0:
        rows.append({"bitstring": "tail", "value": tail_value, "count": None, "is_tail": True})
    width = 1500
    margin = 36
    bar_x = 96
    bar_width = 420
    text_x = bar_x + bar_width + 34
    row_gap = 48
    row_start = 132
    max_wrap = max((len(wrap_text(str(item["bitstring"]))) for item in rows), default=1)
    height = row_start + max(1, len(rows)) * row_gap + max(0, max_wrap - 1) * 17 + 42
    max_value = max((float(item["value"]) for item in rows), default=1.0) or 1.0
    candidate = row.get("candidate") or ""
    source = dist.get("source_label") or row.get("source") or ""
    value_label = dist.get("value_label") or "probability"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" stroke="#d9dde6"/>',
        svg_text(margin, 42, f"{label} bitstring probability distribution", 24, "700"),
        svg_text(
            margin,
            72,
            f"difficulty={row.get('difficulty', '')} q={row.get('qubits', '')} source={source} kind={dist.get('kind', '')}",
            15,
        ),
        svg_text(margin, 96, f"Selected bitstring: {candidate}", 14, "700", "Courier New"),
        svg_text(bar_x, 124, value_label, 13, "700"),
        svg_text(text_x, 124, "qiskit_order bitstring", 13, "700", "Courier New"),
    ]
    for rank, item in enumerate(rows, start=1):
        y = row_start + (rank - 1) * row_gap
        value = float(item["value"])
        scaled = int((value / max_value) * bar_width)
        is_selected = bool(candidate and item["bitstring"] == candidate)
        is_tail = bool(item["is_tail"])
        bar_color = "#287271" if is_selected else "#d0d0d0" if is_tail else "#4c78a8"
        rank_label = "tail" if is_tail else f"{rank:>2}"
        count = item.get("count")
        value_text = fmt_probability(value) if value else "0"
        if count is not None:
            value_text = f"{count} / {value_text}"
        parts.append(svg_text(margin, y + 22, rank_label, 14, "700", "Courier New"))
        parts.append(f'<rect x="{bar_x}" y="{y}" width="{bar_width}" height="26" fill="#eef2f7" rx="4"/>')
        parts.append(f'<rect x="{bar_x}" y="{y}" width="{max(scaled, 2)}" height="26" fill="{bar_color}" rx="4"/>')
        parts.append(svg_text(bar_x + 10, y + 19, value_text, 13, "700"))
        for line_index, chunk in enumerate(wrap_text(str(item["bitstring"]))):
            parts.append(svg_text(text_x, y + 18 + 17 * line_index, chunk, 14, "400", "Courier New"))
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n")


def write_bitstring_distribution_images(
    root: Path,
    solved: list[dict[str, Any]],
    image_dir: Path,
    summary_by_label: dict[str, dict[str, Any]],
    top_limit: int,
) -> dict[str, Path]:
    image_dir.mkdir(parents=True, exist_ok=True)
    for stale in image_dir.glob("challenge-*.bitstring_probability.svg"):
        stale.unlink()
    paths = {}
    for row in solved:
        dist = distribution_for_row(root, row, summary_by_label)
        image_path = image_dir / f"challenge-{row['challenge']}.bitstring_probability.svg"
        make_bitstring_distribution_svg(row, dist, image_path, top_limit)
        paths[row["challenge"]] = image_path
    return paths


def svg_probability_plot(solved: list[dict[str, Any]], path: Path) -> None:
    rows = list(solved)
    width = max(1200, 26 * len(rows) + 180)
    height = 620
    left = 80
    right = 30
    top = 42
    bottom = 150
    plot_w = width - left - right
    plot_h = height - top - bottom
    reported = [
        float(row["probability_f"])
        for row in rows
        if row.get("probability_f") is not None and float(row["probability_f"]) > 0.0
    ]
    min_v = min(reported) if reported else 1e-3
    max_v = max(reported) if reported else 1.0
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
        value = float(row["probability_f"] or 0.0)
        display_value = value if value > 0.0 else 10 ** min_log
        y = y_for(display_value)
        h = height - bottom - y
        label = html.escape(row["challenge"])
        bitstring = html.escape(row.get("candidate") or "")
        prob = html.escape(fmt_probability(value) if value > 0.0 else "not reported")
        source = html.escape(row.get("source") or "")
        color = difficulty_color(row.get("difficulty") or "")
        parts.append(f"<g><title>{label}: {prob} ({source}) bitstring={bitstring}</title>")
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


def markdown_report(
    rows: list[dict[str, Any]],
    report_path: Path,
    plot_path: Path,
    source_path: Path,
    image_paths: dict[str, Path],
) -> None:
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
            "The SVG contains one plotted bar for every solved candidate in the rollup; each bar tooltip includes the full selected bitstring.",
            "",
            f"![Solved candidate bitstring probability]({plot_rel})",
            "",
            "## Per-Problem Bitstring Probability Graphs",
            "",
            "Each solved problem below embeds its own bitstring probability graph from the committed SVG artifacts. Where top-k distribution evidence was retained, the graph shows the ranked bitstrings and tail mass; otherwise it plots the selected bitstring probability/top fraction from the rollup. Green marks the selected candidate.",
            "",
            "## Solved Candidates",
            "",
            "| challenge | probability graph | difficulty | qubits | bitstring | probability/top fraction | source | validation |",
            "| --- | --- | --- | ---: | --- | ---: | --- | --- |",
        ]
    )
    for row in solved_sorted:
        probability = fmt_probability(row.get("probability_f"))
        image_path = image_paths.get(row.get("challenge", ""))
        image_src = os.path.relpath(image_path, report_path.parent) if image_path else ""
        lines.append(
            "| "
            + " | ".join(
                [
                    row.get("challenge", ""),
                    f'<img src="{html.escape(image_src, quote=True)}" alt="Bitstring probability graph for {html.escape(row.get("challenge", ""), quote=True)}" width="360">',
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
    parser.add_argument("--image-dir", type=Path, default=ROOT / "research" / "hard_problems" / "bitstring_probability_images")
    parser.add_argument("--evidence", type=Path, default=ROOT / "outputs" / "tree_tensor_sim" / "CANDIDATE_EVIDENCE.json")
    parser.add_argument("--distribution-summary", type=Path, default=ROOT / "research" / "quantum_peak_session" / "results" / "distributions" / "distribution_summary.json")
    parser.add_argument("--top-limit", type=int, default=8)
    args = parser.parse_args()

    root = args.root.resolve()
    candidates = args.candidates if args.candidates.is_absolute() else root / args.candidates
    report = args.report if args.report.is_absolute() else root / args.report
    plot = args.plot if args.plot.is_absolute() else root / args.plot
    image_dir = args.image_dir if args.image_dir.is_absolute() else root / args.image_dir
    evidence = args.evidence if args.evidence.is_absolute() else root / args.evidence
    distribution_summary = args.distribution_summary if args.distribution_summary.is_absolute() else root / args.distribution_summary
    rows = load_candidates(candidates)
    attach_selected_evidence(rows, evidence)
    solved = [row for row in rows if row.get("candidate")]
    summary_by_label = load_distribution_summary(distribution_summary)
    image_paths = write_bitstring_distribution_images(
        root,
        sorted(solved, key=lambda row: int(row.get("challenge_id") or 0)),
        image_dir,
        summary_by_label,
        args.top_limit,
    )
    svg_probability_plot(sorted(solved, key=lambda row: int(row.get("challenge_id") or 0)), plot)
    markdown_report(rows, report, plot, candidates, image_paths)
    print(f"wrote {report.relative_to(root)}")
    print(f"wrote {plot.relative_to(root)}")
    print(f"wrote {len(image_paths)} per-problem bitstring probability images under {image_dir.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
