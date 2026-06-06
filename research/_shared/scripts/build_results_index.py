#!/usr/bin/env python3
"""Build normalized results indexes for the research packages.

The indexes are intentionally generated artifacts.  Raw result files keep their
native layout; this script creates stable TSV/Markdown views for quick review.
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
from dataclasses import dataclass
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

CHALLENGE_FIELDS = [
    "challenge",
    "difficulty",
    "qubits",
    "qasm",
    "selected_bitstring",
    "selected_method",
    "validation",
    "top_fraction",
    "evidence_count",
]

SELECTED_FIELDS = [
    "challenge",
    "difficulty",
    "qubits",
    "selected_bitstring",
    "selected_method",
    "validation",
    "top_fraction",
    "evidence_count",
    "status",
]

RUN_FIELDS = [
    "session",
    "challenge",
    "difficulty",
    "qubits",
    "method",
    "method_family",
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
    "session",
    "challenge",
    "difficulty",
    "qubits",
    "method",
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
]


@dataclass(frozen=True)
class SessionConfig:
    name: str
    session_dir: Path
    collector_tsv: Path
    collector_evidence_json: Path
    raw_roots: tuple[Path, ...]


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
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


def challenge_sort_key(label: str, difficulty: str = "") -> tuple[int, int, int, str]:
    left = right = 9999
    if "_" in label:
        a, b = label.split("_", 1)
        left = as_int(a) or left
        right = as_int(b) or right
    return (DIFFICULTY_ORDER.get(difficulty, 8), right, left, label)


def relpath(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return os.path.relpath(path.resolve(), repo_root.resolve())


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


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
    """Return the last commit that touched a tracked source artifact.

    Generated indexes should not change just because the index commit changed.
    For untracked local raw artifacts, fall back to the raw-root HEAD.
    """
    root = root.resolve()
    try:
        rel = path.resolve().relative_to(root).as_posix()
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
    if method.startswith("exact") or method in {"statevector", "selected_statevector"}:
        return "exact"
    if method.startswith("quimb"):
        return "quimb"
    if method.startswith("aer_mps") or method.startswith("aer_tree_mps"):
        return "mps"
    if method.startswith("peaked"):
        return "mpo"
    if method.startswith("sparse"):
        return "sparse"
    if method.startswith("collector"):
        return "collector"
    return "other"


def bitstring_from_item(item: Any) -> str:
    if isinstance(item, dict):
        return as_text(item.get("bitstring") or item.get("candidate") or item.get("bitstring_qiskit"))
    if isinstance(item, (list, tuple)) and item:
        return as_text(item[0])
    return ""


def count_from_item(item: Any) -> str:
    if isinstance(item, dict):
        return as_text(item.get("count"))
    if isinstance(item, (list, tuple)) and len(item) > 1:
        return as_text(item[1])
    return ""


def candidate_status(bitstring: str, selected: str) -> str:
    return "1" if bitstring and selected and bitstring == selected else "0"


def source_challenge(path: Path, data: dict[str, Any] | None = None) -> str:
    data = data or {}
    for key in ("challenge_label", "challenge"):
        if data.get(key):
            return as_text(data[key])
    for key in ("qasm", "path", "circuit"):
        if data.get(key):
            match = CHALLENGE_RE.search(as_text(data[key]))
            if match:
                return match.group(1)
    match = CHALLENGE_RE.search(path.as_posix())
    if match:
        return match.group(1)
    stem = path.stem
    match = re.search(r"(\d+_\d+)", stem)
    return match.group(1) if match else ""


def qasm_from_data(data: dict[str, Any]) -> str:
    return as_text(data.get("qasm") or data.get("path") or data.get("circuit"))


def backend_from_data(data: dict[str, Any]) -> str:
    backend = data.get("backend")
    if isinstance(backend, dict):
        return as_text(backend.get("selected") or backend.get("requested"))
    return as_text(backend)


def normalize_tree_method(path: Path, data: dict[str, Any]) -> str:
    folder = path.parent.parent.name
    raw_method = as_text(data.get("method"))
    name = path.name

    quimb_map = {
        "all": "quimb_gpu_all",
        "all_cpu": "quimb_cpu_all",
        "rcm_cpu": "quimb_rcm_cpu",
        "mst_cpu": "quimb_mst_cpu",
        "degree_cpu": "quimb_degree_cpu",
        "mid_cpu": "quimb_mid_cpu",
        "fast_cpu": "quimb_fast_cpu",
        "identity_cpu": "quimb_identity_cpu",
        "opt_u3_gpu": "quimb_opt_u3_gpu",
        "quimb_pilot": "quimb_pilot",
    }
    if "quimb_tree_graph_mps" in name or raw_method == "quimb_graph_tree_ordered_circuit_mps":
        return quimb_map.get(folder, f"quimb_{folder}")
    if folder == "sparse_beam":
        return "sparse_beam"
    if folder == "peaked_unswap_gpu" or raw_method == "peaked_mpo_unswap":
        return "peaked_mpo_unswap_gpu"
    if "tree_tensor_mps" in name or raw_method == "tree_graph_ordered_mps_fallback":
        return f"aer_tree_mps_{folder}"
    return raw_method or folder


def add_run(
    runs: dict[tuple[str, str, str, str, str], dict[str, str]],
    row: dict[str, Any],
) -> None:
    normalized = {field: as_text(row.get(field, "")) for field in RUN_FIELDS}
    key = (
        normalized["session"],
        normalized["challenge"],
        normalized["method"],
        normalized["run_id"],
        normalized["source_path"],
    )
    if key not in runs:
        runs[key] = normalized


def add_candidate(
    candidates: dict[tuple[str, str, str, str, str, str, str], dict[str, str]],
    row: dict[str, Any],
) -> None:
    normalized = {field: as_text(row.get(field, "")) for field in CANDIDATE_FIELDS}
    if not normalized["bitstring_qiskit"]:
        return
    key = (
        normalized["session"],
        normalized["challenge"],
        normalized["method"],
        normalized["run_id"],
        normalized["rank_type"],
        normalized["rank"],
        normalized["bitstring_qiskit"],
    )
    if key not in candidates:
        candidates[key] = normalized


def selected_map(challenges: dict[str, dict[str, str]]) -> dict[str, str]:
    return {label: row.get("selected_bitstring", "") for label, row in challenges.items()}


def load_collector(session: SessionConfig, repo_root: Path) -> tuple[dict[str, dict[str, str]], list[dict[str, Any]]]:
    challenges: dict[str, dict[str, str]] = {}
    evidence_records: list[dict[str, Any]] = []

    if session.collector_tsv.exists():
        with session.collector_tsv.open(newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for raw in reader:
                label = raw.get("challenge", "")
                if not label:
                    continue
                candidate = raw.get("candidate", "")
                challenges[label] = {
                    "challenge": label,
                    "difficulty": raw.get("difficulty", ""),
                    "qubits": raw.get("qubits", ""),
                    "qasm": raw.get("qasm", ""),
                    "selected_bitstring": candidate,
                    "selected_method": raw.get("source", ""),
                    "validation": raw.get("validation", ""),
                    "top_fraction": raw.get("top_fraction", ""),
                    "evidence_count": raw.get("evidence_count", ""),
                }

    if session.collector_evidence_json.exists():
        data = read_json(session.collector_evidence_json)
        if isinstance(data, list):
            evidence_records = data
            for item in data:
                label = as_text(item.get("label")) or source_challenge(session.collector_evidence_json, item)
                if not label:
                    continue
                row = challenges.setdefault(
                    label,
                    {
                        "challenge": label,
                        "difficulty": as_text(item.get("difficulty")),
                        "qubits": as_text(item.get("num_qubits")),
                        "qasm": as_text(item.get("qasm")),
                        "selected_bitstring": "",
                        "selected_method": "",
                        "validation": "",
                        "top_fraction": "",
                        "evidence_count": "0",
                    },
                )
                row["evidence_count"] = as_text(len(item.get("evidence") or []))
                if item.get("difficulty") and not row["difficulty"]:
                    row["difficulty"] = as_text(item.get("difficulty"))
                if item.get("num_qubits") and not row["qubits"]:
                    row["qubits"] = as_text(item.get("num_qubits"))
                if item.get("qasm") and not row["qasm"]:
                    row["qasm"] = as_text(item.get("qasm"))
                selected = item.get("selected") or {}
                if selected and not row["selected_bitstring"]:
                    row["selected_bitstring"] = as_text(selected.get("candidate"))
                    row["selected_method"] = as_text(selected.get("source"))
                    row["validation"] = as_text(selected.get("validation"))
                    row["top_fraction"] = as_text(selected.get("top_fraction"))

    return challenges, evidence_records


def add_collector_rows(
    session: SessionConfig,
    repo_root: Path,
    challenges: dict[str, dict[str, str]],
    evidence_records: list[dict[str, Any]],
    runs: dict[tuple[str, str, str, str, str], dict[str, str]],
    candidates: dict[tuple[str, str, str, str, str, str, str], dict[str, str]],
) -> None:
    selected = selected_map(challenges)
    collector_source = relpath(session.collector_tsv, repo_root)
    collector_commit = source_commit(repo_root, session.collector_tsv)

    for label, row in challenges.items():
        if row.get("selected_bitstring"):
            run_id = f"collector_selected:{label}"
            add_run(
                runs,
                {
                    "session": session.name,
                    "challenge": label,
                    "difficulty": row.get("difficulty"),
                    "qubits": row.get("qubits"),
                    "method": "collector_snapshot",
                    "method_family": "collector",
                    "run_id": run_id,
                    "status": row.get("validation"),
                    "source_path": collector_source,
                    "worktree": repo_root.name,
                    "commit": collector_commit,
                    "notes": f"selected from {row.get('selected_method')}",
                },
            )
            add_candidate(
                candidates,
                {
                    "session": session.name,
                    "challenge": label,
                    "difficulty": row.get("difficulty"),
                    "qubits": row.get("qubits"),
                    "method": "collector_snapshot",
                    "run_id": run_id,
                    "rank_type": "collector_selected",
                    "rank": 1,
                    "bitstring_qiskit": row.get("selected_bitstring"),
                    "score_type": "sample_fraction" if row.get("top_fraction") else "",
                    "score": row.get("top_fraction"),
                    "fraction": row.get("top_fraction"),
                    "selected": "1",
                    "validation": row.get("validation"),
                    "status": row.get("validation"),
                    "source_path": collector_source,
                    "notes": row.get("selected_method"),
                },
            )

    evidence_source = relpath(session.collector_evidence_json, repo_root)
    evidence_commit = source_commit(repo_root, session.collector_evidence_json)
    for item in evidence_records:
        label = as_text(item.get("label"))
        meta = challenges.get(label, {})
        for rank, ev in enumerate(item.get("evidence") or [], start=1):
            method = as_text(ev.get("source")) or "collector_evidence"
            run_id = f"collector_evidence:{label}:{rank}"
            ev_source = as_text(ev.get("path")) or evidence_source
            ev_source_path = repo_root / ev_source
            ev_commit = source_commit(repo_root, ev_source_path) if ev_source_path.exists() else evidence_commit
            add_run(
                runs,
                {
                    "session": session.name,
                    "challenge": label,
                    "difficulty": meta.get("difficulty") or item.get("difficulty"),
                    "qubits": meta.get("qubits") or item.get("num_qubits"),
                    "method": method,
                    "method_family": method_family(method),
                    "run_id": run_id,
                    "status": ev.get("validation"),
                    "source_path": ev_source,
                    "worktree": repo_root.name,
                    "commit": ev_commit,
                    "shots": "",
                    "max_bond": ev.get("max_bond"),
                    "seconds": ev.get("seconds"),
                    "notes": f"collector priority {as_text(ev.get('priority'))}",
                },
            )
            bitstring = as_text(ev.get("candidate"))
            add_candidate(
                candidates,
                {
                    "session": session.name,
                    "challenge": label,
                    "difficulty": meta.get("difficulty") or item.get("difficulty"),
                    "qubits": meta.get("qubits") or item.get("num_qubits"),
                    "method": method,
                    "run_id": run_id,
                    "rank_type": "collector_evidence",
                    "rank": rank,
                    "bitstring_qiskit": bitstring,
                    "score_type": "sample_fraction" if ev.get("top_fraction") not in (None, "") else "",
                    "score": ev.get("top_fraction"),
                    "fraction": ev.get("top_fraction"),
                    "selected": candidate_status(bitstring, selected.get(label, "")),
                    "validation": ev.get("validation"),
                    "status": ev.get("validation"),
                    "source_path": ev_source,
                    "notes": f"collector priority {as_text(ev.get('priority'))}",
                },
            )


def parse_exact_jsonl(
    session: SessionConfig,
    repo_root: Path,
    challenges: dict[str, dict[str, str]],
    runs: dict[tuple[str, str, str, str, str], dict[str, str]],
    candidates: dict[tuple[str, str, str, str, str, str, str], dict[str, str]],
) -> None:
    selected = selected_map(challenges)
    for root in session.raw_roots:
        path = root / "agent_work/exact_baseline/peaks_exact.jsonl"
        if not path.exists():
            continue
        commit = source_commit(root, path)
        for data in read_jsonl(path):
            label = source_challenge(path, data)
            if label not in challenges:
                continue
            meta = challenges[label]
            source = relpath(path, repo_root)
            run_id = "exact_statevector"
            add_run(
                runs,
                {
                    "session": session.name,
                    "challenge": label,
                    "difficulty": meta.get("difficulty") or data.get("difficulty"),
                    "qubits": meta.get("qubits") or data.get("qubits"),
                    "method": "exact_statevector",
                    "method_family": "exact",
                    "run_id": run_id,
                    "status": "ok",
                    "source_path": source,
                    "worktree": root.name,
                    "commit": commit,
                    "backend": data.get("backend"),
                    "seconds": data.get("elapsed_seconds"),
                    "notes": "exact statevector top list",
                },
            )
            for rank, item in enumerate(data.get("top") or [], start=1):
                bitstring = bitstring_from_item(item)
                add_candidate(
                    candidates,
                    {
                        "session": session.name,
                        "challenge": label,
                        "difficulty": meta.get("difficulty") or data.get("difficulty"),
                        "qubits": meta.get("qubits") or data.get("qubits"),
                        "method": "exact_statevector",
                        "run_id": run_id,
                        "rank_type": "exact_top",
                        "rank": item.get("rank", rank) if isinstance(item, dict) else rank,
                        "bitstring_qiskit": bitstring,
                        "score_type": "probability",
                        "score": item.get("probability") if isinstance(item, dict) else "",
                        "fraction": item.get("probability") if isinstance(item, dict) else "",
                        "selected": candidate_status(bitstring, selected.get(label, "")),
                        "validation": "exact",
                        "status": "ok",
                        "source_path": source,
                    },
                )


def parse_mps_distill_summary(
    session: SessionConfig,
    repo_root: Path,
    challenges: dict[str, dict[str, str]],
    runs: dict[tuple[str, str, str, str, str], dict[str, str]],
    candidates: dict[tuple[str, str, str, str, str, str, str], dict[str, str]],
) -> None:
    selected = selected_map(challenges)
    seen_sources: set[Path] = set()
    for root in session.raw_roots:
        path = root / "agent_work/mps_distill/summaries/pilot_summary.json"
        if not path.exists() or path.resolve() in seen_sources:
            continue
        seen_sources.add(path.resolve())
        data = read_json(path)
        commit = source_commit(root, path)
        source = relpath(path, repo_root)
        for item in data.get("circuits") or []:
            label = source_challenge(path, {"circuit": item.get("circuit")})
            if label not in challenges:
                continue
            meta = challenges[label]
            run_id = "mps_distill_pilot"
            add_run(
                runs,
                {
                    "session": session.name,
                    "challenge": label,
                    "difficulty": meta.get("difficulty"),
                    "qubits": meta.get("qubits") or item.get("num_qubits"),
                    "method": "aer_mps_pilot",
                    "method_family": "mps",
                    "run_id": run_id,
                    "status": item.get("classification", "ok"),
                    "source_path": source,
                    "worktree": root.name,
                    "commit": commit,
                    "shots": (item.get("high_config") or {}).get("shots"),
                    "max_bond": (item.get("high_config") or {}).get("bond_dim"),
                    "seconds": item.get("mean_total_seconds"),
                    "notes": f"ok_trials={as_text(item.get('ok_trials'))}; expected={as_text(item.get('expected_trials'))}",
                },
            )
            for rank_type, score_type in (
                ("aggregate_rank", "aggregate_fraction"),
                ("top1_vote_rank", "vote_fraction"),
            ):
                for rank, ranked in enumerate(item.get(rank_type) or [], start=1):
                    bitstring = bitstring_from_item(ranked)
                    add_candidate(
                        candidates,
                        {
                            "session": session.name,
                            "challenge": label,
                            "difficulty": meta.get("difficulty"),
                            "qubits": meta.get("qubits") or item.get("num_qubits"),
                            "method": "aer_mps_pilot",
                            "run_id": run_id,
                            "rank_type": rank_type,
                            "rank": rank,
                            "bitstring_qiskit": bitstring,
                            "score_type": score_type,
                            "score": ranked.get("fraction") if isinstance(ranked, dict) else "",
                            "support": ranked.get("support") if isinstance(ranked, dict) else "",
                            "fraction": ranked.get("fraction") if isinstance(ranked, dict) else "",
                            "selected": candidate_status(bitstring, selected.get(label, "")),
                            "validation": item.get("classification"),
                            "status": item.get("classification"),
                            "source_path": source,
                        },
                    )


def parse_selected_sim_outputs(
    session: SessionConfig,
    repo_root: Path,
    challenges: dict[str, dict[str, str]],
    runs: dict[tuple[str, str, str, str, str], dict[str, str]],
    candidates: dict[tuple[str, str, str, str, str, str, str], dict[str, str]],
) -> None:
    selected = selected_map(challenges)
    for root in session.raw_roots:
        json_dir = root / "outputs/sim_11_26_34_41_49/json"
        if not json_dir.exists():
            continue
        for path in sorted(json_dir.glob("*.json")):
            data = read_json(path)
            label = source_challenge(path, data)
            if label not in challenges:
                continue
            meta = challenges[label]
            method = "aer_mps_selected" if data.get("method") == "mps" else as_text(data.get("method"))
            if data.get("method") == "statevector":
                method = "selected_statevector"
            source = relpath(path, repo_root)
            commit = source_commit(root, path)
            run_id = path.stem
            add_run(
                runs,
                {
                    "session": session.name,
                    "challenge": label,
                    "difficulty": meta.get("difficulty"),
                    "qubits": meta.get("qubits") or data.get("num_qubits"),
                    "method": method,
                    "method_family": method_family(method),
                    "run_id": run_id,
                    "status": data.get("status"),
                    "source_path": source,
                    "worktree": root.name,
                    "commit": commit,
                    "shots": data.get("shots"),
                    "max_bond": data.get("bond_dim"),
                    "seed": data.get("seed"),
                    "notes": data.get("reason", ""),
                },
            )
            if data.get("method") == "mps":
                shots = as_float(data.get("shots")) or 0.0
                counts = data.get("top_counts") or {}
                probabilities = data.get("top_probability_estimates") or {}
                iterable = counts.items() if isinstance(counts, dict) else []
                for rank, (bitstring, count) in enumerate(iterable, start=1):
                    fraction = probabilities.get(bitstring)
                    if fraction is None and shots:
                        fraction = (as_float(count) or 0.0) / shots
                    add_candidate(
                        candidates,
                        {
                            "session": session.name,
                            "challenge": label,
                            "difficulty": meta.get("difficulty"),
                            "qubits": meta.get("qubits") or data.get("num_qubits"),
                            "method": method,
                            "run_id": run_id,
                            "rank_type": "sample_top",
                            "rank": rank,
                            "bitstring_qiskit": bitstring,
                            "score_type": "sample_fraction",
                            "score": fraction,
                            "count": count,
                            "fraction": fraction,
                            "selected": candidate_status(bitstring, selected.get(label, "")),
                            "status": data.get("status"),
                            "source_path": source,
                        },
                    )
            elif data.get("method") == "statevector":
                probs = data.get("top_probabilities") or {}
                for rank, (bitstring, probability) in enumerate(probs.items(), start=1):
                    add_candidate(
                        candidates,
                        {
                            "session": session.name,
                            "challenge": label,
                            "difficulty": meta.get("difficulty"),
                            "qubits": meta.get("qubits") or data.get("num_qubits"),
                            "method": method,
                            "run_id": run_id,
                            "rank_type": "exact_top",
                            "rank": rank,
                            "bitstring_qiskit": bitstring,
                            "score_type": "probability",
                            "score": probability,
                            "fraction": probability,
                            "selected": candidate_status(bitstring, selected.get(label, "")),
                            "validation": "exact",
                            "status": data.get("status"),
                            "source_path": source,
                        },
                    )


def parse_tree_tensor_outputs(
    session: SessionConfig,
    repo_root: Path,
    challenges: dict[str, dict[str, str]],
    runs: dict[tuple[str, str, str, str, str], dict[str, str]],
    candidates: dict[tuple[str, str, str, str, str, str, str], dict[str, str]],
) -> None:
    selected = selected_map(challenges)
    for root in session.raw_roots:
        base = root / "outputs/tree_tensor_sim"
        if not base.exists():
            continue
        for path in sorted(base.glob("*/json/*.json")):
            data = read_json(path)
            label = source_challenge(path, data)
            if label not in challenges:
                continue
            meta = challenges[label]
            method = normalize_tree_method(path, data)
            params = data.get("parameters") or {}
            source = relpath(path, repo_root)
            commit = source_commit(root, path)
            status = as_text(data.get("status") or "ok")
            base_run = path.stem

            if data.get("trials"):
                for trial_index, trial in enumerate(data.get("trials") or [], start=1):
                    order_method = as_text(trial.get("order_method"))
                    run_id = f"{base_run}:trial{trial_index}:{order_method}:bd{as_text(trial.get('bond_dim'))}:seed{as_text(trial.get('seed'))}"
                    add_run(
                        runs,
                        {
                            "session": session.name,
                            "challenge": label,
                            "difficulty": meta.get("difficulty") or data.get("difficulty"),
                            "qubits": meta.get("qubits") or data.get("num_qubits"),
                            "method": method,
                            "method_family": method_family(method),
                            "run_id": run_id,
                            "status": trial.get("status") or status,
                            "source_path": source,
                            "worktree": root.name,
                            "commit": commit,
                            "backend": backend_from_data(data),
                            "shots": trial.get("shots"),
                            "max_bond": trial.get("bond_dim"),
                            "seed": trial.get("seed"),
                            "ordering": order_method,
                            "seconds": trial.get("seconds"),
                            "notes": as_text(trial.get("ansatz_status") or data.get("ansatz_status")),
                        },
                    )
                    counts = trial.get("top_counts_qiskit_order") or {}
                    shots = as_float(trial.get("shots")) or 0.0
                    for rank, (bitstring, count) in enumerate(counts.items(), start=1):
                        fraction = (as_float(count) or 0.0) / shots if shots else ""
                        add_candidate(
                            candidates,
                            {
                                "session": session.name,
                                "challenge": label,
                                "difficulty": meta.get("difficulty") or data.get("difficulty"),
                                "qubits": meta.get("qubits") or data.get("num_qubits"),
                                "method": method,
                                "run_id": run_id,
                                "rank_type": "sample_top",
                                "rank": rank,
                                "bitstring_qiskit": bitstring,
                                "score_type": "sample_fraction",
                                "score": fraction,
                                "count": count,
                                "fraction": fraction,
                                "selected": candidate_status(bitstring, selected.get(label, "")),
                                "validation": data.get("validation", ""),
                                "status": trial.get("status") or status,
                                "source_path": source,
                            },
                        )
                final = data.get("final_candidate") or {}
                bitstring = as_text(final.get("candidate_qiskit_order"))
                if bitstring:
                    add_candidate(
                        candidates,
                        {
                            "session": session.name,
                            "challenge": label,
                            "difficulty": meta.get("difficulty") or data.get("difficulty"),
                            "qubits": meta.get("qubits") or data.get("num_qubits"),
                            "method": method,
                            "run_id": base_run,
                            "rank_type": "final_candidate",
                            "rank": 1,
                            "bitstring_qiskit": bitstring,
                            "score_type": "probability" if final.get("score") not in (None, "") else "",
                            "score": final.get("score"),
                            "fraction": final.get("score"),
                            "selected": candidate_status(bitstring, selected.get(label, "")),
                            "validation": data.get("validation", ""),
                            "status": status,
                            "source_path": source,
                            "notes": final.get("source", ""),
                        },
                    )
                continue

            add_run(
                runs,
                {
                    "session": session.name,
                    "challenge": label,
                    "difficulty": meta.get("difficulty") or data.get("difficulty"),
                    "qubits": meta.get("qubits") or data.get("num_qubits"),
                    "method": method,
                    "method_family": method_family(method),
                    "run_id": base_run,
                    "status": status,
                    "source_path": source,
                    "worktree": root.name,
                    "commit": commit,
                    "backend": backend_from_data(data),
                    "shots": params.get("samples") or params.get("shots"),
                    "max_bond": params.get("max_bond") or params.get("mps_max_bond"),
                    "seed": params.get("seed"),
                    "ordering": params.get("order_method") or (data.get("ordering") or {}).get("method", ""),
                    "seconds": data.get("total_seconds") or data.get("seconds"),
                    "notes": data.get("method_classification") or data.get("candidate_strategy") or "",
                },
            )

            sampling = data.get("sampling") or {}
            observed = as_float(sampling.get("observed_samples") or params.get("samples")) or 0.0
            top_qiskit = sampling.get("top_qiskit_order") or []
            for rank, item in enumerate(top_qiskit, start=1):
                bitstring = bitstring_from_item(item)
                count = count_from_item(item)
                fraction = (as_float(count) or 0.0) / observed if observed else ""
                add_candidate(
                    candidates,
                    {
                        "session": session.name,
                        "challenge": label,
                        "difficulty": meta.get("difficulty") or data.get("difficulty"),
                        "qubits": meta.get("qubits") or data.get("num_qubits"),
                        "method": method,
                        "run_id": base_run,
                        "rank_type": "sample_top",
                        "rank": rank,
                        "bitstring_qiskit": bitstring,
                        "score_type": "sample_fraction",
                        "score": fraction,
                        "count": count,
                        "fraction": fraction,
                        "selected": candidate_status(bitstring, selected.get(label, "")),
                        "validation": data.get("validation", ""),
                        "status": status,
                        "source_path": source,
                    },
                )

            for rank, item in enumerate(data.get("top") or [], start=1):
                bitstring = bitstring_from_item(item)
                add_candidate(
                    candidates,
                    {
                        "session": session.name,
                        "challenge": label,
                        "difficulty": meta.get("difficulty") or data.get("difficulty"),
                        "qubits": meta.get("qubits") or data.get("num_qubits"),
                        "method": method,
                        "run_id": base_run,
                        "rank_type": "sparse_beam" if method == "sparse_beam" else "sample_top",
                        "rank": item.get("rank", rank) if isinstance(item, dict) else rank,
                        "bitstring_qiskit": bitstring,
                        "score_type": "weight" if isinstance(item, dict) and "weight" in item else "",
                        "score": item.get("weight") if isinstance(item, dict) else "",
                        "selected": candidate_status(bitstring, selected.get(label, "")),
                        "status": status,
                        "source_path": source,
                    },
                )

            for key, rank_type in (
                ("final_candidate_qiskit_order", "final_candidate"),
                ("candidate_qiskit_order", "marginal_candidate"),
                ("pred_bitstring_qiskit_order", "marginal_candidate"),
            ):
                bitstring = as_text(data.get(key))
                if not bitstring:
                    continue
                add_candidate(
                    candidates,
                    {
                        "session": session.name,
                        "challenge": label,
                        "difficulty": meta.get("difficulty") or data.get("difficulty"),
                        "qubits": meta.get("qubits") or data.get("num_qubits"),
                        "method": method,
                        "run_id": base_run,
                        "rank_type": rank_type,
                        "rank": 1,
                        "bitstring_qiskit": bitstring,
                        "score_type": "margin" if data.get("p1_margin_min") is not None else "",
                        "score": data.get("p1_margin_min"),
                        "selected": candidate_status(bitstring, selected.get(label, "")),
                        "validation": data.get("validation", ""),
                        "status": status,
                        "source_path": source,
                    },
                )


def parse_peaked_outputs(
    session: SessionConfig,
    repo_root: Path,
    challenges: dict[str, dict[str, str]],
    runs: dict[tuple[str, str, str, str, str], dict[str, str]],
    candidates: dict[tuple[str, str, str, str, str, str, str], dict[str, str]],
) -> None:
    selected = selected_map(challenges)
    for root in session.raw_roots:
        for json_dir in (
            root / "outputs/peaked_circuit_sim_all/json",
            root / "outputs/peaked_circuit_sim_pilot/json",
        ):
            if not json_dir.exists():
                continue
            for path in sorted(json_dir.glob("*.json")):
                data = read_json(path)
                label = source_challenge(path, data)
                if label not in challenges:
                    continue
                meta = challenges[label]
                params = data.get("parameters") or {}
                source = relpath(path, repo_root)
                commit = source_commit(root, path)
                status = as_text(data.get("status") or "ok")
                method = "peaked_mpo_mps"
                run_id = path.stem
                add_run(
                    runs,
                    {
                        "session": session.name,
                        "challenge": label,
                        "difficulty": meta.get("difficulty") or data.get("difficulty"),
                        "qubits": meta.get("qubits") or data.get("num_qubits"),
                        "method": method,
                        "method_family": "mpo",
                        "run_id": run_id,
                        "status": status,
                        "source_path": source,
                        "worktree": root.name,
                        "commit": commit,
                        "backend": backend_from_data(data),
                        "shots": "",
                        "max_bond": params.get("max_bond"),
                        "seed": params.get("seed"),
                        "seconds": data.get("total_seconds"),
                        "notes": "peaked circuit MPO/MPS marginal candidate",
                    },
                )
                bitstring = as_text(data.get("pred_bitstring_qiskit_order"))
                if bitstring:
                    add_candidate(
                        candidates,
                        {
                            "session": session.name,
                            "challenge": label,
                            "difficulty": meta.get("difficulty") or data.get("difficulty"),
                            "qubits": meta.get("qubits") or data.get("num_qubits"),
                            "method": method,
                            "run_id": run_id,
                            "rank_type": "marginal_candidate",
                            "rank": 1,
                            "bitstring_qiskit": bitstring,
                            "score_type": "margin",
                            "score": data.get("p1_margin_min"),
                            "selected": candidate_status(bitstring, selected.get(label, "")),
                            "status": status,
                            "source_path": source,
                        },
                    )


def load_annotations(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return [{field: row.get(field, "") for field in ANNOTATION_FIELDS} for row in csv.DictReader(fh, delimiter="\t")]


def ensure_default_annotations(
    rows: list[dict[str, str]],
    candidates: dict[tuple[str, str, str, str, str, str, str], dict[str, str]],
) -> list[dict[str, str]]:
    existing = {(row["challenge"], row["bitstring_qiskit"], row["status"]) for row in rows}

    aggregate = [
        row
        for row in candidates.values()
        if row["challenge"] == "64_41"
        and row["method"] == "aer_mps_pilot"
        and row["rank_type"] == "aggregate_rank"
    ]
    aggregate.sort(key=lambda row: as_int(row["rank"]) or 9999)
    defaults: list[dict[str, str]] = []
    if len(aggregate) >= 1:
        defaults.append(
            {
                "challenge": "64_41",
                "bitstring_qiskit": aggregate[0]["bitstring_qiskit"],
                "status": "rejected",
                "note": "User reported the first 64_41 bitstring is wrong.",
                "date": "2026-06-06",
                "source": "user",
            }
        )
    if len(aggregate) >= 2:
        defaults.append(
            {
                "challenge": "64_41",
                "bitstring_qiskit": aggregate[1]["bitstring_qiskit"],
                "status": "try_next",
                "note": "User asked to try the second aggregate-rank candidate next.",
                "date": "2026-06-06",
                "source": "user",
            }
        )

    for row in defaults:
        key = (row["challenge"], row["bitstring_qiskit"], row["status"])
        if key not in existing:
            rows.append(row)
            existing.add(key)
    return rows


def write_tsv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            normalized = {field: as_text(row.get(field, "")) for field in fields}
            if fields and normalized[fields[-1]] == "":
                normalized[fields[-1]] = "-"
            writer.writerow(normalized)


def method_sort_key(row: dict[str, str]) -> tuple[str, str, int, str]:
    return (
        row.get("method", ""),
        row.get("rank_type", ""),
        as_int(row.get("rank")) or 999999,
        row.get("bitstring_qiskit", ""),
    )


def write_markdown_pages(
    output_dir: Path,
    challenges: dict[str, dict[str, str]],
    candidates: list[dict[str, str]],
    annotations: list[dict[str, str]],
) -> None:
    by_challenge_dir = output_dir / "by_challenge"
    by_method_dir = output_dir / "by_method"
    by_challenge_dir.mkdir(parents=True, exist_ok=True)
    by_method_dir.mkdir(parents=True, exist_ok=True)

    annotation_by_key = defaultdict(list)
    for row in annotations:
        annotation_by_key[(row["challenge"], row["bitstring_qiskit"])].append(row)

    grouped = defaultdict(list)
    for row in candidates:
        grouped[row["challenge"]].append(row)

    for label, meta in sorted(challenges.items(), key=lambda item: challenge_sort_key(item[0], item[1].get("difficulty", ""))):
        rows = sorted(grouped.get(label, []), key=method_sort_key)
        lines = [
            f"# Challenge {label}",
            "",
            f"- Difficulty: {meta.get('difficulty', '')}",
            f"- Qubits: {meta.get('qubits', '')}",
            f"- QASM: `{meta.get('qasm', '')}`",
            f"- Selected: `{meta.get('selected_bitstring', '')}`",
            f"- Selected method: `{meta.get('selected_method', '')}`",
            f"- Validation: `{meta.get('validation', '')}`",
            f"- Candidate rows: {len(rows)}",
            "",
        ]

        challenge_annotations = [row for row in annotations if row["challenge"] == label]
        if challenge_annotations:
            lines.extend(
                [
                    "## Review Notes",
                    "",
                    "| status | bitstring | note | date | source |",
                    "|---|---|---|---|---|",
                ]
            )
            for ann in challenge_annotations:
                lines.append(
                    f"| {ann['status']} | `{ann['bitstring_qiskit']}` | {ann['note']} | {ann['date']} | {ann['source']} |"
                )
            lines.append("")

        lines.extend(
            [
                "## Candidates",
                "",
                "| review | selected | method | rank_type | rank | bitstring | score | count | support | fraction | validation | status | source |",
                "|---|---:|---|---|---:|---|---:|---:|---:|---:|---|---|---|",
            ]
        )
        for row in rows:
            review = ",".join(ann["status"] for ann in annotation_by_key.get((label, row["bitstring_qiskit"]), []))
            lines.append(
                "| "
                + " | ".join(
                    [
                        review,
                        row["selected"],
                        row["method"],
                        row["rank_type"],
                        row["rank"],
                        f"`{row['bitstring_qiskit']}`",
                        row["score"],
                        row["count"],
                        row["support"],
                        row["fraction"],
                        row["validation"],
                        row["status"],
                        f"`{row['source_path']}`",
                    ]
                )
                + " |"
            )
        (by_challenge_dir / f"{label}.md").write_text("\n".join(lines) + "\n")

    by_method = defaultdict(list)
    for row in candidates:
        by_method[row["method"]].append(row)
    for method, rows in sorted(by_method.items()):
        safe_method = re.sub(r"[^A-Za-z0-9_.-]+", "_", method)
        write_tsv(by_method_dir / f"{safe_method}.tsv", CANDIDATE_FIELDS, sorted(rows, key=lambda row: (challenge_sort_key(row["challenge"], row["difficulty"]), method_sort_key(row))))


def write_readme(output_dir: Path, session: SessionConfig, summary: dict[str, Any]) -> None:
    lines = [
        f"# Results Index: {session.name}",
        "",
        "Generated by `research/_shared/scripts/build_results_index.py`.",
        "",
        "Use this folder as the quick lookup layer for candidate answers. The raw Slurm and method artifacts remain in their original locations.",
        "",
        "## Entry Points",
        "",
        "- `selected_answers.tsv`: one selected or blank answer row per challenge.",
        "- `candidates.tsv`: every normalized candidate/rank row captured by the generator.",
        "- `method_runs.tsv`: method attempts, including started/error rows when present.",
        "- `annotations.tsv`: manual review statuses such as rejected and try_next.",
        "- `by_challenge/64_41.md`: quick page for checking alternate 64_41 candidates.",
        "- `by_method/*.tsv`: candidate rows split by normalized method.",
        "",
        "## Summary",
        "",
        f"- Challenges: {summary['challenge_count']}",
        f"- Selected answers: {summary['selected_count']}",
        f"- Method runs: {summary['method_run_count']}",
        f"- Candidate rows: {summary['candidate_count']}",
        "",
        "For schema details, see `research/_shared/schemas/results_index_schema.md`.",
    ]
    (output_dir / "README.md").write_text("\n".join(lines) + "\n")


def build_session(session: SessionConfig, repo_root: Path) -> dict[str, Any]:
    output_dir = session.session_dir / "results_index"
    existing_annotations = load_annotations(output_dir / "annotations.tsv")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    challenges, evidence_records = load_collector(session, repo_root)
    runs: dict[tuple[str, str, str, str, str], dict[str, str]] = {}
    candidates: dict[tuple[str, str, str, str, str, str, str], dict[str, str]] = {}

    add_collector_rows(session, repo_root, challenges, evidence_records, runs, candidates)
    parse_exact_jsonl(session, repo_root, challenges, runs, candidates)
    parse_mps_distill_summary(session, repo_root, challenges, runs, candidates)
    parse_selected_sim_outputs(session, repo_root, challenges, runs, candidates)
    parse_tree_tensor_outputs(session, repo_root, challenges, runs, candidates)
    parse_peaked_outputs(session, repo_root, challenges, runs, candidates)

    annotations = ensure_default_annotations(existing_annotations, candidates)

    challenge_rows = [
        {field: row.get(field, "") for field in CHALLENGE_FIELDS}
        for _, row in sorted(challenges.items(), key=lambda item: challenge_sort_key(item[0], item[1].get("difficulty", "")))
    ]
    selected_rows = []
    for row in challenge_rows:
        selected_rows.append(
            {
                **row,
                "status": "selected" if row.get("selected_bitstring") else "blank",
            }
        )

    candidate_rows = sorted(
        candidates.values(),
        key=lambda row: (challenge_sort_key(row["challenge"], row["difficulty"]), method_sort_key(row), row["run_id"], row["source_path"]),
    )
    run_rows = sorted(
        runs.values(),
        key=lambda row: (challenge_sort_key(row["challenge"], row["difficulty"]), row["method"], row["run_id"], row["source_path"]),
    )

    write_tsv(output_dir / "challenges.tsv", CHALLENGE_FIELDS, challenge_rows)
    write_tsv(output_dir / "selected_answers.tsv", SELECTED_FIELDS, selected_rows)
    write_tsv(output_dir / "method_runs.tsv", RUN_FIELDS, run_rows)
    write_tsv(output_dir / "candidates.tsv", CANDIDATE_FIELDS, candidate_rows)
    write_tsv(output_dir / "annotations.tsv", ANNOTATION_FIELDS, annotations)
    write_markdown_pages(output_dir, challenges, candidate_rows, annotations)

    by_method_counts = Counter(row["method"] for row in candidate_rows)
    by_challenge_counts = Counter(row["challenge"] for row in candidate_rows)
    summary = {
        "session": session.name,
        "challenge_count": len(challenges),
        "selected_count": sum(1 for row in challenge_rows if row.get("selected_bitstring")),
        "blank_count": sum(1 for row in challenge_rows if not row.get("selected_bitstring")),
        "method_run_count": len(run_rows),
        "candidate_count": len(candidate_rows),
        "methods": dict(sorted(by_method_counts.items())),
        "candidate_rows_by_challenge": dict(sorted(by_challenge_counts.items(), key=lambda item: challenge_sort_key(item[0], challenges.get(item[0], {}).get("difficulty", "")))),
        "raw_roots": [relpath(root, repo_root) if root != repo_root else "." for root in session.raw_roots],
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    write_readme(output_dir, session, summary)
    return summary


def default_sessions(repo_root: Path) -> list[SessionConfig]:
    sibling = repo_root.parent / "quantum-junction-tree-tensor"
    main_roots = (repo_root,)
    tree_roots = (sibling, repo_root) if sibling.exists() else (repo_root,)
    return [
        SessionConfig(
            name="tree_tensor_sim_session",
            session_dir=repo_root / "research/tree_tensor_sim_session",
            collector_tsv=repo_root / "research/tree_tensor_sim_session/artifacts/collector/CANDIDATES.tsv",
            collector_evidence_json=repo_root / "research/tree_tensor_sim_session/artifacts/collector/CANDIDATE_EVIDENCE.json",
            raw_roots=tree_roots,
        ),
        SessionConfig(
            name="quantum_peak_session",
            session_dir=repo_root / "research/quantum_peak_session",
            collector_tsv=repo_root / "research/quantum_peak_session/results/current_candidates/CANDIDATES.tsv",
            collector_evidence_json=repo_root / "research/quantum_peak_session/results/current_candidates/CANDIDATE_EVIDENCE.json",
            raw_roots=main_roots,
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
    summaries = {}
    for session in default_sessions(repo_root):
        if requested and session.name not in requested:
            continue
        summaries[session.name] = build_session(session, repo_root)
    print(json.dumps(summaries, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
