#!/usr/bin/env python3
from __future__ import annotations

import collections
import csv
import json
import math
import time
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent_work" / "tree_tensor_sim" / "report"
FIG = OUT / "figures"
CANDIDATES = ROOT / "outputs" / "tree_tensor_sim" / "collector_current" / "CANDIDATES.tsv"
EVIDENCE = ROOT / "outputs" / "tree_tensor_sim" / "collector_current" / "CANDIDATE_EVIDENCE.json"


def tex_escape(value: Any) -> str:
    s = "" if value is None else str(value)
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(repl.get(ch, ch) for ch in s)


def bits_cell(bits: str) -> str:
    if not bits:
        return "--"
    chunks = [bits[i : i + 8] for i in range(0, len(bits), 8)]
    return r"{\scriptsize\ttfamily " + r"\allowbreak ".join(chunks) + "}"


def source_label(source: str) -> str:
    labels = {
        "exact_statevector": "exact",
        "quimb_gpu_all": "GPU MPS",
        "quimb_cpu_all": "CPU MPS",
        "quimb_rcm_cpu": "RCM MPS",
        "quimb_mst_cpu": "MST MPS",
        "quimb_degree_cpu": "degree MPS",
        "quimb_mid_cpu": "mid MPS",
        "quimb_fast_cpu": "fast MPS",
        "quimb_identity_cpu": "identity MPS",
        "peaked_mpo_unswap_gpu": "MPO unswap",
        "aer_mps_pilot": "Aer pilot",
    }
    return labels.get(source or "", source or "blank")


