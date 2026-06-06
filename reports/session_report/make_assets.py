#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shutil
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
FIG = OUT / "figures"
TAB = OUT / "tables"


def esc(text: object) -> str:
    s = "" if text is None else str(text)
    repl = {
        "\\": r"\textbackslash{}",
        "_": r"\_",
        "%": r"\%",
        "&": r"\&",
        "#": r"\#",
        "$": r"\$",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(repl.get(ch, ch) for ch in s)


def bittex(text: object) -> str:
    return r"\bitstr{" + esc(text) + "}"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def savefig(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()


def exact_results() -> list[dict]:
    return read_jsonl(ROOT / "agent_work/exact_baseline/peaks_exact_aer.jsonl")


def peaked_results() -> list[dict]:
    rows = []
    for base in [
        ROOT / "outputs/peaked_circuit_sim_pilot/json",
        ROOT / "outputs/peaked_circuit_sim_all/json",
    ]:
        if not base.exists():
            continue
        for path in sorted(base.glob("*.json")):
            data = read_json(path)
            data["_source"] = base.parent.name
            rows.append(data)
    return rows


def selected_mps_results() -> list[dict]:
    base = ROOT / "outputs/sim_11_26_34_41_49/json"
    return [read_json(path) for path in sorted(base.glob("*.mps.json"))]


def mps_distill_summary() -> list[dict]:
    path = ROOT / "agent_work/mps_distill/summaries/pilot_summary.json"
    return read_json(path)["circuits"] if path.exists() else []


def static_difficulty() -> list[dict]:
    path = ROOT / "agent_work/static_forensics/difficulty_summary.csv"
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def plot_exact_peak_probabilities() -> None:
    rows = sorted(exact_results(), key=lambda r: (r["qubits"], r["difficulty"], r["challenge"]))
    labels = [r["challenge"] for r in rows]
    probs = [r["peak_probability"] for r in rows]
    colors = {
        "very easy": "#5b8c5a",
        "easy": "#287271",
        "moderate": "#b08900",
    }
    plt.figure(figsize=(8.0, 3.8))
    plt.bar(labels, probs, color=[colors.get(r["difficulty"], "#777777") for r in rows])
    plt.ylabel("Exact peak probability")
    plt.xlabel("Challenge")
    plt.ylim(0, 1.0)
    plt.xticks(rotation=35, ha="right")
    for i, r in enumerate(rows):
        plt.text(i, probs[i] + 0.015, str(r["qubits"]), ha="center", va="bottom", fontsize=7)
    plt.title("Exact statevector peaks for circuits up to 28 qubits")
    savefig(FIG / "exact_peak_probabilities.png")


def plot_method_agreement() -> None:
    exact = {r["challenge"]: r["peak_bitstring"] for r in exact_results()}
    records = []
    for row in peaked_results():
        if row.get("status") != "ok":
            continue
        ch = row.get("challenge_label")
        pred = row.get("pred_bitstring_qiskit_order")
        if ch in exact and pred:
            hd = sum(a != b for a, b in zip(exact[ch], pred))
            records.append((ch, f"peaked/{row['_source']}", hd))
    for row in selected_mps_results():
        ch = Path(row["path"]).stem.replace("challenge-", "")
        if ch in exact and row.get("peak"):
            hd = sum(a != b for a, b in zip(exact[ch], row["peak"]))
            records.append((ch, "Aer MPS sampling", hd))
    for row in mps_distill_summary():
        ch = Path(row["circuit"]).stem.replace("challenge-", "")
        if ch in exact and row.get("candidate"):
            hd = sum(a != b for a, b in zip(exact[ch], row["candidate"]))
            records.append((ch, "MPS distill", hd))

    labels = [f"{ch}\n{method}" for ch, method, _ in records]
    values = [hd for _, _, hd in records]
    colors = ["#2a9d8f" if hd == 0 else "#c44536" for hd in values]
    plt.figure(figsize=(9.5, 4.1))
    plt.bar(range(len(records)), values, color=colors)
    plt.ylabel("Hamming distance to exact peak")
    plt.xticks(range(len(records)), labels, rotation=55, ha="right", fontsize=7)
    plt.yticks(range(0, max(values + [1]) + 1))
    plt.title("Validation of approximate methods on exact-checkable circuits")
    savefig(FIG / "method_agreement.png")


def plot_peaked_margins() -> None:
    rows = [
        r
        for r in peaked_results()
        if r.get("status") == "ok" and r.get("_source") == "peaked_circuit_sim_all"
    ]
    rows = sorted(rows, key=lambda r: (r.get("difficulty", ""), int(r.get("num_qubits", 0)), r.get("challenge_label", "")))
    labels = [r["challenge_label"] for r in rows]
    margins = [max(float(r.get("p1_margin_min") or 0), 1e-16) for r in rows]
    colors = ["#c44536" if m < 1e-3 else "#e9a03f" if m < 1e-2 else "#287271" for m in margins]
    plt.figure(figsize=(9.5, 3.9))
    plt.bar(labels, margins, color=colors)
    plt.yscale("log")
    plt.axhline(1e-3, color="#444444", linewidth=0.8, linestyle="--")
    plt.ylabel("Minimum bit margin |P(1)-0.5|")
    plt.xlabel("Peaked-circuit completed outputs")
    plt.xticks(rotation=45, ha="right", fontsize=7)
    plt.title("Marginal-threshold confidence for peaked-circuit outputs")
    savefig(FIG / "peaked_margins.png")


def plot_mps_stability() -> None:
    rows = mps_distill_summary()
    labels = [Path(r["circuit"]).stem.replace("challenge-", "") for r in rows]
    agg = [r["aggregate_rank"][0]["fraction"] for r in rows]
    votes = [r["top1_vote_fraction"] for r in rows]
    x = np.arange(len(rows))
    plt.figure(figsize=(8.5, 3.7))
    plt.bar(x - 0.18, agg, width=0.36, label="aggregate support fraction", color="#287271")
    plt.bar(x + 0.18, votes, width=0.36, label="top-1 vote fraction", color="#b08900")
    plt.ylabel("Fraction")
    plt.ylim(0, 1.05)
    plt.xticks(x, labels, rotation=35, ha="right")
    plt.legend(fontsize=8)
    plt.title("MPS sampling/distillation stability across shots, bonds, and seeds")
    savefig(FIG / "mps_stability.png")


def plot_selected_mps_counts() -> None:
    rows = selected_mps_results()
    rows = sorted(rows, key=lambda r: int(r["challenge_id"]))
    fig, axes = plt.subplots(len(rows), 1, figsize=(8.5, 8.5), sharex=False)
    if len(rows) == 1:
        axes = [axes]
    for ax, row in zip(axes, rows):
        counts = list(row.get("top_counts", {}).items())[:10]
        vals = [c for _, c in counts]
        ax.bar(range(len(vals)), vals, color="#287271")
        ax.set_title(
            f"challenge {Path(row['path']).stem.replace('challenge-', '')}: "
            f"shots={row['shots']}, bond={row['bond_dim']}, unique={row['unique_samples']}, top={row['peak_count']}",
            fontsize=9,
        )
        ax.set_ylabel("count")
        ax.set_xticks([])
    axes[-1].set_xlabel("Top sampled bitstrings, ranked left to right")
    savefig(FIG / "selected_mps_top_counts.png")


def plot_static_summary() -> None:
    rows = static_difficulty()
    labels = [r["difficulty"] for r in rows]
    gates = [float(r["gate_count_mean"]) for r in rows]
    density = [float(r["noisy_angle_fraction"]) for r in rows]
    x = np.arange(len(rows))
    fig, ax1 = plt.subplots(figsize=(8.0, 3.7))
    ax1.bar(x - 0.18, gates, width=0.36, color="#4c78a8", label="mean gates")
    ax1.set_ylabel("Mean gates")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=25, ha="right")
    ax2 = ax1.twinx()
    ax2.plot(x + 0.18, density, color="#c44536", marker="o", label="non-grid angle fraction")
    ax2.set_ylabel("Non-grid angle fraction")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8)
    plt.title("Static challenge scale and angle noise by difficulty")
    savefig(FIG / "static_difficulty.png")


