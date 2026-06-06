#!/usr/bin/env python3
"""Build per-challenge solution books with distribution figures."""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DIFFICULTY_ORDER = {
    "very easy": 0,
    "very_easy": 0,
    "easy": 1,
    "moderate": 2,
    "hard": 3,
    "very_hard": 4,
    "very hard": 4,
    "": 9,
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
DOCUMENT_EXTENSIONS = {".pdf"}


@dataclass(frozen=True)
class SessionConfig:
    name: str
    session_dir: Path
    local_figure_roots: tuple[Path, ...]
    copied_figure_roots: tuple[tuple[str, Path], ...]
    global_figure_roots: tuple[Path, ...]


@dataclass(frozen=True)
class Figure:
    path: Path
    caption: str
    embedded: bool


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def as_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def challenge_sort_key(label: str, difficulty: str = "") -> tuple[int, int, int, str]:
    left = right = 9999
    if "_" in label:
        a, b = label.split("_", 1)
        left = as_int(a) or left
        right = as_int(b) or right
    return (DIFFICULTY_ORDER.get(difficulty, 8), right, left, label)


def method_sort_key(row: dict[str, str]) -> tuple[str, str, int, str]:
    return (
        row.get("method", ""),
        row.get("rank_type", ""),
        as_int(row.get("rank", "")) or 999999,
        row.get("bitstring_qiskit", ""),
    )


def clean_text(value: str) -> str:
    return "" if value == "-" else value


def md_escape(value: str) -> str:
    return clean_text(value).replace("|", "\\|")


def rel_link(target: Path, source_dir: Path) -> str:
    return os.path.relpath(target.resolve(), source_dir.resolve())


def figure_caption(path: Path, root: Path) -> str:
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = path.name
    name = path.stem
    if "quimb_tree_graph_mps" in name:
        method = "Quimb graph-ordered MPS"
    elif "tree_tensor_mps" in name:
        method = "tree/order MPS sample"
    elif "peaked_mpo" in name or name.startswith("peaked_"):
        method = "peaked MPO/MPS marginal"
    elif name.startswith("mps_") or "/mps/" in rel:
        method = "Aer MPS sample"
    elif "/statevector/" in rel:
        method = "statevector distribution"
    else:
        method = "distribution figure"
    return f"{method}: {rel}"


def label_in_path(label: str, path: Path) -> bool:
    return label in path.name or label in path.as_posix()


def iter_files(root: Path, extensions: set[str]) -> Iterable[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in extensions)


def copy_external_figures(session: SessionConfig, output_dir: Path, labels: set[str]) -> list[Path]:
    copied: list[Path] = []
    for namespace, root in session.copied_figure_roots:
        if not root.exists():
            continue
        for path in iter_files(root, IMAGE_EXTENSIONS):
            if not any(label_in_path(label, path) for label in labels):
                continue
            rel = path.resolve().relative_to(root.resolve())
            dest = output_dir / "figures" / namespace / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            copied.append(dest)
    return copied


def collect_challenge_figures(
    session: SessionConfig,
    output_dir: Path,
    labels: set[str],
) -> dict[str, list[Figure]]:
    copied = copy_external_figures(session, output_dir, labels)
    roots = list(session.local_figure_roots) + [output_dir / "figures"]
    paths: list[tuple[Path, Path]] = []
    for root in roots:
        for path in iter_files(root, IMAGE_EXTENSIONS):
            paths.append((root, path))

    seen: set[Path] = set()
    by_label: dict[str, list[Figure]] = defaultdict(list)
    for root, path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        for label in labels:
            if label_in_path(label, path):
                by_label[label].append(Figure(path=path, caption=figure_caption(path, root), embedded=True))

    for label, figures in by_label.items():
        figures.sort(key=lambda item: item.caption)
    return by_label


def collect_global_figures(session: SessionConfig) -> list[Path]:
    result: list[Path] = []
    for root in session.global_figure_roots:
        result.extend(iter_files(root, DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS))
    return sorted(set(result), key=lambda path: path.as_posix())


def write_challenge_page(
    page_path: Path,
    meta: dict[str, str],
    candidates: list[dict[str, str]],
    annotations: list[dict[str, str]],
    figures: list[Figure],
    index_page: Path,
) -> None:
    page_path.parent.mkdir(parents=True, exist_ok=True)
    label = meta["challenge"]
    selected = clean_text(meta.get("selected_bitstring", ""))
    lines = [
        f"# Challenge {label}",
        "",
        f"- Difficulty: {meta.get('difficulty', '')}",
        f"- Qubits: {meta.get('qubits', '')}",
        f"- QASM: `{meta.get('qasm', '')}`",
        f"- Selected answer: `{selected}`" if selected else "- Selected answer: blank",
        f"- Selected method: `{meta.get('selected_method', '')}`",
        f"- Validation: `{meta.get('validation', '')}`",
        f"- Evidence rows: {meta.get('evidence_count', '')}",
        f"- Normalized index page: [{label}]({rel_link(index_page, page_path.parent)})",
        "",
    ]

    if annotations:
        lines.extend(
            [
                "## Review Notes",
                "",
                "| status | bitstring | note | date | source |",
                "|---|---|---|---|---|",
            ]
        )
        for row in annotations:
            lines.append(
                f"| {md_escape(row.get('status', ''))} | `{row.get('bitstring_qiskit', '')}` | {md_escape(row.get('note', ''))} | {md_escape(row.get('date', ''))} | {md_escape(row.get('source', ''))} |"
            )
        lines.append("")

    lines.extend(["## Distribution Figures", ""])
    if figures:
        for figure in figures:
            link = rel_link(figure.path, page_path.parent)
            lines.extend([f"### {md_escape(figure.caption)}", "", f"![{md_escape(figure.caption)}]({link})", ""])
    else:
        lines.extend(["No committed bitstring-distribution figure was found for this challenge.", ""])

    lines.extend(
        [
            "## Candidate Rows",
            "",
            "| review | selected | method | rank_type | rank | bitstring | score | count | support | fraction | validation | status | source |",
            "|---|---:|---|---|---:|---|---:|---:|---:|---:|---|---|---|",
        ]
    )

    review_by_bitstring = defaultdict(list)
    for row in annotations:
        review_by_bitstring[row.get("bitstring_qiskit", "")].append(row.get("status", ""))

    for row in sorted(candidates, key=method_sort_key):
        review = ",".join(review_by_bitstring.get(row.get("bitstring_qiskit", ""), []))
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(review),
                    md_escape(row.get("selected", "")),
                    md_escape(row.get("method", "")),
                    md_escape(row.get("rank_type", "")),
                    md_escape(row.get("rank", "")),
                    f"`{row.get('bitstring_qiskit', '')}`",
                    md_escape(row.get("score", "")),
                    md_escape(row.get("count", "")),
                    md_escape(row.get("support", "")),
                    md_escape(row.get("fraction", "")),
                    md_escape(row.get("validation", "")),
                    md_escape(row.get("status", "")),
                    f"`{row.get('source_path', '')}`",
                ]
            )
            + " |"
        )
    page_path.write_text("\n".join(lines) + "\n")