def load_candidates() -> list[dict[str, str]]:
    with CANDIDATES.open(newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def load_evidence_rows() -> list[dict[str, Any]]:
    if not EVIDENCE.exists():
        return []
    return json.loads(EVIDENCE.read_text())


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def selected_json_path(row: dict[str, str]) -> Path | None:
    label = row["challenge"]
    source = row["source"]
    candidates = {
        "quimb_gpu_all": ROOT / "outputs" / "tree_tensor_sim" / "all" / "json" / f"challenge-{label}.quimb_tree_graph_mps.json",
        "quimb_cpu_all": ROOT / "outputs" / "tree_tensor_sim" / "all_cpu" / "json" / f"challenge-{label}.quimb_tree_graph_mps.json",
        "quimb_rcm_cpu": ROOT / "outputs" / "tree_tensor_sim" / "rcm_cpu" / "json" / f"challenge-{label}.quimb_tree_graph_mps.json",
        "quimb_degree_cpu": ROOT / "outputs" / "tree_tensor_sim" / "degree_cpu" / "json" / f"challenge-{label}.quimb_tree_graph_mps.json",
        "quimb_fast_cpu": ROOT / "outputs" / "tree_tensor_sim" / "fast_cpu" / "json" / f"challenge-{label}.quimb_tree_graph_mps.json",
        "peaked_mpo_unswap_gpu": ROOT / "outputs" / "tree_tensor_sim" / "peaked_unswap_gpu" / "json" / f"challenge-{label}.peaked_mpo_unswap.json",
    }
    path = candidates.get(source)
    return path if path and path.exists() else None


def sampling_top(data: dict[str, Any]) -> tuple[list[str], list[int], int]:
    sampling = data.get("sampling") or {}
    if data.get("method") == "peaked_mpo_unswap":
        top = sampling.get("top") or []
        labels = [(item.get("permuted_measurement_order") or item.get("raw_site_order") or "")[::-1] for item in top]
        counts = [int(item.get("count") or 0) for item in top]
        total = int(sampling.get("samples") or sum(counts) or 1)
        return labels, counts, total
    top = sampling.get("top_qiskit_order") or []
    labels = [item.get("bitstring") or "" for item in top]
    counts = [int(item.get("count") or 0) for item in top]
    total = int(sampling.get("observed_samples") or sum(counts) or 1)
    return labels, counts, total


def shorten_bits(bits: str, width: int = 18) -> str:
    if len(bits) <= width:
        return bits
    head = max(6, width // 2)
    tail = max(6, width - head - 1)
    return f"{bits[:head]}...{bits[-tail:]}"


def plot_source_counts(rows: list[dict[str, str]]) -> None:
    solved = [r for r in rows if r.get("candidate")]
    counts = collections.Counter(source_label(r.get("source", "")) for r in solved)
    order = [k for k, _ in counts.most_common()]
    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    colors = ["#3b6ea8", "#5aa469", "#d49a3a", "#8b6bb1", "#a64b4b", "#668c8c"]
    ax.bar(order, [counts[k] for k in order], color=colors[: len(order)])
    ax.set_ylabel("selected candidates")
    ax.set_title("Selected answer sources")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIG / "coverage_by_source.png", dpi=180)
    plt.close(fig)


def plot_fraction_runtime(rows: list[dict[str, str]]) -> None:
    solved = [r for r in rows if r.get("candidate")]
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.6))
    marker_by_source = {
        "exact_statevector": "o",
        "quimb_gpu_all": "s",
        "quimb_cpu_all": "^",
        "quimb_rcm_cpu": "D",
        "aer_mps_pilot": "x",
    }
    color_by_source = {
        "exact_statevector": "#2f5f8f",
        "quimb_gpu_all": "#4f8f55",
        "quimb_cpu_all": "#c1782d",
        "quimb_rcm_cpu": "#7b5aa6",
        "aer_mps_pilot": "#9a4949",
    }
    for source, group in collections.defaultdict(list, {s: [] for s in []}).items():
        pass
    grouped: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for r in solved:
        grouped[r.get("source", "")].append(r)
    for source, group in grouped.items():
        xs = [int(r["qubits"]) for r in group]
        ys = [float(r["top_fraction"] or 0.0) for r in group]
        axes[0].scatter(xs, ys, label=source_label(source), marker=marker_by_source.get(source, "o"), color=color_by_source.get(source, "#666666"), s=40, alpha=0.85)
        rt_x = []
        rt_y = []
        for r in group:
            try:
                sec = float(r["seconds"])
            except Exception:
                continue
            if sec > 0:
                rt_x.append(int(r["qubits"]))
                rt_y.append(sec)
        if rt_x:
            axes[1].scatter(rt_x, rt_y, label=source_label(source), marker=marker_by_source.get(source, "o"), color=color_by_source.get(source, "#666666"), s=40, alpha=0.85)
    axes[0].set_xlabel("qubits")
    axes[0].set_ylabel("selected top fraction")
    axes[0].set_yscale("log")
    axes[0].set_title("Peak strength of selected evidence")
    axes[0].grid(alpha=0.25)
    axes[1].set_xlabel("qubits")
    axes[1].set_ylabel("runtime seconds")
    axes[1].set_yscale("log")
    axes[1].set_title("Runtime of selected evidence")
    axes[1].grid(alpha=0.25)
    axes[1].legend(fontsize=8, loc="best")
    fig.tight_layout()
    fig.savefig(FIG / "top_fraction_runtime.png", dpi=180)
    plt.close(fig)


