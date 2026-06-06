#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


SESSION = Path(__file__).resolve().parents[2]
REPO = SESSION.parents[1]
OUT = Path(__file__).resolve().parent
FIG = OUT / "figures"
TAB = OUT / "tables"
SUMMARY_DIR = SESSION / "results" / "distributions"
SUMMARY_JSON = SUMMARY_DIR / "distribution_summary.json"
APPENDIX_PDF = FIG / "distribution_appendix_pages.pdf"
APPENDIX_TEX = TAB / "distribution_appendix.tex"

DEFAULT_RAW_ROOT = REPO.parent / "quantum-junction-tree-tensor"
RAW_ROOT = Path(os.environ.get("QUANTUM_PEAK_RAW_ROOT", DEFAULT_RAW_ROOT))

DIFF_ORDER = {
    "very easy": 0,
    "easy": 1,
    "moderate": 2,
    "hard": 3,
    "very_hard": 4,
}

SOURCE_LABELS = {
    "exact_statevector": "exact statevector",
    "quimb_gpu_all": "Quimb GPU",
    "quimb_opt_u3_gpu": "optimized-U3 GPU",
    "quimb_cpu_all": "Quimb CPU",
    "quimb_rcm_cpu": "Quimb RCM CPU",
    "quimb_mst_cpu": "Quimb MST CPU",
    "quimb_degree_cpu": "Quimb degree CPU",
    "quimb_mid_cpu": "Quimb mid CPU",
    "quimb_fast_cpu": "Quimb fast CPU",
    "quimb_identity_cpu": "Quimb identity CPU",
    "aer_mps_pilot": "Aer MPS distill",
    "peaked_mpo_unswap_gpu": "MPO unswap",
}

DIR_SOURCE = {
    "all": "quimb_gpu_all",
    "all_cpu": "quimb_cpu_all",
    "rcm_cpu": "quimb_rcm_cpu",
    "mst_cpu": "quimb_mst_cpu",
    "degree_cpu": "quimb_degree_cpu",
    "mid_cpu": "quimb_mid_cpu",
    "fast_cpu": "quimb_fast_cpu",
    "identity_cpu": "quimb_identity_cpu",
    "peaked_unswap_gpu": "peaked_mpo_unswap_gpu",
}

SOURCE_PRIORITY = {
    "exact_statevector": 100,
    "quimb_gpu_all": 90,
    "quimb_opt_u3_gpu": 85,
    "quimb_cpu_all": 80,
    "peaked_mpo_unswap_gpu": 72,
    "quimb_rcm_cpu": 70,
    "quimb_mst_cpu": 68,
    "quimb_degree_cpu": 66,
    "quimb_mid_cpu": 64,
    "quimb_fast_cpu": 62,
    "quimb_identity_cpu": 60,
    "aer_mps_pilot": 40,
}


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