def write_readme(
    output_dir: Path,
    session: SessionConfig,
    challenges: list[dict[str, str]],
    candidates_by_challenge: dict[str, list[dict[str, str]]],
    figures_by_challenge: dict[str, list[Figure]],
    global_figures: list[Path],
) -> None:
    lines = [
        f"# Solution Book: {session.name}",
        "",
        "This folder is the quick browser for challenge answers, alternates, and bitstring-distribution figures.",
        "",
        "Each challenge page contains the selected answer, review notes, all normalized candidate rows, and every matched distribution figure found in committed artifacts.",
        "",
        "## Challenges",
        "",
        "| challenge | difficulty | qubits | selected answer | selected method | validation | candidates | figures | page |",
        "|---|---|---:|---|---|---|---:|---:|---|",
    ]
    for row in challenges:
        label = row["challenge"]
        page = output_dir / "challenges" / f"{label}.md"
        selected = clean_text(row.get("selected_bitstring", ""))
        selected_cell = f"`{selected}`" if selected else "blank"
        lines.append(
            "| "
            + " | ".join(
                [
                    label,
                    row.get("difficulty", ""),
                    row.get("qubits", ""),
                    selected_cell,
                    row.get("selected_method", ""),
                    row.get("validation", ""),
                    str(len(candidates_by_challenge.get(label, []))),
                    str(len(figures_by_challenge.get(label, []))),
                    f"[open]({rel_link(page, output_dir)})",
                ]
            )
            + " |"
        )

    if global_figures:
        lines.extend(["", "## Global Distribution Figures", ""])
        for path in global_figures:
            lines.append(f"- [{path.name}]({rel_link(path, output_dir)})")
    lines.append("")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "README.md").write_text("\n".join(lines))