def plot_distributions() -> None:
    examples = [
        ("16_28", ROOT / "outputs/tree_tensor_sim/peaked_unswap_gpu/json/challenge-16_28.peaked_mpo_unswap.json", "MPO unswap validation"),
        ("40_17", ROOT / "outputs/tree_tensor_sim/all/json/challenge-40_17.quimb_tree_graph_mps.json", "easy GPU MPS"),
        ("56_39", ROOT / "outputs/tree_tensor_sim/all/json/challenge-56_39.quimb_tree_graph_mps.json", "hard GPU MPS"),
        ("56_38", ROOT / "outputs/tree_tensor_sim/rcm_cpu/json/challenge-56_38.quimb_tree_graph_mps.json", "hard RCM fallback"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(10.0, 6.6))
    for ax, (label, path, title) in zip(axes.ravel(), examples):
        data = read_json(path)
        if not data:
            ax.axis("off")
            ax.set_title(f"{label}: missing")
            continue
        bits, counts, total = sampling_top(data)
        bits = bits[:8]
        counts = counts[:8]
        fracs = [c / total for c in counts]
        xs = list(range(len(fracs)))
        ax.bar(xs, fracs, color="#4f8f55")
        ax.set_xticks(xs)
        ax.set_xticklabels([shorten_bits(b, 15) for b in bits], rotation=45, ha="right", fontsize=7)
        ax.set_ylabel("sample fraction")
        ax.set_title(f"{label}: {title}")
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIG / "sample_distributions.png", dpi=180)
    plt.close(fig)


def write_tex_fragments(rows: list[dict[str, str]]) -> None:
    solved = [r for r in rows if r.get("candidate")]
    unresolved = [r for r in rows if not r.get("candidate")]
    source_counts = collections.Counter(r["source"] for r in solved)
    difficulty_counts: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        difficulty_counts[r["difficulty"]][1] += 1
        if r.get("candidate"):
            difficulty_counts[r["difficulty"]][0] += 1

    lines = [
        r"\newcommand{\ReportGenerated}{" + tex_escape(time.strftime("%Y-%m-%d %H:%M:%S %Z")) + "}",
        r"\newcommand{\SelectedCount}{" + str(len(solved)) + "}",
        r"\newcommand{\TotalCount}{" + str(len(rows)) + "}",
        r"\newcommand{\UnresolvedList}{" + tex_escape(", ".join(r["challenge"] for r in unresolved)) + "}",
        "",
        r"\begin{tabular}{lrr}",
        r"\toprule",
        r"Difficulty & selected & total \\",
        r"\midrule",
    ]
    for diff in sorted(difficulty_counts):
        selected, total = difficulty_counts[diff]
        lines.append(f"{tex_escape(diff)} & {selected} & {total} \\\\")
    lines.extend([r"\bottomrule", r"\end{tabular}", "", r"\bigskip", ""])

    lines.extend([r"\begin{tabular}{lr}", r"\toprule", r"Source & selected \\ ", r"\midrule"])
    for source, count in source_counts.most_common():
        lines.append(f"{tex_escape(source_label(source))} & {count} \\\\")
    lines.extend([r"\bottomrule", r"\end{tabular}", "", r"\bigskip", ""])

    lines.extend(
        [
            r"\begin{longtable}{p{0.10\linewidth}p{0.12\linewidth}rp{0.39\linewidth}p{0.13\linewidth}r}",
            r"\caption{Current candidate rollup. Empty candidate rows are unresolved at report time.}\\",
            r"\toprule",
            r"Challenge & difficulty & q & candidate & source & top frac \\",
            r"\midrule",
            r"\endfirsthead",
            r"\toprule",
            r"Challenge & difficulty & q & candidate & source & top frac \\",
            r"\midrule",
            r"\endhead",
        ]
    )
    for r in rows:
        top = ""
        if r.get("top_fraction"):
            try:
                top = f"{float(r['top_fraction']):.4g}"
            except Exception:
                top = tex_escape(r["top_fraction"])
        lines.append(
            f"\\texttt{{{tex_escape(r['challenge'])}}} & {tex_escape(r['difficulty'])} & {int(r['qubits'])} & "
            f"{bits_cell(r.get('candidate', ''))} & {tex_escape(source_label(r.get('source', '')))} & {top} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{longtable}"])

    (OUT / "report_data.tex").write_text("\n".join(lines) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    rows = load_candidates()
    plot_source_counts(rows)
    plot_fraction_runtime(rows)
    plot_distributions()
    write_tex_fragments(rows)


if __name__ == "__main__":
    main()