def copy_existing_figures() -> None:
    copies = {
        "selected_overview.png": ROOT / "outputs/sim_11_26_34_41_49/images/selected_outputs_overview.png",
        "mps_8_11.png": ROOT / "outputs/sim_11_26_34_41_49/images/mps/challenge-8_11.png",
        "mps_64_26.png": ROOT / "outputs/sim_11_26_34_41_49/images/mps/challenge-64_26.png",
        "mps_64_34.png": ROOT / "outputs/sim_11_26_34_41_49/images/mps/challenge-64_34.png",
        "mps_64_41.png": ROOT / "outputs/sim_11_26_34_41_49/images/mps/challenge-64_41.png",
        "mps_104_49.png": ROOT / "outputs/sim_11_26_34_41_49/images/mps/challenge-104_49.png",
        "peaked_24_13.png": ROOT / "outputs/peaked_circuit_sim_all/images/challenge-24_13.peaked_mpo_mps.png",
        "peaked_40_16.png": ROOT / "outputs/peaked_circuit_sim_all/images/challenge-40_16.peaked_mpo_mps.png",
        "peaked_16_12.png": ROOT / "outputs/peaked_circuit_sim_all/images/challenge-16_12.peaked_mpo_mps.png",
    }
    for name, src in copies.items():
        if src.exists():
            shutil.copy2(src, FIG / name)