def build_session(session: SessionConfig, repo_root: Path) -> None:
    index_dir = session.session_dir / "results_index"
    output_dir = session.session_dir / "solution_book"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    challenges = read_tsv(index_dir / "challenges.tsv")
    candidates = read_tsv(index_dir / "candidates.tsv")
    annotations = read_tsv(index_dir / "annotations.tsv")
    challenges.sort(key=lambda row: challenge_sort_key(row["challenge"], row.get("difficulty", "")))

    labels = {row["challenge"] for row in challenges}
    figures_by_challenge = collect_challenge_figures(session, output_dir, labels)

    candidates_by_challenge: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        candidates_by_challenge[row["challenge"]].append(row)

    annotations_by_challenge: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in annotations:
        annotations_by_challenge[row["challenge"]].append(row)

    for row in challenges:
        label = row["challenge"]
        write_challenge_page(
            output_dir / "challenges" / f"{label}.md",
            row,
            candidates_by_challenge.get(label, []),
            annotations_by_challenge.get(label, []),
            figures_by_challenge.get(label, []),
            index_dir / "by_challenge" / f"{label}.md",
        )

    write_readme(
        output_dir,
        session,
        challenges,
        candidates_by_challenge,
        figures_by_challenge,
        collect_global_figures(session),
    )


def default_sessions(repo_root: Path) -> list[SessionConfig]:
    sibling = repo_root.parent / "quantum-junction-tree-tensor"
    return [
        SessionConfig(
            name="tree_tensor_sim_session",
            session_dir=repo_root / "research/tree_tensor_sim_session",
            local_figure_roots=(
                repo_root / "outputs/peaked_circuit_sim_all/images",
                repo_root / "outputs/peaked_circuit_sim_pilot/images",
                repo_root / "outputs/sim_11_26_34_41_49/images",
            ),
            copied_figure_roots=(
                ("tree_tensor_sim", sibling / "outputs/tree_tensor_sim"),
            ),
            global_figure_roots=(
                repo_root / "research/tree_tensor_sim_session/report/figures",
            ),
        ),
        SessionConfig(
            name="quantum_peak_session",
            session_dir=repo_root / "research/quantum_peak_session",
            local_figure_roots=(
                repo_root / "outputs/peaked_circuit_sim_all/images",
                repo_root / "outputs/peaked_circuit_sim_pilot/images",
                repo_root / "outputs/sim_11_26_34_41_49/images",
                repo_root / "research/quantum_peak_session/reports/session_report/figures",
                repo_root / "research/quantum_peak_session/reports/tree_tensor_report/figures",
            ),
            copied_figure_roots=(),
            global_figure_roots=(
                repo_root / "research/quantum_peak_session/reports/session_report/figures",
                repo_root / "research/quantum_peak_session/reports/tree_tensor_report/figures",
            ),
        ),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--session",
        choices=["tree_tensor_sim_session", "quantum_peak_session"],
        action="append",
        help="Build only the named session. May be supplied more than once.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    requested = set(args.session or [])
    for session in default_sessions(repo_root):
        if requested and session.name not in requested:
            continue
        build_session(session, repo_root)
        print(f"built {session.session_dir / 'solution_book'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
