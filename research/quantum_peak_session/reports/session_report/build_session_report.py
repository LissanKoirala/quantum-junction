#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import math
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "session_report"
FIG = OUT / "figures"
TEX = OUT / "quantum_junction_session_report.tex"

DIFF_ORDER = ["very easy", "easy", "moderate", "hard", "very_hard"]
DIFF_LABEL = {
    "very easy": "very easy",
    "easy": "easy",
    "moderate": "moderate",
    "hard": "hard",
    "very_hard": "very hard",
}


def latex_escape(s: Any) -> str:
    text = "" if s is None or (isinstance(s, float) and math.isnan(s)) else str(s)
    return (
        text.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("$", r"\$")
        .replace("#", r"\#")
        .replace("_", r"\_")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("~", r"\textasciitilde{}")
        .replace("^", r"\textasciicircum{}")
    )


def bit_tex(bits: Any, group: int = 8) -> str:
    if bits is None or (isinstance(bits, float) and math.isnan(bits)) or bits == "":
        return ""
    s = str(bits)
    return r"\texttt{\scriptsize " + r"\allowbreak ".join(s[i : i + group] for i in range(0, len(s), group)) + "}"


def short_bits(bits: str, head: int = 10, tail: int = 8) -> str:
    if len(bits) <= head + tail + 3:
        return bits
    return f"{bits[:head]}...{bits[-tail:]}"


def read_json(path: Path) -> dict[str, Any] | list[Any]:
    return json.loads(path.read_text())


def to_float(x: Any) -> float | None:
    if x in ("", None):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(v):
        return None
    return v


def source_label(source: str) -> str:
    labels = {
        "exact_statevector": "exact",
        "quimb_gpu_all": "quimb GPU",
        "quimb_opt_u3_gpu": "opt-U3 GPU",
        "quimb_cpu_all": "quimb CPU",
        "quimb_rcm_cpu": "RCM CPU",
        "quimb_mst_cpu": "MST CPU",
        "quimb_degree_cpu": "degree CPU",
        "quimb_mid_cpu": "mid CPU",
        "quimb_fast_cpu": "fast CPU",
        "quimb_identity_cpu": "identity CPU",
        "aer_mps_pilot": "Aer MPS",
        "peaked_mpo_unswap_gpu": "MPO unswap",
        "sparse_beam": "sparse beam",
    }
    return labels.get(source, source.replace("_", " "))


