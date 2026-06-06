#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHALLENGE_RE = re.compile(r"challenge-(\d+)_(\d+)\.qasm$")


def challenge_rows(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((root / "challenges").glob("*/*.qasm"), key=lambda p: (p.parent.name, p.name)):
        match = CHALLENGE_RE.match(path.name)
        if not match:
            continue
        rows.append(
            {
                "label": f"{match.group(1)}_{match.group(2)}",
                "challenge_id": int(match.group(2)),
                "num_qubits": int(match.group(1)),
                "difficulty": path.parent.name,
                "qasm": str(path.relative_to(root)),
            }
        )
    return rows


def add_evidence(evidence: dict[str, list[dict[str, Any]]], label: str | None, row: dict[str, Any]) -> None:
    if not label or not row.get("candidate"):
        return
    evidence.setdefault(label, []).append(row)


def has_finite_marginals(data: dict[str, Any]) -> bool:
    p0s = ((data.get("marginal") or {}).get("p0s_raw_site_order") or [])
    if not p0s:
        return False
    try:
        return all(math.isfinite(float(p0)) for p0 in p0s)
    except Exception:
        return False


def has_usable_graph_tns_candidate(data: dict[str, Any]) -> bool:
    if not data.get("final_candidate_qiskit_order"):
        return False
    strategy = data.get("candidate_strategy") or ""
    if strategy.startswith("marginal_") and not has_finite_marginals(data):
        return False
    return True


def source_priority(source: str) -> int:
    priorities = {
        "exact_statevector": 98,
        "quimb_gpu_all": 90,
        "quimb_opt_u3_gpu": 88,
        "quimb_cpu_all": 80,
        "peaked_mpo_unswap_gpu": 70,
        "quimb_rcm_cpu": 55,
        "quimb_mst_cpu": 54,
        "quimb_degree_cpu": 53,
        "quimb_mid_cpu": 52,
        "quimb_fast_cpu": 50,
        "quimb_identity_cpu": 49,
        "quimb_vh_multiseed_cpu": 48,
        "sparse_beam": 45,
        "aer_mps_pilot": 40,
        "peaked_mpo_graph_tns_gpu_retry": 36,
        "peaked_mpo_graph_tns": 35,
        "peaked_mpo_graph_tns_cpu": 34,
        "peaked_mpo_graph_tns_extra_cpu": 33,
        "peaked_mpo_graph_tns_veryhard_fast_cpu": 32,
        "peaked_mpo_graph_tns_veryhard_fast_cpu_b": 31,
        "peaked_mpo_graph_tns_veryhard_fast_cpu_c": 30,
        "peaked_mpo_graph_tns_veryhard_fast_cpu_d": 29,
        "peaked_mpo_graph_tns_veryhard_fast_cpu_e": 28,
        "peaked_mpo_graph_tns_ultrafast_cpu": 27,
        "peaked_mpo_graph_tns_ultrafast_cpu_s2": 26,
        "peaked_mpo_graph_tns_veryhard_fast_cpu_f": 25,
        "peaked_mpo_graph_tns_veryhard_fast_cpu_g": 24,
        "peaked_mpo_graph_tns_marginal_fallback_cpu": 23,
    }
    return priorities.get(source, 10)


def load_archived_candidate_rollup(root: Path, rel_path: str, evidence: dict[str, list[dict[str, Any]]]) -> None:
    path = root / rel_path
    if not path.exists():
        return
    with path.open(newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            source = row.get("source") or "archived_rollup"
            add_evidence(
                evidence,
                row.get("challenge"),
                {
                    "source": source,
                    "priority": source_priority(source),
                    "candidate": row.get("candidate"),
                    "validation": row.get("validation") or "unknown",
                    "top_fraction": row.get("top_fraction") or "",
                    "max_bond": row.get("max_bond") or "",
                    "seconds": row.get("seconds") or "",
                    "path": str(path.relative_to(root)),
                    "archived_evidence_count": row.get("evidence_count") or "",
                },
            )


def load_exact(root: Path, evidence: dict[str, list[dict[str, Any]]]) -> None:
    path = root / "agent_work" / "exact_baseline" / "peaks_exact.csv"
    if not path.exists():
        return
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            qasm = Path(row.get("path", "")).name
            match = CHALLENGE_RE.match(qasm)
            if not match:
                continue
            label = f"{match.group(1)}_{match.group(2)}"
            add_evidence(
                evidence,
                label,
                {
                    "source": "exact_statevector",
                    "priority": 100,
                    "candidate": row.get("peak_bitstring") or row.get("peak"),
                    "validation": "exact",
                    "top_fraction": row.get("peak_probability") or "",
                    "max_bond": "",
                    "seconds": "",
                    "path": str(path.relative_to(root)),
                },
            )


def load_quimb_dir(root: Path, rel_dir: str, source: str, priority: int, evidence: dict[str, list[dict[str, Any]]]) -> None:
    json_dir = root / rel_dir / "json"
    if not json_dir.exists():
        return
    for path in sorted(json_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception as exc:  # noqa: BLE001
            add_evidence(
                evidence,
                path.stem,
                {
                    "source": source,
                    "priority": 0,
                    "candidate": "",
                    "validation": "read_error",
                    "error": repr(exc),
                    "path": str(path.relative_to(root)),
                },
            )
            continue
        if data.get("status") != "ok":
            continue
        if data.get("method") != "quimb_graph_tree_ordered_circuit_mps":
            continue
        label = data.get("challenge_label")
        sampling = data.get("sampling", {})
        validation = data.get("validation", {})
        mps_info = data.get("mps_info", {})
        add_evidence(
            evidence,
            label,
            {
                "source": source,
                "priority": priority,
                "candidate": data.get("final_candidate_qiskit_order"),
                "validation": validation.get("status") or "unknown",
                "top_fraction": sampling.get("top_fraction", ""),
                "max_bond": mps_info.get("max_bond", ""),
                "seconds": data.get("total_seconds", ""),
                "path": str(path.relative_to(root)),
            },
        )


def load_quimb_multiseed_dir(root: Path, rel_dir: str, source: str, priority: int, evidence: dict[str, list[dict[str, Any]]]) -> None:
    base_dir = root / rel_dir
    if not base_dir.exists():
        return
    for path in sorted(base_dir.glob("seed_*/json/*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        if data.get("status") != "ok":
            continue
        if data.get("method") != "quimb_graph_tree_ordered_circuit_mps":
            continue
        label = data.get("challenge_label")
        sampling = data.get("sampling", {})
        validation = data.get("validation", {})
        mps_info = data.get("mps_info", {})
        add_evidence(
            evidence,
            label,
            {
                "source": source,
                "priority": priority,
                "candidate": data.get("final_candidate_qiskit_order"),
                "validation": validation.get("status") or "unknown",
                "top_fraction": sampling.get("top_fraction", ""),
                "max_bond": mps_info.get("max_bond", ""),
                "seconds": data.get("total_seconds", ""),
                "path": str(path.relative_to(root)),
                "seed": (data.get("parameters") or {}).get("seed", ""),
            },
        )


def load_peaked_unswap_dir(root: Path, rel_dir: str, source: str, priority: int, evidence: dict[str, list[dict[str, Any]]]) -> None:
    json_dir = root / rel_dir / "json"
    if not json_dir.exists():
        return
    for path in sorted(json_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception as exc:  # noqa: BLE001
            add_evidence(
                evidence,
                path.stem,
                {
                    "source": source,
                    "priority": 0,
                    "candidate": "",
                    "validation": "read_error",
                    "error": repr(exc),
                    "path": str(path.relative_to(root)),
                },
            )
            continue
        if data.get("status") != "ok":
            continue
        if data.get("method") != "peaked_mpo_unswap":
            continue
        label = data.get("challenge_label")
        sampling = data.get("sampling", {})
        validation = data.get("validation", {})
        mps_info = data.get("mps_info", {})
        add_evidence(
            evidence,
            label,
            {
                "source": source,
                "priority": priority,
                "candidate": data.get("final_candidate_qiskit_order"),
                "validation": validation.get("status") or "unknown",
                "top_fraction": sampling.get("top_fraction", ""),
                "max_bond": mps_info.get("max_bond", ""),
                "seconds": data.get("total_seconds", ""),
                "path": str(path.relative_to(root)),
            },
        )


def load_peaked_graph_tns_dir(root: Path, rel_dir: str, source: str, priority: int, evidence: dict[str, list[dict[str, Any]]]) -> None:
    json_dir = root / rel_dir / "json"
    if not json_dir.exists():
        return
    for path in sorted(json_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception as exc:  # noqa: BLE001
            add_evidence(
                evidence,
                path.stem,
                {
                    "source": source,
                    "priority": 0,
                    "candidate": "",
                    "validation": "read_error",
                    "error": repr(exc),
                    "path": str(path.relative_to(root)),
                },
            )
            continue
        if data.get("status") != "ok":
            continue
        if data.get("method") != "peaked_mpo_graph_tns":
            continue
        if not has_usable_graph_tns_candidate(data):
            continue
        label = data.get("challenge_label")
        sampling = data.get("sampling", {})
        validation = data.get("validation", {})
        mps_info = data.get("mps_info", {})
        add_evidence(
            evidence,
            label,
            {
                "source": source,
                "priority": priority,
                "candidate": data.get("final_candidate_qiskit_order"),
                "validation": validation.get("status") or "unknown",
                "top_fraction": sampling.get("top_fraction", ""),
                "max_bond": mps_info.get("max_bond", ""),
                "seconds": data.get("total_seconds", ""),
                "path": str(path.relative_to(root)),
                "candidate_strategy": data.get("candidate_strategy", ""),
            },
        )


def load_mps_pilot(root: Path, evidence: dict[str, list[dict[str, Any]]]) -> None:
    path = root / "agent_work" / "mps_distill" / "summaries" / "pilot_candidates.tsv"
    if not path.exists():
        return
    with path.open(newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            qasm = Path(row.get("circuit", "")).name
            match = CHALLENGE_RE.match(qasm)
            if not match:
                continue
            label = f"{match.group(1)}_{match.group(2)}"
            add_evidence(
                evidence,
                label,
                {
                    "source": "aer_mps_pilot",
                    "priority": 40,
                    "candidate": row.get("candidate"),
                    "validation": row.get("classification") or "unknown",
                    "top_fraction": row.get("top1_vote_fraction") or "",
                    "max_bond": "",
                    "seconds": "",
                    "path": str(path.relative_to(root)),
                },
            )


def load_sparse_beam(root: Path, evidence: dict[str, list[dict[str, Any]]]) -> None:
    json_dir = root / "outputs" / "tree_tensor_sim" / "sparse_beam" / "json"
    if not json_dir.exists():
        return
    for path in sorted(json_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        qasm = Path(data.get("qasm") or path.name).name
        match = CHALLENGE_RE.match(qasm)
        if not match:
            continue
        top = data.get("top") or []
        if not top:
            continue
        best = top[0]
        label = f"{match.group(1)}_{match.group(2)}"
        kept_norm = float(data.get("kept_norm") or 0.0)
        weight = float(best.get("weight") or 0.0)
        add_evidence(
            evidence,
            label,
            {
                "source": "sparse_beam",
                "priority": 45,
                "candidate": best.get("bitstring"),
                "validation": "unknown",
                "top_fraction": (weight / kept_norm) if kept_norm else weight,
                "max_bond": data.get("beam", ""),
                "seconds": data.get("seconds", ""),
                "path": str(path.relative_to(root)),
            },
        )


def choose(evidence_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not evidence_rows:
        return None
    selectable = [row for row in evidence_rows if row.get("validation") != "incorrect"]
    if not selectable:
        return None
    return max(
        selectable,
        key=lambda row: (
            int(row.get("priority") or 0),
            str(row.get("validation") == "correct"),
            float(row.get("top_fraction") or 0.0) if str(row.get("top_fraction") or "").replace(".", "", 1).isdigit() else 0.0,
            str(row.get("candidate") or ""),
        ),
    )


def fmt(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def submission_explanation(selected: dict[str, Any]) -> str:
    source = selected.get("source") or "candidate rollup"
    return (
        f"This answer was selected from the {source} evidence in the candidate rollup. "
        "The method uses exact statevector results where available and otherwise a graph-ordered Quimb CircuitMPS tensor-network sampling adaptation, with candidates cross-checked against known answers and alternate orderings when evidence exists."
    )


def write_outputs(root: Path, out_dir: Path, challenges: list[dict[str, Any]], evidence: dict[str, list[dict[str, Any]]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for challenge in challenges:
        label = challenge["label"]
        ev_rows = sorted(evidence.get(label, []), key=lambda row: (-int(row.get("priority") or 0), row.get("source", "")))
        selected = choose(ev_rows)
        rows.append({**challenge, "selected": selected, "evidence": ev_rows})

    tsv_path = out_dir / "CANDIDATES.tsv"
    with tsv_path.open("w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(
            [
                "challenge",
                "difficulty",
                "qubits",
                "candidate",
                "source",
                "validation",
                "top_fraction",
                "max_bond",
                "seconds",
                "evidence_count",
                "qasm",
            ]
        )
        for row in rows:
            selected = row["selected"] or {}
            writer.writerow(
                [
                    row["label"],
                    row["difficulty"],
                    row["num_qubits"],
                    fmt(selected.get("candidate")),
                    fmt(selected.get("source")),
                    fmt(selected.get("validation")),
                    fmt(selected.get("top_fraction")),
                    fmt(selected.get("max_bond")),
                    fmt(selected.get("seconds")),
                    len(row["evidence"]),
                    row["qasm"],
                ]
            )

    submission_tsv_path = out_dir / "SUBMISSION_ANSWERS.tsv"
    with submission_tsv_path.open("w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["challenge", "candidate", "explanation"])
        for row in rows:
            selected = row["selected"] or {}
            candidate = selected.get("candidate")
            if not candidate:
                continue
            writer.writerow([row["label"], candidate, submission_explanation(selected)])

    evidence_path = out_dir / "CANDIDATE_EVIDENCE.json"
    evidence_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")

    solved = [r for r in rows if r["selected"] and r["selected"].get("candidate")]
    lines = [
        "# Peak Candidate Rollup",
        "",
        f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
        f"Selected candidates: {len(solved)}/{len(rows)}.",
        "",
        "| challenge | difficulty | q | candidate | source | validation | top fraction | max bond | evidence |",
        "| --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        selected = row["selected"] or {}
        candidate = selected.get("candidate")
        lines.append(
            "| "
            + " | ".join(
                [
                    row["label"],
                    row["difficulty"],
                    str(row["num_qubits"]),
                    f"`{candidate}`" if candidate else "",
                    fmt(selected.get("source")),
                    fmt(selected.get("validation")),
                    fmt(selected.get("top_fraction")),
                    fmt(selected.get("max_bond")),
                    str(len(row["evidence"])),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Artifacts:",
            f"- `{tsv_path.relative_to(root)}`",
            f"- `{evidence_path.relative_to(root)}`",
            f"- `{submission_tsv_path.relative_to(root)}`",
            "",
            "Bit order: candidates are in Qiskit/counts order, with the right-most bit corresponding to qubit 0.",
        ]
    )
    (out_dir / "CANDIDATES.md").write_text("\n".join(lines) + "\n")

    submission_lines = [
        "# Submission Answers",
        "",
        f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
        f"Selected candidates: {len(solved)}/{len(rows)}.",
        "",
        "| challenge | candidate | explanation |",
        "| --- | --- | --- |",
    ]
    for row in rows:
        selected = row["selected"] or {}
        candidate = selected.get("candidate")
        if not candidate:
            continue
        submission_lines.append(
            "| "
            + " | ".join(
                [
                    row["label"],
                    f"`{candidate}`",
                    submission_explanation(selected),
                ]
            )
            + " |"
        )
    submission_lines.extend(
        [
            "",
            "Bit order: candidates are in Qiskit/counts order, with the right-most bit corresponding to qubit 0.",
        ]
    )
    (out_dir / "SUBMISSION_ANSWERS.md").write_text("\n".join(submission_lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs" / "tree_tensor_sim")
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir

    evidence: dict[str, list[dict[str, Any]]] = {}
    load_exact(root, evidence)
    load_archived_candidate_rollup(root, "research/quantum_peak_session/results/current_candidates/CANDIDATES.tsv", evidence)
    load_archived_candidate_rollup(root, "research/tree_tensor_sim_session/artifacts/collector/CANDIDATES.tsv", evidence)
    load_quimb_dir(root, "outputs/tree_tensor_sim/all", "quimb_gpu_all", 90, evidence)
    load_quimb_dir(root, "outputs/tree_tensor_sim/opt_u3_gpu", "quimb_opt_u3_gpu", 88, evidence)
    load_quimb_dir(root, "outputs/tree_tensor_sim/all_cpu", "quimb_cpu_all", 80, evidence)
    load_peaked_unswap_dir(root, "outputs/tree_tensor_sim/peaked_unswap_gpu", "peaked_mpo_unswap_gpu", 70, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_gpu_retry", "peaked_mpo_graph_tns_gpu_retry", 36, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_all", "peaked_mpo_graph_tns", 35, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_all_cpu", "peaked_mpo_graph_tns_cpu", 34, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_missing_cpu", "peaked_mpo_graph_tns_cpu", 34, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_extra_cpu", "peaked_mpo_graph_tns_extra_cpu", 33, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_extra_cpu_b", "peaked_mpo_graph_tns_extra_cpu", 33, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_extra_cpu_c", "peaked_mpo_graph_tns_extra_cpu", 33, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_extra_cpu_d", "peaked_mpo_graph_tns_extra_cpu", 33, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_extra_cpu_e", "peaked_mpo_graph_tns_extra_cpu", 33, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_extra_cpu_f", "peaked_mpo_graph_tns_extra_cpu", 33, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_extra_cpu_g", "peaked_mpo_graph_tns_extra_cpu", 33, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_veryhard_fast_cpu", "peaked_mpo_graph_tns_veryhard_fast_cpu", 32, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_veryhard_fast_cpu_b", "peaked_mpo_graph_tns_veryhard_fast_cpu_b", 31, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_veryhard_fast_cpu_c", "peaked_mpo_graph_tns_veryhard_fast_cpu_c", 30, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_veryhard_fast_cpu_d", "peaked_mpo_graph_tns_veryhard_fast_cpu_d", 29, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_veryhard_fast_cpu_e", "peaked_mpo_graph_tns_veryhard_fast_cpu_e", 28, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_veryhard_ultrafast_cpu", "peaked_mpo_graph_tns_ultrafast_cpu", 27, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_veryhard_ultrafast_cpu_s2", "peaked_mpo_graph_tns_ultrafast_cpu_s2", 26, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_veryhard_fast_cpu_f", "peaked_mpo_graph_tns_veryhard_fast_cpu_f", 25, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_veryhard_fast_cpu_g", "peaked_mpo_graph_tns_veryhard_fast_cpu_g", 24, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_marginal_fallback_cpu", "peaked_mpo_graph_tns_marginal_fallback_cpu", 23, evidence)
    load_peaked_graph_tns_dir(root, "outputs/mpo_graph_tns_param_probe", "peaked_mpo_graph_tns_veryhard_fast_cpu", 32, evidence)
    load_quimb_dir(root, "outputs/tree_tensor_sim/rcm_cpu", "quimb_rcm_cpu", 55, evidence)
    load_quimb_dir(root, "outputs/tree_tensor_sim/mst_cpu", "quimb_mst_cpu", 54, evidence)
    load_quimb_dir(root, "outputs/tree_tensor_sim/degree_cpu", "quimb_degree_cpu", 53, evidence)
    load_quimb_dir(root, "outputs/tree_tensor_sim/mid_cpu", "quimb_mid_cpu", 52, evidence)
    load_quimb_dir(root, "outputs/tree_tensor_sim/fast_cpu", "quimb_fast_cpu", 50, evidence)
    load_quimb_dir(root, "outputs/tree_tensor_sim/identity_cpu", "quimb_identity_cpu", 49, evidence)
    load_quimb_multiseed_dir(root, "outputs/multiseed_vh_cpu", "quimb_vh_multiseed_cpu", 48, evidence)
    load_sparse_beam(root, evidence)
    load_mps_pilot(root, evidence)

    write_outputs(root, out_dir, challenge_rows(root), evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