def bit_or_blank(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text or None


def short_bits(bits: str, head: int = 6, tail: int = 5) -> str:
    if len(bits) <= head + tail + 3:
        return bits
    return f"{bits[:head]}...{bits[-tail:]}"


def label_source(source: str | None) -> str:
    if not source:
        return ""
    return SOURCE_LABELS.get(source, source.replace("_", " "))


def challenge_key(row: dict[str, Any]) -> tuple[int, int, int, str]:
    label = str(row["challenge"])
    q_s, _, id_s = label.partition("_")
    return (
        DIFF_ORDER.get(str(row["difficulty"]), 99),
        int(q_s) if q_s.isdigit() else 999,
        int(id_s) if id_s.isdigit() else 999,
        label,
    )


def read_candidates() -> list[dict[str, Any]]:
    path = SESSION / "results" / "current_candidates" / "CANDIDATES.tsv"
    with path.open(newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    return sorted(rows, key=challenge_key)


def read_evidence() -> dict[str, list[dict[str, Any]]]:
    path = SESSION / "results" / "current_candidates" / "CANDIDATE_EVIDENCE.json"
    data = json.loads(path.read_text())
    return {str(row["label"]): list(row.get("evidence") or []) for row in data}


def read_exact_tops(raw_root: Path) -> dict[str, dict[str, Any]]:
    path = raw_root / "agent_work" / "exact_baseline" / "peaks_exact.jsonl"
    if not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        top = [
            {
                "bitstring": item["bitstring"],
                "value": float(item["probability"]),
                "rank": int(item.get("rank", len(out) + 1)),
            }
            for item in row.get("top", [])[:8]
        ]
        out[str(row["challenge"])] = {
            "status": "ok",
            "kind": "exact",
            "source": "exact_statevector",
            "source_label": label_source("exact_statevector"),
            "value_label": "probability",
            "total": 1.0,
            "top": top,
            "tail_value": max(0.0, 1.0 - sum(item["value"] for item in top)),
            "note": "Exact statevector probabilities; tail is all other basis states.",
        }
    return out


def read_distill(raw_root: Path) -> dict[str, dict[str, Any]]:
    path = raw_root / "agent_work" / "mps_distill" / "summaries" / "pilot_summary.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    out: dict[str, dict[str, Any]] = {}
    for row in data.get("circuits", []):
        label = Path(row.get("circuit", "")).stem.replace("challenge-", "")
        top = [
            {
                "bitstring": item["bitstring"],
                "value": float(item["fraction"]),
                "support": int(item.get("support", 0)),
            }
            for item in row.get("aggregate_rank", [])[:8]
        ]
        out[label] = {
            "status": "ok",
            "kind": "aggregate",
            "source": "aer_mps_pilot",
            "source_label": label_source("aer_mps_pilot"),
            "value_label": "aggregate support fraction",
            "total": 1.0,
            "top": top,
            "tail_value": max(0.0, 1.0 - sum(item["value"] for item in top)),
            "note": (
                "MPS distillation aggregate across seed/shot/bond trials; "
                "support is repeated observations, not an exact probability."
            ),
        }
    return out


def source_from_json_path(path: Path) -> str:
    parent = path.parent.parent.name
    return DIR_SOURCE.get(parent, parent)


def extract_json_distribution(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None
    sampling = data.get("sampling") or {}
    source = source_from_json_path(path)
    status = data.get("status")
    if status not in (None, "ok") and sampling.get("status") != "ok":
        return None

    if "top_qiskit_order" in sampling:
        total = float(sampling.get("observed_samples") or sampling.get("samples") or 0)
        if total <= 0:
            return None
        top = [
            {
                "bitstring": item["bitstring"],
                "count": int(item["count"]),
                "value": float(item["count"]) / total,
            }
            for item in sampling.get("top_qiskit_order", [])[:8]
        ]
        return {
            "status": "ok",
            "kind": "sample",
            "source": source,
            "source_label": label_source(source),
            "value_label": "sample fraction",
            "total": total,
            "top": top,
            "tail_value": max(0.0, 1.0 - sum(item["value"] for item in top)),
            "note": "Sampled output distribution; tail is all observed outcomes outside the plotted top ranks.",
            "path": str(path),
        }

    if "top" in sampling:
        total = float(sampling.get("samples") or 0)
        top = []
        for item in sampling.get("top", [])[:8]:
            bits = item.get("permuted_measurement_order") or item.get("bitstring") or item.get("raw_site_order") or ""
            qiskit_bits = bits[::-1] if item.get("permuted_measurement_order") else bits
            value = float(item.get("fraction") or (float(item.get("count", 0)) / total if total else 0.0))
            top.append({"bitstring": qiskit_bits, "count": int(item.get("count", 0)), "value": value})
        if not top:
            return None
        return {
            "status": "ok",
            "kind": "sample",
            "source": source,
            "source_label": label_source(source),
            "value_label": "sample fraction",
            "total": total,
            "top": top,
            "tail_value": max(0.0, 1.0 - sum(item["value"] for item in top)),
            "note": "MPO-unswap sampled distribution after the recovered measurement permutation; tail is unplotted sample mass.",
            "path": str(path),
        }

    return None


def evidence_distribution(raw_root: Path, ev: dict[str, Any]) -> dict[str, Any] | None:
    rel = bit_or_blank(ev.get("path"))
    if not rel or not rel.endswith(".json"):
        return None
    path = raw_root / rel
    if not path.exists():
        return None
    return extract_json_distribution(path)


def scan_distribution(raw_root: Path, label: str) -> dict[str, Any] | None:
    base = raw_root / "outputs" / "tree_tensor_sim"
    if not base.exists():
        return None
    found = []
    for path in sorted(base.glob(f"*/json/challenge-{label}.*.json")):
        dist = extract_json_distribution(path)
        if dist is None:
            continue
        top_value = float(dist["top"][0]["value"]) if dist.get("top") else 0.0
        priority = SOURCE_PRIORITY.get(str(dist.get("source")), 0)
        found.append((top_value, priority, dist))
    if not found:
        return None
    found.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return found[0][2]


def collect_distributions() -> list[dict[str, Any]]:
    rows = read_candidates()
    evidence = read_evidence()
    exact = read_exact_tops(RAW_ROOT)
    distill = read_distill(RAW_ROOT)
    out = []

    for row in rows:
        label = str(row["challenge"])
        selected = bit_or_blank(row.get("candidate"))
        source = bit_or_blank(row.get("source"))
        selected_ev = None
        for ev in evidence.get(label, []):
            if source and ev.get("source") == source:
                selected_ev = ev
                break
            if selected and ev.get("candidate") == selected:
                selected_ev = ev
                break

        dist = None
        if label in exact:
            dist = exact[label]
        elif source == "aer_mps_pilot" and label in distill:
            dist = distill[label]
        elif selected_ev is not None:
            dist = evidence_distribution(RAW_ROOT, selected_ev)
        if dist is None:
            dist = scan_distribution(RAW_ROOT, label)

        if dist is None:
            dist = {
                "status": "missing",
                "kind": "none",
                "source": source or "",
                "source_label": label_source(source) if source else "",
                "value_label": "",
                "total": None,
                "top": [],
                "tail_value": 0.0,
                "note": "No completed distribution was available in the session artifacts.",
            }
        elif not selected:
            dist["note"] = "No answer was selected for this row; plotted data is the best completed low-confidence distribution found."

        top_value = float(dist["top"][0]["value"]) if dist.get("top") else None
        out.append(
            {
                "challenge": label,
                "difficulty": row["difficulty"],
                "qubits": int(row["qubits"]),
                "selected_candidate": selected,
                "selected_source": source,
                "collector_top_fraction": bit_or_blank(row.get("top_fraction")),
                "evidence_count": bit_or_blank(row.get("evidence_count")),
                "distribution": dist,
                "plotted_top_value": top_value,
            }
        )
    return out


def load_or_collect() -> list[dict[str, Any]]:
    if (RAW_ROOT / "outputs").exists() or (RAW_ROOT / "agent_work").exists():
        rows = collect_distributions()
        SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
        SUMMARY_JSON.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
        return rows
    if SUMMARY_JSON.exists():
        return json.loads(SUMMARY_JSON.read_text())
    raise FileNotFoundError(
        f"No raw outputs under {RAW_ROOT} and no committed summary at {SUMMARY_JSON}"
    )


def plot_panel(ax: Any, row: dict[str, Any]) -> None:
    dist = row["distribution"]
    title = f"{row['challenge']} ({row['difficulty']}, q={row['qubits']})"
    selected = row.get("selected_candidate")

    if not dist.get("top"):
        ax.set_axis_off()
        ax.text(0.5, 0.58, title, ha="center", va="center", fontsize=9, weight="bold")
        ax.text(0.5, 0.42, "no completed distribution", ha="center", va="center", fontsize=8, color="#8a2d2d")
        return

    top = dist["top"][:8]
    values = [float(item["value"]) for item in top] + [float(dist.get("tail_value") or 0.0)]
    labels = [f"r{i + 1}\n{short_bits(item['bitstring'])}" for i, item in enumerate(top)] + ["tail"]
    colors = []
    for item in top:
        if selected and item["bitstring"] == selected:
            colors.append("#287271")
        elif not selected:
            colors.append("#b08900")
        else:
            colors.append("#4c78a8")
    colors.append("#d0d0d0")

    ax.bar(range(len(values)), values, color=colors)
    ax.set_title(title, fontsize=8, pad=3)
    ax.set_ylim(0, max(values + [0.01]) * 1.22)
    ax.set_xticks(range(len(labels)), labels, rotation=0, fontsize=5)
    ax.tick_params(axis="y", labelsize=6)
    ax.grid(axis="y", alpha=0.2, linewidth=0.5)
    top_value = values[0]
    status = "selected" if selected else "not selected"
    source = dist.get("source_label") or label_source(row.get("selected_source"))
    ax.text(
        0.01,
        0.97,
        f"{source}\n{status}; top={top_value:.4g}",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=6,
        bbox={"facecolor": "white", "alpha": 0.72, "edgecolor": "none", "pad": 1.5},
    )


def write_plots(rows: list[dict[str, Any]]) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    per_page = 8
    with PdfPages(APPENDIX_PDF) as pdf:
        for start in range(0, len(rows), per_page):
            chunk = rows[start : start + per_page]
            fig, axes = plt.subplots(4, 2, figsize=(11.0, 8.5))
            axes_flat = list(axes.ravel())
            for ax, row in zip(axes_flat, chunk):
                plot_panel(ax, row)
            for ax in axes_flat[len(chunk) :]:
                ax.set_axis_off()
            page = start // per_page + 1
            total_pages = math.ceil(len(rows) / per_page)
            fig.suptitle(
                f"Per-problem result distributions, page {page}/{total_pages}",
                fontsize=12,
                y=0.992,
            )
            fig.tight_layout(rect=(0, 0, 1, 0.965))
            pdf.savefig(fig)
            plt.close(fig)


def write_appendix_tex(rows: list[dict[str, Any]]) -> None:
    TAB.mkdir(parents=True, exist_ok=True)
    lines = [
        r"\clearpage",
        r"\section*{Appendix: Per-Problem Result Distributions}",
        (
            r"Each panel below shows the best distribution evidence retained for one challenge. "
            r"Exact panels show the largest exact probabilities from statevector simulation. "
            r"Sampled panels show the top observed bitstrings from Quimb MPS, MPO-unswap, or MPS "
            r"distillation evidence; the grey tail is all unplotted probability or sample mass. "
            r"Green bars mark a plotted bitstring that equals the selected candidate. Orange panels "
            r"mean no answer was selected even though a low-confidence distribution was available. "
            r"Bitstrings in plots are shortened for readability; the full selected bitstrings remain "
            r"in the selected candidate table above. All bitstrings use Qiskit count order."
        ),
        "",
        r"\includepdf[pages=-,fitpaper=true]{figures/distribution_appendix_pages.pdf}",
        r"\clearpage",
        r"\subsection*{Distribution Metadata}",
        (
            r"The table records the source used in each appendix panel and the top plotted mass. "
            r"For exact rows this is an exact probability; for sampled rows it is an observed sample "
            r"fraction or aggregate support fraction. Rows with no completed distribution are left blank."
        ),
        r"\scriptsize",
        r"\begin{longtable}{l l r l l r l}",
        r"\toprule",
        r"Challenge & difficulty & q & selected source & plotted source & top mass & appendix status \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"Challenge & difficulty & q & selected source & plotted source & top mass & appendix status \\",
        r"\midrule",
        r"\endhead",
    ]
    for row in rows:
        dist = row["distribution"]
        top = row.get("plotted_top_value")
        top_s = "" if top is None else f"{float(top):.4g}"
        selected_source = label_source(row.get("selected_source"))
        plotted_source = dist.get("source_label") or ""
        status = "selected" if row.get("selected_candidate") else "not selected"
        if dist.get("status") == "missing":
            status = "no completed distribution"
        lines.append(
            f"{esc(row['challenge'])} & {esc(row['difficulty'])} & {row['qubits']} & "
            f"{esc(selected_source)} & {esc(plotted_source)} & {esc(top_s)} & {esc(status)} \\\\"
        )
    lines += [r"\bottomrule", r"\end{longtable}", r"\normalsize"]
    APPENDIX_TEX.write_text("\n".join(lines) + "\n")


def main() -> int:
    rows = load_or_collect()
    write_plots(rows)
    write_appendix_tex(rows)
    print(APPENDIX_PDF)
    print(APPENDIX_TEX)
    print(SUMMARY_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