def read_inputs() -> tuple[pd.DataFrame, list[dict[str, Any]], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candidates = pd.read_csv(ROOT / "outputs/tree_tensor_sim/collector_current/CANDIDATES.tsv", sep="\t")
    evidence = read_json(ROOT / "outputs/tree_tensor_sim/collector_current/CANDIDATE_EVIDENCE.json")
    static_summary = pd.read_csv(ROOT / "agent_work/static_forensics/difficulty_summary.csv")
    exact = pd.read_csv(ROOT / "agent_work/exact_baseline/peaks_exact.csv")
    opt = pd.read_csv(ROOT / "outputs/tree_tensor_sim/optimized_qasm/stats/remaining_transpile_stats.tsv", sep="\t")
    per_file = pd.read_csv(ROOT / "agent_work/static_forensics/per_file_metrics.csv")
    return candidates, evidence, static_summary, exact, opt, per_file


def plot_coverage(candidates: pd.DataFrame) -> None:
    rows = []
    for diff in DIFF_ORDER:
        sub = candidates[candidates["difficulty"] == diff]
        rows.append((DIFF_LABEL[diff], int(sub["candidate"].notna().sum()), int(sub["candidate"].isna().sum())))
    labels, solved, missing = zip(*rows)
    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.bar(labels, solved, label="selected", color="#2f6f8f")
    ax.bar(labels, missing, bottom=solved, label="blank", color="#c8c8c8")
    ax.set_ylabel("challenges")
    ax.set_title("Coverage by difficulty")
    for i, (s, m) in enumerate(zip(solved, missing)):
        ax.text(i, s / 2 if s else 0.1, str(s), ha="center", va="center", color="white", fontsize=9)
        if m:
            ax.text(i, s + m / 2, str(m), ha="center", va="center", color="#333333", fontsize=9)
    ax.legend(loc="upper left", ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "coverage_by_difficulty.pdf")
    plt.close(fig)


def plot_source_counts(candidates: pd.DataFrame) -> None:
    solved = candidates[candidates["candidate"].notna()].copy()
    solved["source_label"] = solved["source"].map(source_label)
    counts = solved["source_label"].value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.barh(counts.index, counts.values, color="#6a8f3a")
    ax.set_xlabel("selected candidates")
    ax.set_title("Winning source for selected candidates")
    for y, v in enumerate(counts.values):
        ax.text(v + 0.2, y, str(v), va="center", fontsize=9)
    ax.set_xlim(0, max(counts.values) + 3)
    fig.tight_layout()
    fig.savefig(FIG / "selected_source_counts.pdf")
    plt.close(fig)


def plot_top_fraction(candidates: pd.DataFrame) -> None:
    solved = candidates[candidates["candidate"].notna()].copy()
    solved["top_fraction"] = pd.to_numeric(solved["top_fraction"], errors="coerce")
    solved["difficulty_label"] = solved["difficulty"].map(DIFF_LABEL)
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    colors = {"exact": "#2f6f8f", "unknown": "#9a6b2f", "unstable_top1_vs_aggregate": "#9a2f4f"}
    for i, diff in enumerate(DIFF_ORDER):
        vals = solved[solved["difficulty"] == diff]
        xs = [i + (j - (len(vals) - 1) / 2) * 0.035 for j in range(len(vals))]
        cs = [colors.get(str(v), "#666666") for v in vals["validation"].fillna("")]
        ax.scatter(xs, vals["top_fraction"], c=cs, s=28, alpha=0.85, edgecolors="white", linewidths=0.4)
    ax.set_yscale("log")
    ax.set_xticks(range(len(DIFF_ORDER)), [DIFF_LABEL[d] for d in DIFF_ORDER])
    ax.set_ylabel("top fraction (log scale)")
    ax.set_title("Observed peak concentration for selected candidates")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIG / "top_fraction_by_difficulty.pdf")
    plt.close(fig)


def plot_static_gates(static_summary: pd.DataFrame) -> None:
    df = static_summary.set_index("difficulty").loc[DIFF_ORDER]
    labels = [DIFF_LABEL[d] for d in DIFF_ORDER]
    rx = df["op_rx_mean"].to_numpy()
    rz = df["op_rz_mean"].to_numpy()
    cx = df["op_cx_mean"].to_numpy()
    sw = df["op_swap_mean"].to_numpy()
    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    ax.bar(labels, rx, label="rx", color="#3f7f93")
    ax.bar(labels, rz, bottom=rx, label="rz", color="#a06a2b")
    ax.bar(labels, cx, bottom=rx + rz, label="cx", color="#6b5fa8")
    ax.bar(labels, sw, bottom=rx + rz + cx, label="swap", color="#7a7a7a")
    ax.set_ylabel("mean gate count")
    ax.set_title("Mean QASM size by difficulty")
    ax.legend(ncol=4, frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "gate_counts_by_difficulty.pdf")
    plt.close(fig)


def plot_runtime(candidates: pd.DataFrame) -> None:
    solved = candidates[candidates["candidate"].notna()].copy()
    solved["seconds"] = pd.to_numeric(solved["seconds"], errors="coerce")
    solved["max_bond"] = pd.to_numeric(solved["max_bond"], errors="coerce")
    solved = solved[solved["seconds"].notna()]
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    for source, grp in solved.groupby("source"):
        ax.scatter(grp["qubits"], grp["seconds"], s=35, label=source_label(source), alpha=0.85)
    ax.set_yscale("log")
    ax.set_xlabel("qubits")
    ax.set_ylabel("runtime seconds (log)")
    ax.set_title("Runtime of winning non-exact selected runs")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=7, frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(FIG / "runtime_by_qubits.pdf")
    plt.close(fig)