def write_exact_table() -> None:
    rows = sorted(exact_results(), key=lambda r: (r["qubits"], r["difficulty"], r["challenge"]))
    lines = [
        r"\begin{tabular}{llrp{0.36\linewidth}rr}",
        r"\toprule",
        r"Challenge & Difficulty & Qubits & Peak bitstring & Peak prob. & Gap \\",
        r"\midrule",
    ]
    for r in rows:
        lines.append(
            f"{esc(r['challenge'])} & {esc(r['difficulty'])} & {r['qubits']} & "
            f"{bittex(r['peak_bitstring'])} & {r['peak_probability']:.6f} & {r['gap_to_second']:.6f} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TAB / "exact_peaks.tex").write_text("\n".join(lines) + "\n")


def write_candidate_table() -> None:
    rows = [
        ("8_1", "exact/peaked", "10101101", "validated", "Exact peak p=0.9126; peaked matched."),
        ("8_11", "exact/peaked/MPS", "01001110", "validated", "All methods matched; exact p=0.5454."),
        ("8_27", "exact/peaked", "11001001", "validated", "Exact p=0.2879; peaked matched."),
        ("16_12", "exact/peaked/MPS", "1111000101101011", "validated", "All methods matched; exact p=0.4665."),
        ("24_13", "exact", "111110011111001011010001", "validated", "Peaked marginal output was one bit off."),
        ("40_16", "MPS distill", "0101110101001110011000111011100110010110", "strong candidate", "Stable across 6/6 MPS trials; peaked disagreed by 3 bits."),
        ("64_26", "Aer MPS", "0110101010100011010111011000011100010110110110011100011001100110", "candidate", "Top count 287/4096; runner candidate only."),
        ("64_34", "Aer MPS", "0011010100010011001110101110100101001011001011011001111011100110", "candidate", "Top count 552/4096; runner candidate only."),
        ("64_41", "MPS samples", "--", "unreliable", "4096/4096 unique in selected run; distill unstable."),
        ("104_49", "MPS samples", "--", "unreliable", "1024/1024 unique; no repeated peak evidence."),
    ]
    lines = [
        r"\begin{longtable}{p{0.10\linewidth}p{0.15\linewidth}p{0.39\linewidth}p{0.12\linewidth}p{0.18\linewidth}}",
        r"\caption{Candidate bitstrings and confidence after this session.}\\",
        r"\toprule",
        r"Challenge & Source & Candidate & Confidence & Reason \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"Challenge & Source & Candidate & Confidence & Reason \\",
        r"\midrule",
        r"\endhead",
    ]
    for ch, src, cand, conf, reason in rows:
        cand_tex = bittex(cand) if cand != "--" else "--"
        lines.append(f"{esc(ch)} & {esc(src)} & {cand_tex} & {esc(conf)} & {esc(reason)} \\\\")
    lines += [r"\bottomrule", r"\end{longtable}"]
    (TAB / "candidate_table.tex").write_text("\n".join(lines) + "\n")


def write_peaked_table() -> None:
    rows = []
    for r in peaked_results():
        if r.get("_source") != "peaked_circuit_sim_all" or r.get("status") != "ok":
            continue
        rows.append(r)
    rows = sorted(rows, key=lambda r: (r.get("difficulty", ""), r.get("challenge_label", "")))
    lines = [
        r"\begin{tabular}{llrp{0.43\linewidth}rr}",
        r"\toprule",
        r"Challenge & Difficulty & Qubits & Peaked candidate & Min margin & MPS bond \\",
        r"\midrule",
    ]
    for r in rows:
        lines.append(
            f"{esc(r['challenge_label'])} & {esc(r['difficulty'])} & {r['num_qubits']} & "
            f"{bittex(r['pred_bitstring_qiskit_order'])} & {float(r.get('p1_margin_min') or 0):.2e} & "
            f"{r.get('mps_info', {}).get('max_bond')} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TAB / "peaked_completed.tex").write_text("\n".join(lines) + "\n")


def write_mps_selected_table() -> None:
    rows = sorted(selected_mps_results(), key=lambda r: int(r["challenge_id"]))
    lines = [
        r"\begin{tabular}{rrrrp{0.43\linewidth}rr}",
        r"\toprule",
        r"ID & Qubits & Shots & Bond & Top sampled bitstring & Count & Unique \\",
        r"\midrule",
    ]
    for r in rows:
        ch = Path(r["path"]).stem.replace("challenge-", "")
        lines.append(
            f"{esc(ch)} & {r['num_qubits']} & {r['shots']} & {r['bond_dim']} & "
            f"{bittex(r['peak'])} & {r['peak_count']} & {r['unique_samples']} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TAB / "selected_mps.tex").write_text("\n".join(lines) + "\n")


def write_summary_json() -> None:
    exact = {r["challenge"]: r for r in exact_results()}
    peaked_ok = [r for r in peaked_results() if r.get("_source") == "peaked_circuit_sim_all" and r.get("status") == "ok"]
    selected = selected_mps_results()
    payload = {
        "exact_completed": len(exact),
        "peaked_full_json": len(list((ROOT / "outputs/peaked_circuit_sim_all/json").glob("*.json"))),
        "peaked_full_ok": len(peaked_ok),
        "peaked_full_started": sum(
            1
            for p in (ROOT / "outputs/peaked_circuit_sim_all/json").glob("*.json")
            if read_json(p).get("status") == "started"
        ),
        "selected_mps_ok": len(selected),
        "mps_distill_circuits": len(mps_distill_summary()),
    }
    (OUT / "report_summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    plot_exact_peak_probabilities()
    plot_method_agreement()
    plot_peaked_margins()
    plot_mps_stability()
    plot_selected_mps_counts()
    plot_static_summary()
    copy_existing_figures()
    write_exact_table()
    write_candidate_table()
    write_peaked_table()
    write_mps_selected_table()
    write_summary_json()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
