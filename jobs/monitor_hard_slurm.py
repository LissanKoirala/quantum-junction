#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from collect_peak_candidates import has_usable_graph_tns_candidate, source_priority


ROOT = Path(__file__).resolve().parents[1]
VERY_HARD = ["48_42", "56_43", "64_44", "72_45", "80_46", "88_47", "96_48", "104_49"]
DEFAULT_CPU_CAP = 2000
DEFAULT_GPU_CAP = 5
VERY_HARD_BY_ARRAY_INDEX = {
    idx: label for idx, label in enumerate(VERY_HARD)
}
GRAPH_DIRS = [
    "mpo_graph_tns_gpu_retry",
    "mpo_graph_tns_all",
    "mpo_graph_tns_all_cpu",
    "mpo_graph_tns_missing_cpu",
    "mpo_graph_tns_extra_cpu",
    "mpo_graph_tns_extra_cpu_b",
    "mpo_graph_tns_extra_cpu_c",
    "mpo_graph_tns_extra_cpu_d",
    "mpo_graph_tns_extra_cpu_e",
    "mpo_graph_tns_extra_cpu_f",
    "mpo_graph_tns_extra_cpu_g",
    "mpo_graph_tns_veryhard_fast_cpu",
    "mpo_graph_tns_veryhard_fast_cpu_b",
    "mpo_graph_tns_veryhard_fast_cpu_c",
    "mpo_graph_tns_veryhard_fast_cpu_d",
    "mpo_graph_tns_veryhard_fast_cpu_e",
    "mpo_veryhard_ultrafast_cpu",
    "mpo_veryhard_ultrafast_cpu_s2",
    "mpo_graph_tns_veryhard_fast_cpu_f",
    "mpo_graph_tns_veryhard_fast_cpu_g",
    "mpo_graph_tns_veryhard_fast_cpu_h",
    "mpo_graph_tns_veryhard_fast_cpu_i",
    "mpo_graph_tns_marginal_fallback_cpu",
    "mpo_graph_tns_param_probe",
]
MULTISEED_DIRS = ["multiseed_vh_cpu"]