def plot_exact_distribution(exact: pd.DataFrame) -> None:
    df = exact.sort_values(["qubits", "challenge"]).copy()
    rest = 1.0 - df["peak_probability"] - df["second_probability"]
    labels = df["challenge"].tolist()
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    ax.bar(labels, df["peak_probability"], label="peak", color="#2f6f8f")
    ax.bar(labels, df["second_probability"], bottom=df["peak_probability"], label="second", color="#d19a3a")
    ax.bar(labels, rest, bottom=df["peak_probability"] + df["second_probability"], label="remaining mass", color="#d0d0d0")
    ax.set_ylabel("probability mass")
    ax.set_title("Exact statevector distribution summary")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(ncol=3, frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "exact_peak_mass.pdf")
    plt.close(fig)


def plot_u3_reduction(opt: pd.DataFrame) -> None:
    df = opt.copy()
    df["reduction_pct"] = 100 * (1 - df["u3_len"] / df["orig_len"])
    fig, ax1 = plt.subplots(figsize=(7.5, 3.9))
    x = range(len(df))
    ax1.bar([i - 0.18 for i in x], df["orig_len"], width=0.36, label="original", color="#7f7f7f")
    ax1.bar([i + 0.18 for i in x], df["u3_len"], width=0.36, label="U3 optimized", color="#2f6f8f")
    ax1.set_xticks(list(x), df["label"], rotation=45, ha="right")
    ax1.set_ylabel("gate count")
    ax2 = ax1.twinx()
    ax2.plot(list(x), df["reduction_pct"], color="#9a2f4f", marker="o", label="reduction")
    ax2.set_ylabel("reduction %")
    ax1.set_title("Optimized-U3 reduction for remaining blanks")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "u3_reduction_remaining.pdf")
    plt.close(fig)


def sample_rows_from_json(path: Path, mode: str) -> tuple[str, list[tuple[str, float]]]:
    data = read_json(path)
    label = data.get("challenge_label", path.stem)
    if mode == "quimb":
        sampling = data.get("sampling", {})
        rows = []
        total = to_float(sampling.get("observed_samples") or sampling.get("samples")) or 1.0
        for item in sampling.get("top_qiskit_order", [])[:10]:
            rows.append((short_bits(item["bitstring"], 8, 6), float(item["count"]) / total))
        return label, rows
    if mode == "unswap":
        sampling = data.get("sampling", {})
        rows = []
        for item in sampling.get("top", [])[:10]:
            bits = item.get("permuted_measurement_order", "")
            qiskit_bits = bits[::-1] if bits else item.get("raw_site_order", "")
            rows.append((short_bits(qiskit_bits, 8, 6), float(item.get("fraction", 0.0))))
        return label, rows
    raise ValueError(mode)


