#!/usr/bin/env python3
"""Build one central per-challenge solution browser.

The session folders remain separate provenance packages.  This script creates a
single generated lookup surface that merges those normalized indexes with later
raw artifacts that were added outside the original report sessions.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


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

CHALLENGE_RE = re.compile(r"challenge-(\d+_\d+)")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

CHALLENGE_FIELDS = [
    "challenge",
    "difficulty",
    "qubits",
    "qasm",
    "selected_bitstring",
    "selected_method",
    "selected_review",
    "try_next_bitstring",
    "validation",
    "evidence_count",
    "source_sessions",
    "notes",
]

SELECTED_SOURCE_FIELDS = [
    "challenge",
    "source_session",
    "selected_bitstring",
    "selected_method",
    "validation",
    "top_fraction",
    "evidence_count",
    "status",
]

RUN_FIELDS = [
    "challenge",
    "difficulty",
    "qubits",
    "method",
    "method_family",
    "source_sessions",
    "run_id",
    "status",
    "source_path",
    "worktree",
    "commit",
    "backend",
    "shots",
    "max_bond",
    "seed",
    "ordering",
    "seconds",
    "notes",
]

CANDIDATE_FIELDS = [
    "challenge",
    "difficulty",
    "qubits",
    "method",
    "method_family",
    "source_sessions",
    "run_id",
    "rank_type",
    "rank",
    "bitstring_qiskit",
    "score_type",
    "score",
    "count",
    "support",
    "fraction",
    "selected",
    "review",
    "validation",
    "status",
    "source_path",
    "notes",
]

ANNOTATION_FIELDS = [
    "challenge",
    "bitstring_qiskit",
    "status",
    "note",
    "date",
    "source",
    "source_sessions",
]

FIGURE_FIELDS = ["challenge", "caption", "path", "source", "embedded"]

METHOD_SELECTOR_FIELDS = [
    "challenge",
    "difficulty",
    "qubits",
    "first_action",
    "best_method_id",
    "best_method_name",
    "best_score",
    "mps_score",
    "tno_score",
    "mpo_unswapping_score",
    "source_path",
]


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def write_tsv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: as_text(row.get(field, "")) for field in fields})


def challenge_sort_key(label: str, difficulty: str = "") -> tuple[int, int, int, str]:
    left = right = 9999
    if "_" in label:
        a, b = label.split("_", 1)
        left = as_int(a) or left
        right = as_int(b) or right
    return (DIFFICULTY_ORDER.get(difficulty, 8), right, left, label)


def relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return os.path.relpath(path.resolve(), root.resolve())


def rel_link(target: Path, source_dir: Path) -> str:
    return os.path.relpath(target.resolve(), source_dir.resolve())


def md_escape(value: Any) -> str:
    return as_text(value).replace("|", "\\|")


def clean(value: Any) -> str:
    value = as_text(value)
    return "" if value == "-" else value


def label_from_text(value: Any) -> str:
    match = CHALLENGE_RE.search(as_text(value))
    return match.group(1) if match else ""


def label_from_path(path: Path, data: dict[str, Any] | None = None) -> str:
    data = data or {}
    for key in ("challenge_label", "challenge"):
        value = as_text(data.get(key))
        if "_" in value and not value.endswith(".qasm"):
            return value
        match = label_from_text(value)
        if match:
            return match
    for key in ("qasm", "path", "output_json"):
        match = label_from_text(data.get(key))
        if match:
            return match
    return label_from_text(path.as_posix())


def git_commit(root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return out.strip()


def source_commit(root: Path, path: Path) -> str:
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return git_commit(root)
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "log", "-1", "--format=%h", "--", rel],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return git_commit(root)
    return out.strip() or git_commit(root)


def method_family(method: str) -> str:
    if method.startswith("exact") or method.endswith("statevector"):
        return "exact"
    if method.startswith("quimb"):
        return "quimb"
    if "mps" in method:
        return "mps"
    if method.startswith("peaked") or method.startswith("mpo"):
        return "mpo"
    if method.startswith("tno"):
        return "tno"
    if method.startswith("collector"):
        return "collector"
    if method.startswith("algebraic"):
        return "heuristic"
    return "other"


def split_joined(value: str) -> set[str]:
    return {item for item in re.split(r"[,;]", clean(value)) if item}


def merge_text(existing: str, incoming: str) -> str:
    values = split_joined(existing) | split_joined(incoming)
    return ",".join(sorted(values))


def merge_notes(existing: str, incoming: str) -> str:
    existing = clean(existing)
    incoming = clean(incoming)
    if not existing:
        return incoming
    if not incoming or incoming in existing:
        return existing
    return f"{existing}; {incoming}"


def selected_flag(bitstring: str, selected: str) -> str:
    return "1" if bitstring and selected and bitstring == selected else "0"


def add_run(runs: dict[tuple[str, ...], dict[str, str]], row: dict[str, Any]) -> None:
    normalized = {field: as_text(row.get(field, "")) for field in RUN_FIELDS}
    normalized["method_family"] = normalized["method_family"] or method_family(normalized["method"])
    key = (
        normalized["challenge"],
        normalized["method"],
        normalized["run_id"],
        normalized["source_path"],
        normalized["status"],
    )
    if key not in runs:
        runs[key] = normalized
        return
    existing = runs[key]
    existing["source_sessions"] = merge_text(existing["source_sessions"], normalized["source_sessions"])
    existing["notes"] = merge_notes(existing["notes"], normalized["notes"])


def add_candidate(candidates: dict[tuple[str, ...], dict[str, str]], row: dict[str, Any]) -> None:
    normalized = {field: as_text(row.get(field, "")) for field in CANDIDATE_FIELDS}
    normalized["method_family"] = normalized["method_family"] or method_family(normalized["method"])
    key = (
        normalized["challenge"],
        normalized["method"],
        normalized["run_id"],
        normalized["rank_type"],
        normalized["rank"],
        normalized["bitstring_qiskit"],
        normalized["source_path"],
    )
    if key not in candidates:
        candidates[key] = normalized
        return
    existing = candidates[key]
    existing["source_sessions"] = merge_text(existing["source_sessions"], normalized["source_sessions"])
    existing["notes"] = merge_notes(existing["notes"], normalized["notes"])
    if not existing["review"]:
        existing["review"] = normalized["review"]


def update_challenge(
    challenges: dict[str, dict[str, str]],
    label: str,
    row: dict[str, Any],
    source_session: str,
) -> None:
    if not label:
        return
    current = challenges.setdefault(
        label,
        {
            "challenge": label,
            "difficulty": "",
            "qubits": "",
            "qasm": "",
            "selected_bitstring": "",
            "selected_method": "",
            "selected_review": "",
            "try_next_bitstring": "",
            "validation": "",
            "evidence_count": "",
            "source_sessions": "",
            "notes": "",
        },
    )
    for field in ("difficulty", "qubits", "qasm", "validation", "evidence_count"):
        if not clean(current.get(field, "")) and clean(row.get(field, "")):
            current[field] = clean(row.get(field, ""))
    incoming_selected = clean(row.get("selected_bitstring", ""))
    if incoming_selected:
        if not clean(current.get("selected_bitstring", "")):
            current["selected_bitstring"] = incoming_selected
            current["selected_method"] = clean(row.get("selected_method", ""))
        elif current["selected_bitstring"] != incoming_selected:
            current["notes"] = merge_notes(
                current["notes"],
                f"{source_session} selected {incoming_selected}",
            )
    current["source_sessions"] = merge_text(current["source_sessions"], source_session)


def load_existing_indexes(
    repo_root: Path,
    challenges: dict[str, dict[str, str]],
    selected_sources: list[dict[str, str]],
    runs: dict[tuple[str, ...], dict[str, str]],
    candidates: dict[tuple[str, ...], dict[str, str]],
    annotations: list[dict[str, str]],
) -> None:
    session_dirs = [
        "tree_tensor_sim_session",
        "quantum_peak_session",
    ]
    selected_status: dict[tuple[str, str], str] = {}
    for session in session_dirs:
        index_dir = repo_root / "research" / session / "results_index"
        for row in read_tsv(index_dir / "selected_answers.tsv"):
            selected_status[(session, row.get("challenge", ""))] = row.get("status", "")
        for row in read_tsv(index_dir / "challenges.tsv"):
            label = row.get("challenge", "")
            update_challenge(challenges, label, row, session)
            selected_sources.append(
                {
                    "challenge": label,
                    "source_session": session,
                    "selected_bitstring": clean(row.get("selected_bitstring", "")),
                    "selected_method": clean(row.get("selected_method", "")),
                    "validation": clean(row.get("validation", "")),
                    "top_fraction": clean(row.get("top_fraction", "")),
                    "evidence_count": clean(row.get("evidence_count", "")),
                    "status": selected_status.get((session, label), ""),
                }
            )
        for row in read_tsv(index_dir / "method_runs.tsv"):
            row = dict(row)
            row["source_sessions"] = row.pop("session", session)
            add_run(runs, row)
        for row in read_tsv(index_dir / "candidates.tsv"):
            row = dict(row)
            row["source_sessions"] = row.pop("session", session)
            add_candidate(candidates, row)
        for row in read_tsv(index_dir / "annotations.tsv"):
            ann = {field: row.get(field, "") for field in ANNOTATION_FIELDS}
            ann["source_sessions"] = session
            if ann not in annotations:
                annotations.append(ann)


def apply_annotations(
    challenges: dict[str, dict[str, str]],
    candidates: dict[tuple[str, ...], dict[str, str]],
    annotations: list[dict[str, str]],
) -> None:
    review_by_pair: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in annotations:
        review_by_pair[(row["challenge"], row["bitstring_qiskit"])].append(row["status"])

    for row in candidates.values():
        reviews = review_by_pair.get((row["challenge"], row["bitstring_qiskit"]), [])
        if reviews:
            row["review"] = ",".join(sorted(set(reviews)))

    for label, meta in challenges.items():
        selected = clean(meta.get("selected_bitstring", ""))
        selected_reviews = review_by_pair.get((label, selected), [])
        meta["selected_review"] = ",".join(sorted(set(selected_reviews)))
        try_next = [
            row["bitstring_qiskit"]
            for row in annotations
            if row["challenge"] == label and row["status"] == "try_next"
        ]
        if try_next:
            meta["try_next_bitstring"] = try_next[0]


def merge_annotations(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        normalized = {field: row.get(field, "") for field in ANNOTATION_FIELDS}
        key = tuple(normalized[field] for field in ANNOTATION_FIELDS if field != "source_sessions")
        if key not in merged:
            merged[key] = normalized
            continue
        merged[key]["source_sessions"] = merge_text(
            merged[key].get("source_sessions", ""),
            normalized.get("source_sessions", ""),
        )
    return sorted(merged.values(), key=lambda row: (row["challenge"], row["bitstring_qiskit"], row["status"]))


def parse_adaptive_mps(
    repo_root: Path,
    challenges: dict[str, dict[str, str]],
    runs: dict[tuple[str, ...], dict[str, str]],
    candidates: dict[tuple[str, ...], dict[str, str]],
) -> None:
    source = repo_root / "agent_work/mps_adaptive_sweep/report/tables/mps_adaptive_summary.tsv"
    top_source = repo_root / "agent_work/mps_adaptive_sweep/report/tables/mps_adaptive_top_counts.tsv"
    if not source.exists():
        return
    source_rel = relpath(source, repo_root)
    commit = source_commit(repo_root, source)
    for row in read_tsv(source):
        label = row["challenge"]
        meta = challenges.get(label, {})
        update_challenge(challenges, label, row, "mps_adaptive_sweep")
        completed = as_int(row.get("completed_trials")) or 0
        expected = as_int(row.get("expected_trials")) or 0
        status = "ok" if completed else "no_data"
        notes = (
            f"classification={row.get('classification', '')}; "
            f"completed={completed}/{expected}; exact_match={row.get('exact_match', '')}; "
            f"matches_previous={row.get('matches_previous_selected', '')}; settings={row.get('settings', '')}"
        )
        max_bonds = [as_int(item) for item in re.findall(r"bd(\d+)", row.get("settings", ""))]
        add_run(
            runs,
            {
                "challenge": label,
                "difficulty": row.get("difficulty") or meta.get("difficulty", ""),
                "qubits": row.get("qubits") or meta.get("qubits", ""),
                "method": "aer_mps_adaptive_sweep",
                "method_family": "mps",
                "source_sessions": "mps_adaptive_sweep",
                "run_id": "adaptive_sweep_aggregate",
                "status": status,
                "source_path": source_rel,
                "worktree": repo_root.name,
                "commit": commit,
                "shots": row.get("total_shots", ""),
                "max_bond": max([item for item in max_bonds if item is not None], default=""),
                "notes": notes,
            },
        )
        bitstring = clean(row.get("candidate", ""))
        if bitstring:
            add_candidate(
                candidates,
                {
                    "challenge": label,
                    "difficulty": row.get("difficulty") or meta.get("difficulty", ""),
                    "qubits": row.get("qubits") or meta.get("qubits", ""),
                    "method": "aer_mps_adaptive_sweep",
                    "method_family": "mps",
                    "source_sessions": "mps_adaptive_sweep",
                    "run_id": "adaptive_sweep_aggregate",
                    "rank_type": "aggregate_candidate",
                    "rank": 1,
                    "bitstring_qiskit": bitstring,
                    "score_type": "stored_fraction",
                    "score": row.get("candidate_stored_fraction", ""),
                    "support": row.get("top1_vote_fraction", ""),
                    "fraction": row.get("candidate_shot_fraction", ""),
                    "selected": selected_flag(bitstring, challenges.get(label, {}).get("selected_bitstring", "")),
                    "validation": row.get("classification", ""),
                    "status": status,
                    "source_path": source_rel,
                    "notes": f"aggregate_gap={row.get('aggregate_gap', '')}; exact_match={row.get('exact_match', '')}",
                },
            )

    if top_source.exists():
        top_rel = relpath(top_source, repo_root)
        selected = {label: meta.get("selected_bitstring", "") for label, meta in challenges.items()}
        for row in read_tsv(top_source):
            label = row["challenge"]
            meta = challenges.get(label, {})
            bitstring = row.get("bitstring", "")
            add_candidate(
                candidates,
                {
                    "challenge": label,
                    "difficulty": meta.get("difficulty", ""),
                    "qubits": meta.get("qubits", ""),
                    "method": "aer_mps_adaptive_sweep",
                    "method_family": "mps",
                    "source_sessions": "mps_adaptive_sweep",
                    "run_id": "adaptive_sweep_aggregate",
                    "rank_type": "aggregate_top_counts",
                    "rank": row.get("rank", ""),
                    "bitstring_qiskit": bitstring,
                    "score_type": "stored_fraction",
                    "score": row.get("stored_fraction", ""),
                    "count": row.get("count", ""),
                    "fraction": row.get("shot_fraction", ""),
                    "selected": selected_flag(bitstring, selected.get(label, "")),
                    "status": "ok",
                    "source_path": top_rel,
                },
            )


def parse_tno_outputs(
    repo_root: Path,
    challenges: dict[str, dict[str, str]],
    runs: dict[tuple[str, ...], dict[str, str]],
    candidates: dict[tuple[str, ...], dict[str, str]],
) -> None:
    roots = [
        ("tno_contract_core_cpu", repo_root / "outputs/tno_sim_cpu/json"),
        ("tno_contract_core_gpu", repo_root / "outputs/tno_sim_gpu/json"),
        ("tno_contract_core_hard", repo_root / "outputs/tno_sim_hard/json"),
        ("tno_contract_core_sample", repo_root / "outputs/tno_sim_sample/json"),
    ]
    for method, root in roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("*.json")):
            data = read_json(path)
            label = label_from_path(path, data)
            if not label:
                continue
            update_challenge(challenges, label, data, method)
            params = data.get("parameters") or {}
            source = relpath(path, repo_root)
            add_run(
                runs,
                {
                    "challenge": label,
                    "difficulty": data.get("difficulty") or challenges.get(label, {}).get("difficulty", ""),
                    "qubits": data.get("num_qubits") or challenges.get(label, {}).get("qubits", ""),
                    "method": method,
                    "method_family": "tno",
                    "source_sessions": method,
                    "run_id": path.stem,
                    "status": data.get("status", ""),
                    "source_path": source,
                    "worktree": repo_root.name,
                    "commit": source_commit(repo_root, path),
                    "backend": data.get("backend") or params.get("backend_requested"),
                    "max_bond": params.get("max_bond_tno") or params.get("max_bond_tne"),
                    "seconds": data.get("total_seconds", ""),
                    "notes": data.get("error_type") or data.get("error") or params.get("method", ""),
                },
            )
            bitstring = clean(data.get("pred_bitstring_qiskit_order", ""))
            if bitstring:
                add_candidate(
                    candidates,
                    {
                        "challenge": label,
                        "difficulty": data.get("difficulty") or challenges.get(label, {}).get("difficulty", ""),
                        "qubits": data.get("num_qubits") or challenges.get(label, {}).get("qubits", ""),
                        "method": method,
                        "method_family": "tno",
                        "source_sessions": method,
                        "run_id": path.stem,
                        "rank_type": "marginal_candidate",
                        "rank": 1,
                        "bitstring_qiskit": bitstring,
                        "score_type": "p1_margin_min",
                        "score": data.get("p1_margin_min", ""),
                        "selected": selected_flag(bitstring, challenges.get(label, {}).get("selected_bitstring", "")),
                        "status": data.get("status", ""),
                        "source_path": source,
                    },
                )


def parse_mpo_test_outputs(
    repo_root: Path,
    challenges: dict[str, dict[str, str]],
    runs: dict[tuple[str, ...], dict[str, str]],
) -> None:
    for root in sorted(repo_root.glob("outputs/mpo_test_*/json")):
        namespace = root.parent.name
        for path in sorted(root.glob("*.json")):
            data = read_json(path)
            label = label_from_path(path, data)
            if not label:
                continue
            method = f"peaked_mpo_graph_tns_{namespace}"
            update_challenge(challenges, label, data, method)
            params = data.get("parameters") or {}
            add_run(
                runs,
                {
                    "challenge": label,
                    "difficulty": data.get("difficulty") or challenges.get(label, {}).get("difficulty", ""),
                    "qubits": data.get("num_qubits") or challenges.get(label, {}).get("qubits", ""),
                    "method": method,
                    "method_family": "mpo",
                    "source_sessions": namespace,
                    "run_id": path.stem,
                    "status": data.get("status", ""),
                    "source_path": relpath(path, repo_root),
                    "worktree": repo_root.name,
                    "commit": source_commit(repo_root, path),
                    "backend": params.get("backend_requested"),
                    "shots": params.get("samples", ""),
                    "max_bond": params.get("max_bond") or params.get("mps_max_bond"),
                    "seed": params.get("seed", ""),
                    "notes": data.get("method_classification", ""),
                },
            )


def parse_opus_combined(
    repo_root: Path,
    challenges: dict[str, dict[str, str]],
    runs: dict[tuple[str, ...], dict[str, str]],
    candidates: dict[tuple[str, ...], dict[str, str]],
) -> None:
    root = repo_root / "outputs/opus_combined"
    if not root.exists():
        return
    for path in sorted(root.glob("challenge-*/*.json")):
        data = read_json(path)
        label = label_from_path(path, data)
        if not label:
            continue
        method = "mpo_unswap_opus_raw_order"
        params = data.get("params") or {}
        source = relpath(path, repo_root)
        update_challenge(challenges, label, {"difficulty": "", "qubits": data.get("n_qubits", "")}, method)
        add_run(
            runs,
            {
                "challenge": label,
                "difficulty": challenges.get(label, {}).get("difficulty", ""),
                "qubits": data.get("n_qubits") or challenges.get(label, {}).get("qubits", ""),
                "method": method,
                "method_family": "mpo",
                "source_sessions": "opus_combined",
                "run_id": f"{path.parent.name}:{path.stem}",
                "status": data.get("status", ""),
                "source_path": source,
                "worktree": repo_root.name,
                "commit": source_commit(repo_root, path),
                "backend": "gpu" if params.get("use_gpu") else "numpy",
                "shots": params.get("samples", ""),
                "max_bond": params.get("max_bond") or data.get("max_bond_seen"),
                "seed": params.get("seed", ""),
                "seconds": data.get("total_seconds", ""),
                "notes": f"stopped={data.get('stopped_reason', '')}; raw-order output, not qiskit-normalized",
            },
        )
        for rank, item in enumerate(data.get("sample_top5") or [], start=1):
            if not item:
                continue
            bitstring = as_text(item[0])
            add_candidate(
                candidates,
                {
                    "challenge": label,
                    "difficulty": challenges.get(label, {}).get("difficulty", ""),
                    "qubits": data.get("n_qubits") or challenges.get(label, {}).get("qubits", ""),
                    "method": method,
                    "method_family": "mpo",
                    "source_sessions": "opus_combined",
                    "run_id": f"{path.parent.name}:{path.stem}",
                    "rank_type": "raw_sample_top",
                    "rank": rank,
                    "bitstring_qiskit": bitstring,
                    "score_type": "count",
                    "score": item[1] if len(item) > 1 else "",
                    "count": item[1] if len(item) > 1 else "",
                    "selected": selected_flag(bitstring, challenges.get(label, {}).get("selected_bitstring", "")),
                    "validation": "raw_order_uncertain",
                    "status": data.get("status", ""),
                    "source_path": source,
                    "notes": "raw sample order from opus output; not promoted as qiskit-order answer",
                },
            )


def parse_algebraic_simplify(
    repo_root: Path,
    challenges: dict[str, dict[str, str]],
    runs: dict[tuple[str, ...], dict[str, str]],
    candidates: dict[tuple[str, ...], dict[str, str]],
) -> None:
    source = repo_root / "agent_work/algebraic_simplify/summary.csv"
    if not source.exists():
        return
    source_rel = relpath(source, repo_root)
    for row in read_csv(source):
        label = label_from_text(row.get("path", ""))
        if not label:
            continue
        update_challenge(
            challenges,
            label,
            {"difficulty": row.get("difficulty", ""), "qubits": row.get("n", ""), "qasm": row.get("path", "")},
            "algebraic_simplify",
        )
        for method, field, match_field in (
            ("algebraic_simplify_cxswap", "candidate_x_cxswap_1e3", "cand_cxswap_matches_sv"),
            ("algebraic_simplify_swaponly", "candidate_x_swaponly_1e3", "cand_swaponly_matches_sv"),
        ):
            add_run(
                runs,
                {
                    "challenge": label,
                    "difficulty": row.get("difficulty", ""),
                    "qubits": row.get("n", ""),
                    "method": method,
                    "method_family": "heuristic",
                    "source_sessions": "algebraic_simplify",
                    "run_id": "static_summary",
                    "status": "static_analysis",
                    "source_path": source_rel,
                    "worktree": repo_root.name,
                    "commit": source_commit(repo_root, source),
                    "notes": f"linear_windows={row.get('linear_window_count', '')}; snapped={row.get('qiskit_snap_1e3_snapped', '')}",
                },
            )
            bitstring = clean(row.get(field, ""))
            if not bitstring:
                continue
            matches = row.get(match_field, "")
            validation = "sv_match" if matches == "True" else "heuristic_only"
            add_candidate(
                candidates,
                {
                    "challenge": label,
                    "difficulty": row.get("difficulty", ""),
                    "qubits": row.get("n", ""),
                    "method": method,
                    "method_family": "heuristic",
                    "source_sessions": "algebraic_simplify",
                    "run_id": "static_summary",
                    "rank_type": "static_heuristic",
                    "rank": 1,
                    "bitstring_qiskit": bitstring,
                    "selected": selected_flag(bitstring, challenges.get(label, {}).get("selected_bitstring", "")),
                    "validation": validation,
                    "status": "heuristic",
                    "source_path": source_rel,
                    "notes": f"exact_available_match={matches}",
                },
            )


def parse_method_selector(repo_root: Path) -> list[dict[str, str]]:
    source = repo_root / "reports/qmill_method_report.csv"
    rows: list[dict[str, str]] = []
    if not source.exists():
        return rows
    for row in read_csv(source):
        label = label_from_text(row.get("path", ""))
        if not label:
            continue
        rows.append(
            {
                "challenge": label,
                "difficulty": row.get("difficulty_group", ""),
                "qubits": row.get("num_qubits", ""),
                "first_action": row.get("first_action", ""),
                "best_method_id": row.get("best_method_id", ""),
                "best_method_name": row.get("best_method_name", ""),
                "best_score": row.get("best_score", ""),
                "mps_score": row.get("mps_score", ""),
                "tno_score": row.get("tno_score", ""),
                "mpo_unswapping_score": row.get("mpo_unswapping_score", ""),
                "source_path": relpath(source, repo_root),
            }
        )
    return rows


def label_in_path(label: str, path: Path) -> bool:
    normalized = path.name.replace("-", "_")
    return label in normalized or label in path.as_posix()


def figure_caption(path: Path, namespace: str) -> str:
    name = path.stem
    if "adaptive" in namespace or "probability_distributions" in path.as_posix():
        return f"Adaptive Aer MPS distribution: {path.name}"
    if "quimb_tree_graph_mps" in name:
        return f"Quimb graph-ordered MPS distribution: {path.name}"
    if "tree_tensor_mps" in name:
        return f"Tree/order MPS distribution: {path.name}"
    if "peaked" in name:
        return f"Peaked MPO/MPS distribution: {path.name}"
    if "statevector" in path.as_posix() or name.startswith("statevector"):
        return f"Statevector distribution: {path.name}"
    if name.startswith("mps") or "/mps/" in path.as_posix():
        return f"Aer MPS distribution: {path.name}"
    return f"Distribution figure: {path.name}"


def copy_figures(repo_root: Path, output_dir: Path, labels: set[str]) -> tuple[dict[str, list[dict[str, str]]], list[dict[str, str]]]:
    roots = [
        ("tree_tensor_sim", repo_root / "research/tree_tensor_sim_session/solution_book/figures"),
        ("peaked_all", repo_root / "outputs/peaked_circuit_sim_all/images"),
        ("peaked_pilot", repo_root / "outputs/peaked_circuit_sim_pilot/images"),
        ("selected_sim", repo_root / "outputs/sim_11_26_34_41_49/images"),
        ("adaptive_mps", repo_root / "agent_work/mps_adaptive_sweep/report/figures/probability_distributions"),
        ("quantum_peak_report", repo_root / "research/quantum_peak_session/reports/session_report/figures"),
        ("tree_tensor_report", repo_root / "research/quantum_peak_session/reports/tree_tensor_report/figures"),
    ]
    by_label: dict[str, list[dict[str, str]]] = defaultdict(list)
    global_figures: list[dict[str, str]] = []
    copied: set[tuple[str, str]] = set()
    for namespace, root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            matched = [label for label in labels if label_in_path(label, path)]
            rel = path.resolve().relative_to(root.resolve())
            dest = output_dir / "figures" / namespace / rel
            key = (namespace, rel.as_posix())
            if key not in copied:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
                copied.add(key)
            if matched:
                for label in matched:
                    by_label[label].append(
                        {
                            "challenge": label,
                            "caption": figure_caption(path, namespace),
                            "path": relpath(dest, output_dir),
                            "source": namespace,
                            "embedded": "1",
                        }
                    )
            elif namespace in {"adaptive_mps", "quantum_peak_report", "tree_tensor_report"}:
                global_figures.append(
                    {
                        "challenge": "",
                        "caption": figure_caption(path, namespace),
                        "path": relpath(dest, output_dir),
                        "source": namespace,
                        "embedded": "1",
                    }
                )

    for figures in by_label.values():
        figures.sort(key=lambda row: (row["source"], row["caption"]))
    global_figures.sort(key=lambda row: (row["source"], row["caption"]))
    return by_label, global_figures


def review_priority(review: str) -> int:
    reviews = set(split_joined(review))
    if "try_next" in reviews:
        return 0
    if "rejected" in reviews:
        return 8
    return 3


def rank_type_priority(rank_type: str) -> int:
    order = {
        "collector_selected": 0,
        "try_next": 1,
        "final_candidate": 2,
        "aggregate_candidate": 3,
        "marginal_candidate": 4,
        "exact_top": 5,
        "aggregate_rank": 6,
        "top1_vote_rank": 7,
        "sample_top": 8,
        "aggregate_top_counts": 9,
        "static_heuristic": 10,
        "raw_sample_top": 11,
    }
    return order.get(rank_type, 20)


def candidate_sort_key(row: dict[str, str]) -> tuple[int, int, int, str, str]:
    selected = 0 if row.get("selected") == "1" else 1
    return (
        review_priority(row.get("review", "")),
        selected,
        rank_type_priority(row.get("rank_type", "")),
        as_int(row.get("rank", "")) or 999999,
        row.get("method", ""),
    )


def best_candidates_by_method(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    best: dict[str, dict[str, str]] = {}
    for row in sorted(rows, key=candidate_sort_key):
        best.setdefault(row["method"], row)
    return best


def write_challenge_page(
    page: Path,
    meta: dict[str, str],
    selected_sources: list[dict[str, str]],
    runs: list[dict[str, str]],
    candidates: list[dict[str, str]],
    annotations: list[dict[str, str]],
    figures: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    output_dir: Path,
) -> None:
    label = meta["challenge"]
    selected = clean(meta.get("selected_bitstring", ""))
    selected_cell = f"`{selected}`" if selected else "blank"
    lines = [
        f"# Challenge {label}",
        "",
        f"- Difficulty: {meta.get('difficulty', '')}",
        f"- Qubits: {meta.get('qubits', '')}",
        f"- QASM: `{meta.get('qasm', '')}`",
        f"- Central selected answer: {selected_cell}",
        f"- Selected method: `{meta.get('selected_method', '')}`",
        f"- Selected review: `{meta.get('selected_review', '')}`" if meta.get("selected_review") else "- Selected review: none",
    ]
    if meta.get("try_next_bitstring"):
        lines.append(f"- Next candidate to try: `{meta['try_next_bitstring']}`")
    lines.extend(
        [
            f"- Candidate rows: {len(candidates)}",
            f"- Method runs: {len(runs)}",
            f"- Distribution figures: {len(figures)}",
            "",
            "## Selected Answer Sources",
            "",
            "| source | selected answer | method | validation | status | evidence |",
            "|---|---|---|---|---|---:|",
        ]
    )
    for row in selected_sources:
        bitstring = clean(row.get("selected_bitstring", ""))
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(row.get("source_session", "")),
                    f"`{bitstring}`" if bitstring else "blank",
                    md_escape(row.get("selected_method", "")),
                    md_escape(row.get("validation", "")),
                    md_escape(row.get("status", "")),
                    md_escape(row.get("evidence_count", "")),
                ]
            )
            + " |"
        )

    if annotations:
        lines.extend(
            [
                "",
                "## Review Notes",
                "",
                "| status | bitstring | note | date | source | sessions |",
                "|---|---|---|---|---|---|",
            ]
        )
        for row in annotations:
            lines.append(
                "| "
                + " | ".join(
                    [
                        md_escape(row.get("status", "")),
                        f"`{row.get('bitstring_qiskit', '')}`",
                        md_escape(row.get("note", "")),
                        md_escape(row.get("date", "")),
                        md_escape(row.get("source", "")),
                        md_escape(row.get("source_sessions", "")),
                    ]
                )
                + " |"
            )

    lines.extend(["", "## Method Summary", ""])
    method_runs = defaultdict(list)
    for row in runs:
        method_runs[row["method"]].append(row)
    best = best_candidates_by_method(candidates)
    lines.extend(
        [
            "| method | family | runs | statuses | best or marked candidate | rank_type | score | fraction | review | sources |",
            "|---|---|---:|---|---|---|---:|---:|---|---|",
        ]
    )
    for method in sorted(set(method_runs) | set(best)):
        run_rows = method_runs.get(method, [])
        cand = best.get(method, {})
        statuses = ",".join(sorted({clean(row.get("status", "")) for row in run_rows if clean(row.get("status", ""))}))
        sources = merge_text(
            ",".join(row.get("source_sessions", "") for row in run_rows),
            cand.get("source_sessions", ""),
        )
        bitstring = clean(cand.get("bitstring_qiskit", ""))
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(method),
                    md_escape(cand.get("method_family") or (run_rows[0].get("method_family", "") if run_rows else "")),
                    str(len(run_rows)),
                    md_escape(statuses),
                    f"`{bitstring}`" if bitstring else "",
                    md_escape(cand.get("rank_type", "")),
                    md_escape(cand.get("score", "")),
                    md_escape(cand.get("fraction", "")),
                    md_escape(cand.get("review", "")),
                    md_escape(sources),
                ]
            )
            + " |"
        )

    if selector_rows:
        lines.extend(
            [
                "",
                "## Method Selector",
                "",
                "| first action | best method | best score | MPS | TNO | MPO-unswap |",
                "|---|---|---:|---:|---:|---:|",
            ]
        )
        for row in selector_rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        md_escape(row.get("first_action", "")),
                        md_escape(row.get("best_method_name", "")),
                        md_escape(row.get("best_score", "")),
                        md_escape(row.get("mps_score", "")),
                        md_escape(row.get("tno_score", "")),
                        md_escape(row.get("mpo_unswapping_score", "")),
                    ]
                )
                + " |"
            )

    lines.extend(["", "## Distribution Figures", ""])
    if figures:
        for figure in figures:
            target = output_dir / figure["path"]
            link = rel_link(target, page.parent)
            lines.extend([f"### {md_escape(figure['caption'])}", "", f"![{md_escape(figure['caption'])}]({link})", ""])
    else:
        lines.extend(["No committed distribution figure was matched for this challenge.", ""])

    lines.extend(
        [
            "## Candidate Rows",
            "",
            "| review | selected | method | rank_type | rank | bitstring | score | count | support | fraction | validation | status | sources | source path | notes |",
            "|---|---:|---|---|---:|---|---:|---:|---:|---:|---|---|---|---|---|",
        ]
    )
    for row in sorted(candidates, key=candidate_sort_key):
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(row.get("review", "")),
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
                    md_escape(row.get("source_sessions", "")),
                    f"`{row.get('source_path', '')}`",
                    md_escape(row.get("notes", "")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Method Runs",
            "",
            "| method | run_id | status | backend | shots | max_bond | seconds | source path | notes |",
            "|---|---|---|---|---:|---:|---:|---|---|",
        ]
    )
    for row in sorted(runs, key=lambda item: (item["method"], item["run_id"], item["source_path"])):
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(row.get("method", "")),
                    md_escape(row.get("run_id", "")),
                    md_escape(row.get("status", "")),
                    md_escape(row.get("backend", "")),
                    md_escape(row.get("shots", "")),
                    md_escape(row.get("max_bond", "")),
                    md_escape(row.get("seconds", "")),
                    f"`{row.get('source_path', '')}`",
                    md_escape(row.get("notes", "")),
                ]
            )
            + " |"
        )
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("\n".join(lines) + "\n")


def write_readme(
    output_dir: Path,
    challenges: list[dict[str, str]],
    candidates_by_challenge: dict[str, list[dict[str, str]]],
    runs_by_challenge: dict[str, list[dict[str, str]]],
    figures_by_challenge: dict[str, list[dict[str, str]]],
    global_figures: list[dict[str, str]],
    method_counts: Counter[str],
) -> None:
    selected_count = sum(1 for row in challenges if clean(row.get("selected_bitstring", "")))
    lines = [
        "# Central Challenge Solutions",
        "",
        "This is the generated central lookup for every challenge, selected answer, alternate candidate, attempted method, and matched distribution figure.",
        "",
        "The original session folders remain as provenance. Use this folder when you want to quickly check one challenge across all pushed work.",
        "",
        "## Summary",
        "",
        f"- Challenges: {len(challenges)}",
        f"- Challenges with selected answers: {selected_count}",
        f"- Candidate rows: {sum(len(rows) for rows in candidates_by_challenge.values())}",
        f"- Method runs: {sum(len(rows) for rows in runs_by_challenge.values())}",
        f"- Matched challenge figures: {sum(len(rows) for rows in figures_by_challenge.values())}",
        "",
        "## Challenges",
        "",
        "| challenge | difficulty | qubits | selected answer | review | next candidate | methods | candidates | figures | page |",
        "|---|---|---:|---|---|---|---:|---:|---:|---|",
    ]
    for row in challenges:
        label = row["challenge"]
        selected = clean(row.get("selected_bitstring", ""))
        try_next = clean(row.get("try_next_bitstring", ""))
        page = output_dir / "challenges" / f"{label}.md"
        lines.append(
            "| "
            + " | ".join(
                [
                    label,
                    md_escape(row.get("difficulty", "")),
                    md_escape(row.get("qubits", "")),
                    f"`{selected}`" if selected else "blank",
                    md_escape(row.get("selected_review", "")),
                    f"`{try_next}`" if try_next else "",
                    str(len({item["method"] for item in runs_by_challenge.get(label, [])})),
                    str(len(candidates_by_challenge.get(label, []))),
                    str(len(figures_by_challenge.get(label, []))),
                    f"[open]({rel_link(page, output_dir)})",
                ]
            )
            + " |"
        )

    lines.extend(["", "## Methods", "", "| method | run rows |", "|---|---:|"])
    for method, count in sorted(method_counts.items()):
        lines.append(f"| {md_escape(method)} | {count} |")

    if global_figures:
        lines.extend(["", "## Global Figures", ""])
        for figure in global_figures:
            target = output_dir / figure["path"]
            lines.append(f"- [{md_escape(figure['caption'])}]({rel_link(target, output_dir)})")

    lines.extend(
        [
            "",
            "## Generated Tables",
            "",
            "- `tables/challenges.tsv`: one canonical row per challenge.",
            "- `tables/selected_sources.tsv`: selected answers by original session package.",
            "- `tables/method_runs.tsv`: every normalized or raw method attempt captured by this generator.",
            "- `tables/candidates.tsv`: all candidate bitstrings, including alternates and reviewed rows.",
            "- `tables/figures.tsv`: copied figure inventory for challenge pages.",
            "- `tables/method_selector.tsv`: method-selector recommendations kept separate from candidate answers.",
            "",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(lines))


def build(repo_root: Path) -> dict[str, Any]:
    output_dir = repo_root / "research/challenge_solutions"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    challenges: dict[str, dict[str, str]] = {}
    selected_sources: list[dict[str, str]] = []
    runs: dict[tuple[str, ...], dict[str, str]] = {}
    candidates: dict[tuple[str, ...], dict[str, str]] = {}
    annotations: list[dict[str, str]] = []

    load_existing_indexes(repo_root, challenges, selected_sources, runs, candidates, annotations)
    parse_adaptive_mps(repo_root, challenges, runs, candidates)
    parse_tno_outputs(repo_root, challenges, runs, candidates)
    parse_mpo_test_outputs(repo_root, challenges, runs)
    parse_opus_combined(repo_root, challenges, runs, candidates)
    parse_algebraic_simplify(repo_root, challenges, runs, candidates)
    annotations = merge_annotations(annotations)
    apply_annotations(challenges, candidates, annotations)

    selector_rows = parse_method_selector(repo_root)
    selector_by_challenge: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selector_rows:
        selector_by_challenge[row["challenge"]].append(row)

    challenge_rows = sorted(
        challenges.values(),
        key=lambda row: challenge_sort_key(row["challenge"], row.get("difficulty", "")),
    )
    labels = {row["challenge"] for row in challenge_rows}
    figures_by_challenge, global_figures = copy_figures(repo_root, output_dir, labels)

    candidates_by_challenge: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates.values():
        candidates_by_challenge[row["challenge"]].append(row)

    runs_by_challenge: dict[str, list[dict[str, str]]] = defaultdict(list)
    method_counts: Counter[str] = Counter()
    for row in runs.values():
        runs_by_challenge[row["challenge"]].append(row)
        method_counts[row["method"]] += 1

    annotations_by_challenge: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in annotations:
        annotations_by_challenge[row["challenge"]].append(row)

    selected_by_challenge: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selected_sources:
        selected_by_challenge[row["challenge"]].append(row)

    for row in challenge_rows:
        label = row["challenge"]
        write_challenge_page(
            output_dir / "challenges" / f"{label}.md",
            row,
            selected_by_challenge.get(label, []),
            runs_by_challenge.get(label, []),
            candidates_by_challenge.get(label, []),
            annotations_by_challenge.get(label, []),
            figures_by_challenge.get(label, []),
            selector_by_challenge.get(label, []),
            output_dir,
        )

    table_dir = output_dir / "tables"
    write_tsv(table_dir / "challenges.tsv", CHALLENGE_FIELDS, challenge_rows)
    write_tsv(table_dir / "selected_sources.tsv", SELECTED_SOURCE_FIELDS, selected_sources)
    write_tsv(table_dir / "method_runs.tsv", RUN_FIELDS, sorted(runs.values(), key=lambda row: (row["challenge"], row["method"], row["run_id"])))
    write_tsv(table_dir / "candidates.tsv", CANDIDATE_FIELDS, sorted(candidates.values(), key=lambda row: (row["challenge"],) + candidate_sort_key(row)))
    figure_rows = [figure for figures in figures_by_challenge.values() for figure in figures] + global_figures
    write_tsv(table_dir / "figures.tsv", FIGURE_FIELDS, sorted(figure_rows, key=lambda row: (row["challenge"], row["source"], row["path"])))
    write_tsv(table_dir / "annotations.tsv", ANNOTATION_FIELDS, annotations)
    write_tsv(table_dir / "method_selector.tsv", METHOD_SELECTOR_FIELDS, selector_rows)
    for method in sorted({row["method"] for row in candidates.values()}):
        method_rows = [row for row in candidates.values() if row["method"] == method]
        write_tsv(output_dir / "by_method" / f"{method}.tsv", CANDIDATE_FIELDS, sorted(method_rows, key=lambda row: (row["challenge"],) + candidate_sort_key(row)))

    write_readme(output_dir, challenge_rows, candidates_by_challenge, runs_by_challenge, figures_by_challenge, global_figures, method_counts)

    summary = {
        "challenge_count": len(challenge_rows),
        "selected_count": sum(1 for row in challenge_rows if clean(row.get("selected_bitstring", ""))),
        "candidate_count": len(candidates),
        "method_run_count": len(runs),
        "figure_count": len(figure_rows),
        "method_count": len(method_counts),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build(args.repo_root.resolve())
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