def run_text(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return ""


def challenge_index(root: Path) -> dict[int, str]:
    out = {}
    paths = sorted((root / "challenges").glob("*/*.qasm"), key=lambda p: (p.parent.name, p.name))
    for idx, path in enumerate(paths):
        out[idx] = path.stem.removeprefix("challenge-")
    return out


def array_task_id(job_id: str) -> int | None:
    match = re.search(r"_(\d+)$", job_id)
    return int(match.group(1)) if match else None


def job_challenge_label(root: Path, row: dict[str, Any]) -> str:
    name = row.get("name") or ""
    job_id = row.get("job") or ""
    embedded = re.search(r"(\d+_\d+)", name)
    if embedded:
        return embedded.group(1)
    task_id = array_task_id(job_id)
    if task_id is None:
        return ""
    if name.startswith(("mpo_graph_tns_vhard_fast", "mpo_graph_tns_marginal")):
        return VERY_HARD_BY_ARRAY_INDEX.get(task_id, "")
    if name.startswith(
        (
            "mpo_graph_tns_all",
            "mpo_graph_tns_cpu_all",
            "mpo_graph_tns_gpu_retry",
            "mpo_graph_tns_extra_cpu",
            "mpo_graph_tns_missing_cpu",
            "mpo_graph_tns_mod_retry",
        )
    ):
        return challenge_index(root).get(task_id, "")
    return ""


def sync_named_outputs(root: Path, source_outputs: Path, dirnames: list[str]) -> None:
    if not source_outputs.exists():
        return
    for dirname in dirnames:
        source = source_outputs / dirname
        if not source.exists():
            continue
        subprocess.run(
            ["rsync", "-a", "--update", f"{source}/", str(root / "outputs" / dirname)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def slurm_summary(cpu_cap: int, gpu_cap: int) -> dict[str, Any]:
    user = run_text(["whoami"]).strip()
    out = run_text(["squeue", "-h", "-u", user, "-o", "%i|%T|%C|%b|%j|%M|%R"])
    summary = {
        "cpu_cap": cpu_cap,
        "gpu_cap": gpu_cap,
        "running_cpu": 0,
        "running_gpu": 0,
        "pending_cpu": 0,
        "pending_gpu": 0,
        "tracked_jobs": [],
        "other_jobs": [],
        "jobs_by_name": {},
    }
    for line in out.splitlines():
        if not line.strip():
            continue
        job_id, state, cpus, tres, name, elapsed, reason = line.split("|", 6)
        cpus_i = int(cpus)
        match = re.search(r"gpu:(\d+)", tres or "")
        gpus = int(match.group(1)) if match else 0
        by_name_key = f"{state}:{name}"
        by_name = summary["jobs_by_name"].setdefault(
            by_name_key,
            {"state": state, "name": name, "count": 0, "cpus": 0, "gpus": 0},
        )
        by_name["count"] += 1
        by_name["cpus"] += cpus_i
        by_name["gpus"] += gpus
        if state == "RUNNING":
            summary["running_cpu"] += cpus_i
            summary["running_gpu"] += gpus
        elif state == "PENDING":
            summary["pending_cpu"] += cpus_i
            summary["pending_gpu"] += gpus
        row = {
            "job": job_id,
            "state": state,
            "cpus": cpus_i,
            "gpus": gpus,
            "name": name,
            "elapsed": elapsed,
            "reason": reason,
        }
        if "mpo_graph_tns" in name:
            summary["tracked_jobs"].append(row)
        elif state in {"RUNNING", "PENDING"}:
            summary["other_jobs"].append(row)
    summary["over_cpu"] = max(0, summary["running_cpu"] - cpu_cap)
    summary["over_gpu"] = max(0, summary["running_gpu"] - gpu_cap)
    summary["cpu_headroom"] = cpu_cap - summary["running_cpu"]
    summary["gpu_headroom"] = gpu_cap - summary["running_gpu"]
    return summary


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def graph_records(root: Path) -> dict[str, list[dict[str, Any]]]:
    records = {label: [] for label in VERY_HARD}
    for dirname in GRAPH_DIRS:
        json_dir = root / "outputs" / dirname / "json"
        if not json_dir.exists():
            continue
        for label in VERY_HARD:
            path = json_dir / f"challenge-{label}.peaked_mpo_graph_tns.json"
            if not path.exists():
                continue
            data = load_json(path)
            if data is None:
                records[label].append({"source": dirname, "status": "unreadable", "path": str(path.relative_to(root))})
                continue
            sampling = data.get("sampling") or {}
            validation = data.get("validation") or {}
            status = data.get("status") or ""
            if status == "ok" and not has_usable_graph_tns_candidate(data):
                status = "ok_unusable"
            records[label].append(
                {
                    "source": dirname,
                    "status": status,
                    "candidate": data.get("final_candidate_qiskit_order") or "",
                    "validation": validation.get("status") or "",
                    "top_fraction": sampling.get("top_fraction"),
                    "seconds": data.get("total_seconds"),
                    "path": str(path.relative_to(root)),
                }
            )
    return records


def multiseed_records(root: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {
        label: {"counts": {}, "ok": [], "started": 0, "paths": []} for label in VERY_HARD
    }
    base = root / "outputs" / "multiseed_vh_cpu"
    if not base.exists():
        return records
    for path in sorted(base.glob("seed_*/json/*.json")):
        data = load_json(path)
        if data is None:
            label = path.name.removeprefix("challenge-").split(".", 1)[0]
            status = "unreadable"
            candidate = ""
            top_fraction = None
        else:
            label = data.get("challenge_label") or path.name.removeprefix("challenge-").split(".", 1)[0]
            status = data.get("status") or "unknown"
            candidate = data.get("final_candidate_qiskit_order") or ""
            top_fraction = (data.get("sampling") or {}).get("top_fraction")
        if label not in records:
            records[label] = {"counts": {}, "ok": [], "started": 0, "paths": []}
        entry = records[label]
        entry["counts"][status] = entry["counts"].get(status, 0) + 1
        if status == "started":
            entry["started"] += 1
        if status == "ok" and candidate:
            entry["ok"].append(
                {
                    "candidate": candidate,
                    "top_fraction": top_fraction,
                    "path": str(path.relative_to(root)),
                }
            )
        if len(entry["paths"]) < 8:
            entry["paths"].append(str(path.relative_to(root)))
    return records


def candidate_status(root: Path) -> dict[str, Any]:
    path = root / "outputs" / "tree_tensor_sim" / "CANDIDATES.tsv"
    if not path.exists():
        return {"path": str(path.relative_to(root)), "exists": False}
    solved = []
    solved_labels = []
    selected_by_label = {}
    missing = []
    with path.open(newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            label = row["challenge"]
            if row.get("candidate"):
                solved.append(label)
                solved_labels.append(label)
                source = row.get("source") or ""
                selected_by_label[label] = {
                    "candidate": row.get("candidate") or "",
                    "source": source,
                    "priority": source_priority(source),
                    "validation": row.get("validation") or "",
                    "top_fraction": row.get("top_fraction") or "",
                }
            else:
                missing.append(label)
    return {
        "path": str(path.relative_to(root)),
        "exists": True,
        "solved": len(solved),
        "solved_labels": solved_labels,
        "selected_by_label": selected_by_label,
        "missing": len(missing),
        "missing_labels": missing,
    }


def is_unrelated_cap_candidate(row: dict[str, Any]) -> bool:
    name = row.get("name") or ""
    if "mpo_graph_tns" in name:
        return False
    return bool(row.get("gpus")) or name.startswith(("tno_", "vh_mps", "extra_g"))


def enforcement_actions(root: Path, data: dict[str, Any], cancel_solved: bool, cancel_solved_min_priority: int) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    slurm = data["slurm"]

    gpu_need = int(slurm.get("over_gpu") or 0)
    cpu_need = int(slurm.get("over_cpu") or 0)
    if gpu_need > 0:
        for row in sorted(
            (r for r in slurm["other_jobs"] if r.get("state") == "RUNNING" and is_unrelated_cap_candidate(r)),
            key=lambda r: (int(r.get("gpus") or 0), int(r.get("cpus") or 0)),
            reverse=True,
        ):
            if gpu_need <= 0:
                break
            actions.append(
                {
                    "job": row["job"],
                    "action": "cancel",
                    "reason": "gpu_cap_unrelated_job",
                    "name": row["name"],
                    "cpus": row["cpus"],
                    "gpus": row["gpus"],
                }
            )
            gpu_need -= int(row.get("gpus") or 0)

    if cpu_need > 0:
        for row in sorted(
            (
                r for r in slurm["other_jobs"]
                if r.get("state") == "RUNNING" and is_unrelated_cap_candidate(r) and int(r.get("cpus") or 0) > 0
            ),
            key=lambda r: int(r.get("cpus") or 0),
            reverse=True,
        ):
            if cpu_need <= 0:
                break
            if any(action["job"] == row["job"] for action in actions):
                continue
            actions.append(
                {
                    "job": row["job"],
                    "action": "cancel",
                    "reason": "cpu_cap_unrelated_job",
                    "name": row["name"],
                    "cpus": row["cpus"],
                    "gpus": row["gpus"],
                }
            )
            cpu_need -= int(row.get("cpus") or 0)

    if cancel_solved:
        solved_labels = set(data.get("candidates", {}).get("solved_labels") or [])
        selected_by_label = data.get("candidates", {}).get("selected_by_label") or {}
        for row in slurm["tracked_jobs"]:
            if row.get("state") not in {"RUNNING", "PENDING"}:
                continue
            label = job_challenge_label(root, row)
            if not label or label not in solved_labels:
                continue
            selected = selected_by_label.get(label) or {}
            priority = int(selected.get("priority") or 0)
            if priority < cancel_solved_min_priority:
                continue
            if any(action["job"] == row["job"] for action in actions):
                continue
            actions.append(
                {
                    "job": row["job"],
                    "action": "cancel",
                    "reason": "solved_label_duplicate",
                    "name": row["name"],
                    "label": label,
                    "selected_source": selected.get("source", ""),
                    "selected_priority": priority,
                    "cpus": row["cpus"],
                    "gpus": row["gpus"],
                }
            )
    return actions


def execute_actions(actions: list[dict[str, Any]]) -> None:
    for action in actions:
        if action.get("action") != "cancel":
            continue
        subprocess.run(["scancel", str(action["job"])], check=False)


def print_human(root: Path, data: dict[str, Any]) -> None:
    slurm = data["slurm"]
    candidates = data["candidates"]
    print(f"generated={data['generated']}")
    print(
        "slurm "
        f"running_cpu={slurm['running_cpu']} running_gpu={slurm['running_gpu']} "
        f"pending_cpu={slurm['pending_cpu']} pending_gpu={slurm['pending_gpu']}"
    )
    print(
        "cap "
        f"cpu={slurm['running_cpu']}/{slurm['cpu_cap']} "
        f"gpu={slurm['running_gpu']}/{slurm['gpu_cap']} "
        f"over_cpu={slurm['over_cpu']} over_gpu={slurm['over_gpu']}"
    )
    if candidates.get("exists"):
        print(
            f"candidate_rollup solved={candidates['solved']} "
            f"missing={candidates['missing']} labels={','.join(candidates['missing_labels'])}"
        )
    else:
        print("candidate_rollup missing")
    print("very_hard_outputs:")
    for label, records in data["very_hard"].items():
        usable = [r for r in records if r.get("status") == "ok" and r.get("candidate") and r.get("validation") != "incorrect"]
        if usable:
            best = sorted(usable, key=lambda r: (float(r.get("top_fraction") or 0.0), r["source"]), reverse=True)[0]
            print(f"  {label}: ok source={best['source']} top={best.get('top_fraction')} candidate={best.get('candidate')}")
            continue
        if records:
            compact = ", ".join(f"{r['source']}:{r.get('status') or 'none'}" for r in records)
            print(f"  {label}: no_ok {compact}")
        else:
            print(f"  {label}: no_records")
    multiseed = data.get("multiseed") or {}
    active_multiseed = {label: row for label, row in multiseed.items() if row.get("counts")}
    if active_multiseed:
        print("multiseed_outputs:")
        for label, row in active_multiseed.items():
            counts = ",".join(f"{status}:{count}" for status, count in sorted(row["counts"].items()))
            ok = row.get("ok") or []
            if ok:
                best = sorted(ok, key=lambda r: float(r.get("top_fraction") or 0.0), reverse=True)[0]
                print(f"  {label}: {counts} best_top={best.get('top_fraction')} candidate={best.get('candidate')}")
            else:
                print(f"  {label}: {counts}")
    if slurm["over_cpu"] or slurm["over_gpu"]:
        print("other_active_jobs:")
        for row in slurm["other_jobs"][:80]:
            print(
                f"  {row['job']} {row['state']} cpus={row['cpus']} gpus={row['gpus']} "
                f"{row['name']} {row['elapsed']} {row['reason']}"
            )
    if slurm["tracked_jobs"]:
        print("tracked_slurm_jobs:")
        for row in slurm["tracked_jobs"][:120]:
            print(
                f"  {row['job']} {row['state']} cpus={row['cpus']} gpus={row['gpus']} "
                f"{row['name']} {row['elapsed']} {row['reason']}"
            )
    actions = data.get("enforcement_actions") or []
    if actions:
        print("enforcement_actions:")
        for action in actions:
            label = f" label={action['label']}" if action.get("label") else ""
            selected = (
                f" selected={action['selected_source']}:{action['selected_priority']}"
                if action.get("selected_source")
                else ""
            )
            print(
                f"  {action['action']} {action['job']} reason={action['reason']}"
                f"{label}{selected} cpus={action.get('cpus', 0)} gpus={action.get('gpus', 0)} "
                f"name={action.get('name', '')}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize hard-problem Slurm jobs and candidate coverage.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--cpu-cap", type=int, default=DEFAULT_CPU_CAP)
    parser.add_argument("--gpu-cap", type=int, default=DEFAULT_GPU_CAP)
    parser.add_argument(
        "--enforce-caps",
        action="store_true",
        help="Compute cap-enforcement actions. Use with --execute to run scancel.",
    )
    parser.add_argument(
        "--cancel-solved",
        action="store_true",
        help="Compute cancellation actions for tracked Slurm tasks whose labels already have candidates.",
    )
    parser.add_argument(
        "--cancel-solved-min-priority",
        type=int,
        default=30,
        help="Minimum selected source priority required before solved-label tasks are cancelled.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute computed enforcement actions. Without this, actions are dry-run only.",
    )
    parser.add_argument(
        "--sync-from",
        action="append",
        type=Path,
        help="Optional sibling outputs directory to rsync graph/TNS outputs from before summarizing.",
    )
    parser.add_argument(
        "--sync-multiseed-from",
        action="append",
        type=Path,
        help="Optional sibling outputs directory to rsync very-hard multiseed outputs from before summarizing.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    if args.sync_from:
        for sync_from in args.sync_from:
            source_outputs = sync_from if sync_from.is_absolute() else root / sync_from
            sync_named_outputs(root, source_outputs.resolve(), GRAPH_DIRS)
    if args.sync_multiseed_from:
        for sync_from in args.sync_multiseed_from:
            source_outputs = sync_from if sync_from.is_absolute() else root / sync_from
            sync_named_outputs(root, source_outputs.resolve(), MULTISEED_DIRS)
    data = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "slurm": slurm_summary(args.cpu_cap, args.gpu_cap),
        "candidates": candidate_status(root),
        "very_hard": graph_records(root),
        "multiseed": multiseed_records(root),
    }
    if args.enforce_caps or args.cancel_solved:
        data["enforcement_actions"] = enforcement_actions(
            root,
            data,
            args.cancel_solved,
            args.cancel_solved_min_priority,
        )
        if args.execute:
            execute_actions(data["enforcement_actions"])
            data["enforcement_executed"] = True
    if args.out:
        out = args.out if args.out.is_absolute() else root / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print_human(root, data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