def plot_sample_distributions() -> None:
    specs = [
        ("56_24 Quimb GPU", ROOT / "outputs/tree_tensor_sim/all/json/challenge-56_24.quimb_tree_graph_mps.json", "quimb"),
        ("64_25 Quimb GPU", ROOT / "outputs/tree_tensor_sim/all/json/challenge-64_25.quimb_tree_graph_mps.json", "quimb"),
        ("48_31 Quimb CPU", ROOT / "outputs/tree_tensor_sim/all_cpu/json/challenge-48_31.quimb_tree_graph_mps.json", "quimb"),
        ("16_28 MPO unswap", ROOT / "outputs/tree_tensor_sim/peaked_unswap_gpu/json/challenge-16_28.peaked_mpo_unswap.json", "unswap"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(8, 6.2))
    for ax, (title, path, mode) in zip(axes.ravel(), specs):
        if not path.exists():
            ax.set_axis_off()
            continue
        _, rows = sample_rows_from_json(path, mode)
        labels = [r[0] for r in rows]
        vals = [r[1] for r in rows]
        ax.bar(range(len(vals)), vals, color="#2f6f8f")
        ax.set_title(title, fontsize=10)
        ax.set_ylabel("sample fraction")
        ax.set_xticks(range(len(vals)), labels, rotation=60, ha="right", fontsize=6)
        ax.set_ylim(0, max(vals + [0.01]) * 1.18)
    fig.suptitle("Representative sampled output distributions", y=0.995)
    fig.tight_layout()
    fig.savefig(FIG / "sample_distribution_examples.pdf")
    plt.close(fig)


def plot_sparse_beam() -> None:
    path = ROOT / "outputs/tree_tensor_sim/sparse_beam/json/challenge-16_28.beam20000.json"
    if not path.exists():
        return
    data = read_json(path)
    rows = data.get("top", [])[:8]
    exact = "1101001111011100"
    weights = [float(r.get("weight", 0.0)) for r in rows]
    labels = [str(r.get("rank", i + 1)) for i, r in enumerate(rows)]
    colors = ["#9a2f4f" if r.get("bitstring") == exact else "#2f6f8f" for r in rows]
    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    ax.bar(labels, weights, color=colors)
    ax.set_xlabel("beam rank")
    ax.set_ylabel("retained weight")
    ax.set_title("Sparse beam calibration on known 16_28")
    ax.text(0.98, 0.92, "exact answer rank 3", ha="right", va="top", transform=ax.transAxes, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / "sparse_beam_calibration.pdf")
    plt.close(fig)


def plot_forensics_similarity() -> None:
    path = ROOT / "agent_work/static_forensics/operation_similarity_by_difficulty.csv"
    df = pd.read_csv(path)
    pivot = pd.DataFrame(index=DIFF_ORDER, columns=DIFF_ORDER, dtype=float)
    for _, row in df.iterrows():
        a, b = row["difficulty_a"], row["difficulty_b"]
        pivot.loc[a, b] = row["mean_op_5gram_cosine"]
        pivot.loc[b, a] = row["mean_op_5gram_cosine"]
    fig, ax = plt.subplots(figsize=(5.4, 4.2))
    im = ax.imshow(pivot.to_numpy(dtype=float), vmin=0.4, vmax=1.0, cmap="viridis")
    ax.set_xticks(range(len(DIFF_ORDER)), [DIFF_LABEL[d] for d in DIFF_ORDER], rotation=45, ha="right")
    ax.set_yticks(range(len(DIFF_ORDER)), [DIFF_LABEL[d] for d in DIFF_ORDER])
    for i in range(len(DIFF_ORDER)):
        for j in range(len(DIFF_ORDER)):
            ax.text(j, i, f"{pivot.iloc[i, j]:.2f}", ha="center", va="center", color="white", fontsize=8)
    ax.set_title("Operation 5-gram similarity")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(FIG / "operation_similarity_heatmap.pdf")
    plt.close(fig)


def make_plots(candidates: pd.DataFrame, static_summary: pd.DataFrame, exact: pd.DataFrame, opt: pd.DataFrame) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    plt.style.use("default")
    plot_coverage(candidates)
    plot_source_counts(candidates)
    plot_top_fraction(candidates)
    plot_static_gates(static_summary)
    plot_runtime(candidates)
    plot_exact_distribution(exact)
    plot_u3_reduction(opt)
    plot_sample_distributions()
    plot_sparse_beam()
    plot_forensics_similarity()


def evidence_stats(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    source_attempts = Counter()
    source_ok = Counter()
    agreement_pairs = 0
    for row in evidence:
        evs = row.get("evidence") or []
        for ev in evs:
            source_attempts[ev.get("source", "")] += 1
            if ev.get("candidate"):
                source_ok[ev.get("source", "")] += 1
        candidates = [ev.get("candidate") for ev in evs if ev.get("candidate")]
        if len(candidates) >= 2 and len(set(candidates)) == 1:
            agreement_pairs += 1
    return {"source_attempts": source_attempts, "source_ok": source_ok, "agreement_rows": agreement_pairs}


def active_slurm_table() -> list[list[str]]:
    try:
        proc = subprocess.run(
            ["squeue", "-u", subprocess.check_output(["whoami"], text=True).strip(), "-h", "-o", "%i|%T|%M|%C|%j|%R"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        return []
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.split("|")
        if len(parts) >= 6:
            rows.append(parts[:6])
    return rows


def selected_table_rows(candidates: pd.DataFrame) -> str:
    lines = []
    order_key = {d: i for i, d in enumerate(DIFF_ORDER)}
    df = candidates.copy()
    df["_order"] = df["difficulty"].map(order_key)
    df = df.sort_values(["_order", "qubits", "challenge"])
    for _, r in df.iterrows():
        cand = r.get("candidate")
        top = to_float(r.get("top_fraction"))
        top_s = "" if top is None else f"{top:.4g}"
        source = "" if pd.isna(r.get("source")) else source_label(str(r.get("source")))
        validation = "" if pd.isna(r.get("validation")) else str(r.get("validation"))
        lines.append(
            " & ".join(
                [
                    latex_escape(r["challenge"]),
                    latex_escape(DIFF_LABEL.get(r["difficulty"], r["difficulty"])),
                    str(int(r["qubits"])),
                    bit_tex(cand),
                    latex_escape(source),
                    latex_escape(validation),
                    latex_escape(top_s),
                    latex_escape("" if pd.isna(r.get("evidence_count")) else int(r.get("evidence_count"))),
                ]
            )
            + r" \\"
        )
    return "\n".join(lines)


def method_summary_table(candidates: pd.DataFrame, evidence: list[dict[str, Any]]) -> str:
    solved = candidates[candidates["candidate"].notna()].copy()
    win_counts = Counter(solved["source"].fillna(""))
    stats = evidence_stats(evidence)
    sources = sorted(set(win_counts) | set(stats["source_ok"]))
    lines = []
    for src in sources:
        if not src:
            continue
        lines.append(
            f"{latex_escape(source_label(src))} & {win_counts.get(src, 0)} & {stats['source_ok'].get(src, 0)} & {stats['source_attempts'].get(src, 0)} \\\\"
        )
    return "\n".join(lines)


def weak_table(candidates: pd.DataFrame) -> str:
    df = candidates[candidates["candidate"].notna()].copy()
    df["top_fraction"] = pd.to_numeric(df["top_fraction"], errors="coerce")
    df = df[(df["top_fraction"].fillna(1.0) < 0.02) | (df["evidence_count"].fillna(0) <= 1)]
    df = df.sort_values(["difficulty", "qubits", "challenge"])
    lines = []
    for _, r in df.iterrows():
        top = to_float(r.get("top_fraction"))
        lines.append(
            " & ".join(
                [
                    latex_escape(r["challenge"]),
                    latex_escape(DIFF_LABEL.get(r["difficulty"], r["difficulty"])),
                    latex_escape(source_label(str(r["source"]))),
                    latex_escape("" if top is None else f"{top:.4g}"),
                    latex_escape(int(r.get("evidence_count", 0))),
                    bit_tex(r["candidate"]),
                ]
            )
            + r" \\"
        )
    return "\n".join(lines) if lines else r"\multicolumn{6}{l}{No weak selected rows under the report threshold.}\\"


def exact_table(exact: pd.DataFrame) -> str:
    df = exact.sort_values(["qubits", "challenge"])
    lines = []
    for _, r in df.iterrows():
        lines.append(
            f"{latex_escape(r['challenge'])} & {int(r['qubits'])} & {bit_tex(r['peak_bitstring'])} & "
            f"{float(r['peak_probability']):.4f} & {float(r['second_probability']):.4f} & {float(r['gap_to_second']):.4f} \\\\"
        )
    return "\n".join(lines)


def opt_table(opt: pd.DataFrame) -> str:
    lines = []
    for _, r in opt.iterrows():
        reduction = 100 * (1 - int(r["u3_len"]) / int(r["orig_len"]))
        lines.append(
            f"{latex_escape(r['label'])} & {int(r['q'])} & {int(r['orig_len'])} & {int(r['u3_len'])} & {reduction:.1f}\\% \\\\"
        )
    return "\n".join(lines)


def active_jobs_tex(rows: list[list[str]]) -> str:
    if not rows:
        return r"\multicolumn{6}{l}{No active Slurm jobs at report build time.}\\"
    lines = []
    for jobid, state, elapsed, cpus, name, reason in rows:
        lines.append(
            f"{latex_escape(jobid)} & {latex_escape(state)} & {latex_escape(elapsed)} & {latex_escape(cpus)} & {latex_escape(name)} & {latex_escape(reason)} \\\\"
        )
    return "\n".join(lines)


def build_tex(candidates: pd.DataFrame, evidence: list[dict[str, Any]], static_summary: pd.DataFrame, exact: pd.DataFrame, opt: pd.DataFrame) -> None:
    solved_n = int(candidates["candidate"].notna().sum())
    total_n = len(candidates)
    missing = candidates[candidates["candidate"].isna()]["challenge"].tolist()
    source_counts = Counter(candidates[candidates["candidate"].notna()]["source"].fillna(""))
    exact_n = source_counts.get("exact_statevector", 0)
    gpu_n = source_counts.get("quimb_gpu_all", 0)
    cpu_n = source_counts.get("quimb_cpu_all", 0)
    rcm_n = source_counts.get("quimb_rcm_cpu", 0)
    active_rows = active_slurm_table()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    exact_peak_mean = exact["peak_probability"].mean()
    exact_gap_mean = exact["gap_to_second"].mean()

    body = rf"""
\documentclass[10pt]{{article}}
\usepackage[margin=0.7in]{{geometry}}
\usepackage{{graphicx}}
\usepackage{{booktabs}}
\usepackage{{longtable}}
\usepackage{{array}}
\usepackage{{hyperref}}
\usepackage{{xcolor}}
\usepackage{{float}}
\usepackage{{caption}}
\usepackage{{pdfpages}}
\hypersetup{{colorlinks=true, linkcolor=blue, urlcolor=blue}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{4pt}}
\renewcommand{{\arraystretch}}{{1.12}}

\title{{Quantum Junction Challenge: Condensed Codex Session Report}}
\author{{Codex run summary}}
\date{{Built {latex_escape(now)}}}

\begin{{document}}
\maketitle

\section*{{Executive Summary}}
The session produced selected peak bitstrings for \textbf{{{solved_n}/{total_n}}} challenge files. The remaining blanks are
\texttt{{{latex_escape(", ".join(missing))}}}. The selected set contains \textbf{{{exact_n}}} exact statevector answers and
\textbf{{{solved_n - exact_n}}} tensor-network or MPS-derived candidates. Among the approximate selected rows, \textbf{{{gpu_n}}}
are from the canonical Quimb GPU pass, \textbf{{{cpu_n}}} from canonical Quimb CPU, and \textbf{{{rcm_n}}} from an RCM-order CPU
fallback. Exact statevector peaks had mean peak probability {exact_peak_mean:.3f} and mean gap to the second bitstring
{exact_gap_mean:.3f}.

The main result is a usable candidate set, not a proof of correctness for every approximate row. Easy and moderate
instances often had large sampled peak fractions and/or corroborating evidence. Several hard rows are weak: they were
selected because they were the best available evidence, but their sampled top fractions are near one or two samples out of
512/1024. The session later pivoted away from long-running graph-MPS sweeps after the user set a practical
``about 2 hours'' per-attempt budget.

\section*{{Candidate Selection Rule}}
The collector selected one answer per challenge using source priority, then evidence consistency. The priority order used in
the current collector was: exact statevector, canonical Quimb GPU, optimized-U3 GPU, canonical Quimb CPU, MPO-unswap, RCM/MST/
degree/mid/fast/identity CPU fallbacks, sparse beam, and low-priority Aer MPS pilot evidence. Exact answers were accepted
directly. Approximate answers were chosen as sampled top bitstrings in Qiskit/counts order, with the right-most bit
corresponding to qubit 0. When multiple methods agreed on the same bitstring, the report records that as higher evidence
count.

\begin{{figure}}[H]
\centering
\includegraphics[width=0.48\linewidth]{{figures/coverage_by_difficulty.pdf}}
\includegraphics[width=0.48\linewidth]{{figures/selected_source_counts.pdf}}
\caption{{Coverage and winning evidence sources. The nine missing rows are all hard or very hard.}}
\end{{figure}}

\section*{{What Was Tried}}
\begin{{longtable}}{{p{{0.22\linewidth}} p{{0.51\linewidth}} p{{0.22\linewidth}}}}
\toprule
Method & Purpose and implementation & Outcome \\
\midrule
Exact statevector & Used Aer/statevector on small enough circuits to establish ground-truth peaks and bit ordering. & 10 exact answers. Used as calibration and highest-priority evidence. \\
Canonical graph/tree MPS & Ran Quimb tree-ordered MPS sampling on CPU and GPU, using sampled top bitstrings as candidate peaks. & Main source of approximate answers; strong on many easy/moderate rows and weak but usable on some hard rows. \\
Ordering fallbacks & Tried RCM, MST, degree, mid, fast, and identity orderings to change contraction behavior. & Added corroboration; RCM supplied the selected 56\_38 weak candidate. Long jobs were later cancelled. \\
Sparse computational-basis beam & Added a C++ top-K sparse branch propagator through RX/RZ/CX. & Rejected for answer selection: on known 16\_28 the exact answer was only rank 3. \\
Static QASM forensics & Counted gates, angle classes, pair repetitions, connectivity, leading one-qubit prefixes, and operation 5-gram similarity. & Confirmed all circuits are RX/RZ/CX/SWAP style, very-hard files are a distinct dense-obfuscation regime, and Clifford shortcuts are not appropriate. \\
Optimized-U3 transpilation & Transpiled the remaining blanks to U3+CX to reduce single-qubit gate count. & Reduced total gate count by roughly 39--42\% on blanks; not yet selected as evidence. \\
MPO unswapping & Patched the local Kremer-Dupuis style MPO cancellation/unswapping code: parameterized SABRE trials, fixed Quimb local expectation API, fixed quantum-op progress counting. & Calibrated on known 16\_28 in 93.26 s and recovered the exact answer. Unresolved runs were still active at report build time and are not counted as solved. \\
\bottomrule
\end{{longtable}}

\section*{{Static Structure}}
The QASM files use only \texttt{{rx}}, \texttt{{rz}}, \texttt{{cx}}, and sparse \texttt{{swap}} gates. Very-hard instances are
much larger and more internally similar to each other than to the easier sets. They also have dense leading single-qubit
prefixes and high all-to-all pair coverage. This drove the pivot toward structure-aware MPO cancellation rather than only
waiting for generic graph-MPS contractions.

\begin{{figure}}[H]
\centering
\includegraphics[width=0.48\linewidth]{{figures/gate_counts_by_difficulty.pdf}}
\includegraphics[width=0.42\linewidth]{{figures/operation_similarity_heatmap.pdf}}
\caption{{Static QASM summary. Very-hard files are large and operation-sequence-similar to each other.}}
\end{{figure}}

\section*{{Exact Baseline}}
The exact rows were used both as final answers and as calibration targets. The peak is visibly separated from the runner-up
on these cases, which made them useful for validating bit order and method behavior.

\begin{{figure}}[H]
\centering
\includegraphics[width=0.78\linewidth]{{figures/exact_peak_mass.pdf}}
\caption{{Exact statevector probability mass: peak, second-largest bitstring, and remaining mass.}}
\end{{figure}}

\begin{{longtable}}{{l r p{{0.36\linewidth}} r r r}}
\toprule
Challenge & q & exact peak & peak prob. & second prob. & gap \\
\midrule
{exact_table(exact)}
\bottomrule
\end{{longtable}}

\section*{{Approximate Tensor-Network Results}}
For approximate rows, the sampled top fraction was the main confidence signal. Strong rows have a clear heavy bitstring.
Weak hard rows are retained because they are currently the best available candidates, but they should be interpreted as
low-confidence until corroborated.

\begin{{figure}}[H]
\centering
\includegraphics[width=0.48\linewidth]{{figures/top_fraction_by_difficulty.pdf}}
\includegraphics[width=0.48\linewidth]{{figures/runtime_by_qubits.pdf}}
\caption{{Peak concentration and runtime for selected rows. The hard set contains several low-concentration candidates.}}
\end{{figure}}

\begin{{figure}}[H]
\centering
\includegraphics[width=0.86\linewidth]{{figures/sample_distribution_examples.pdf}}
\caption{{Representative sampled distributions. The first three are selected Quimb candidates; the fourth is the MPO-unswap validation on 16\_28.}}
\end{{figure}}

\subsection*{{Weak Selected Rows}}
\begin{{longtable}}{{l l l r r p{{0.35\linewidth}}}}
\toprule
Challenge & difficulty & source & top frac. & evidence & candidate \\
\midrule
{weak_table(candidates)}
\bottomrule
\end{{longtable}}

\section*{{Rejected or Not-Yet-Selected Paths}}
The sparse beam search was attractive because it was fast, but its pruning bias failed calibration. In known 16\_28, the exact
answer was rank 3 rather than rank 1, so no sparse-beam guesses were promoted to selected answers. U3 optimization reduced
the remaining blank gate counts substantially, but its GPU pass was not completed before this report snapshot.

\begin{{figure}}[H]
\centering
\includegraphics[width=0.45\linewidth]{{figures/sparse_beam_calibration.pdf}}
\includegraphics[width=0.53\linewidth]{{figures/u3_reduction_remaining.pdf}}
\caption{{Left: sparse beam failed calibration. Right: U3 optimization reduced the remaining blank circuits but was not yet selected as evidence.}}
\end{{figure}}

\begin{{longtable}}{{l r r r r}}
\toprule
Blank & q & original gates & U3 gates & reduction \\
\midrule
{opt_table(opt)}
\bottomrule
\end{{longtable}}

\section*{{Current Slurm Snapshot}}
The report is an as-of snapshot. Any active unresolved MPO-unswap jobs below were still running or pending when the PDF was built,
and their outputs are not counted in the \textbf{{{solved_n}/{total_n}}} result.

\begin{{longtable}}{{l l l r p{{0.24\linewidth}} p{{0.24\linewidth}}}}
\toprule
JobID & state & elapsed & CPUs & name & node/reason \\
\midrule
{active_jobs_tex(active_rows)}
\bottomrule
\end{{longtable}}

\section*{{Method Summary}}
\begin{{longtable}}{{l r r r}}
\toprule
Source & selected winners & candidate evidence rows & attempted evidence rows \\
\midrule
{method_summary_table(candidates, evidence)}
\bottomrule
\end{{longtable}}

\section*{{Selected Candidate Table}}
Full candidate bitstrings are shown in wrapped monospace chunks. Blank rows remain unsolved.

\scriptsize
\begin{{longtable}}{{l l r p{{0.36\linewidth}} l l r r}}
\toprule
Challenge & difficulty & q & candidate & source & validation & top frac. & evidence \\
\midrule
{selected_table_rows(candidates)}
\bottomrule
\end{{longtable}}
\normalsize

\section*{{Conclusions}}
The practical output of the session is a 40-row candidate answer set and a clear split between reliable and weak evidence.
The exact and high-top-fraction Quimb rows are the most defensible. The hard weak rows should be treated as provisional.
The best next direction is not another unconstrained graph-MPS sweep: it is bounded MPO-unswapping or optimized-U3 GPU runs
with calibration checks and immediate collector refreshes.

\input{{tables/distribution_appendix.tex}}

\end{{document}}
"""
    TEX.write_text(body)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candidates, evidence, static_summary, exact, opt, _ = read_inputs()
    make_plots(candidates, static_summary, exact, opt)
    build_tex(candidates, evidence, static_summary, exact, opt)
    print(TEX)


if __name__ == "__main__":
    main()
