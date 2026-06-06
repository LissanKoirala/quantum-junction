#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


KNOWN = {
    "8_1": "10101101",
    "16_2": "1010101011001000",
    "24_3": "011110010000101010001000",
    "28_4": "1111111000101010110110011111",
    "8_11": "01001110",
    "16_12": "1111000101101011",
    "24_13": "111110011111001011010001",
    "8_27": "11001001",
    "16_28": "1101001111011100",
    "24_29": "110100010111100001001001",
}


def run_cmd(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=60)
    text = proc.stdout.strip()
    if proc.stderr.strip():
        text = (text + "\n" if text else "") + proc.stderr.strip()
    return text


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S %Z")


def hamming(a: str, b: str) -> int | None:
    if len(a) != len(b):
        return None
    return sum(x != y for x, y in zip(a, b))


def summarize_outputs(out_dir: Path) -> dict[str, Any]:
    json_dir = out_dir / "json"
    image_dir = out_dir / "images"
    stats_dir = out_dir / "stats"
    rows = []
    status_counts: Counter[str] = Counter()
    by_difficulty: dict[str, Counter[str]] = defaultdict(Counter)
    known_matches = []
    known_mismatches = []
    errors = []

    for path in sorted(json_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception as exc:  # noqa: BLE001 - monitor should not crash on partial writes
            status_counts["json_read_error"] += 1
            errors.append({"file": str(path), "error": repr(exc)})
            continue

        status = data.get("status", "missing")
        label = data.get("challenge_label", path.stem)
        difficulty = data.get("difficulty", "?")
        pred = data.get("pred_bitstring_qiskit_order")
        status_counts[status] += 1
        by_difficulty[difficulty][status] += 1

        row = {
            "file": path.name,
            "challenge": label,
            "difficulty": difficulty,
            "status": status,
            "candidate": pred,
            "error_type": data.get("error_type"),
            "total_seconds": data.get("total_seconds"),
        }
        if status == "error":
            errors.append(
                {
                    "challenge": label,
                    "error_type": data.get("error_type"),
                    "error": data.get("error"),
                }
            )
        if status == "ok" and label in KNOWN:
            hd = hamming(pred or "", KNOWN[label]) if pred else None
            row["known_answer"] = KNOWN[label]
            row["known_match"] = pred == KNOWN[label]
            row["known_hamming"] = hd
            if pred == KNOWN[label]:
                known_matches.append(label)
            else:
                known_mismatches.append({"challenge": label, "candidate": pred, "known": KNOWN[label], "hamming": hd})
        rows.append(row)

    return {
        "json_files": len(list(json_dir.glob("*.json"))),
        "images": len(list(image_dir.glob("*.png"))),
        "stats_jsonl": len(list(stats_dir.glob("*.jsonl"))),
        "status_counts": dict(status_counts),
        "by_difficulty": {k: dict(v) for k, v in sorted(by_difficulty.items())},
        "known_matches": known_matches,
        "known_mismatches": known_mismatches,
        "errors": errors,
        "rows": rows,
    }


def current_throttle(root: Path, job_id: str) -> int | None:
    text = run_cmd(["scontrol", "show", "job", job_id], cwd=root)
    marker = "ArrayTaskThrottle="
    if marker not in text:
        return None
    tail = text.split(marker, 1)[1]
    raw = tail.split(None, 1)[0]
    try:
        return int(raw)
    except ValueError:
        return None


def ensure_throttle(root: Path, job_id: str, desired: int) -> str:
    throttle = current_throttle(root, job_id)
    if throttle is None:
        return "No pending array throttle found."
    if throttle == desired:
        return f"ArrayTaskThrottle already {desired}."
    out = run_cmd(["scontrol", "update", f"JobID={job_id}", f"ArrayTaskThrottle={desired}"], cwd=root)
    throttle_after = current_throttle(root, job_id)
    return f"Requested ArrayTaskThrottle={desired}; before={throttle}; after={throttle_after}; scontrol={out!r}"


def append_log(
    log_path: Path,
    job_id: str,
    squeue_text: str,
    summary: dict[str, Any],
    throttle_action: str,
) -> None:
    lines = [
        "",
        f"## {now()}",
        "",
        f"- Monitored Slurm job: `{job_id}`",
        f"- Queue active: `{bool(squeue_text)}`",
        f"- Throttle action: `{throttle_action}`",
        f"- JSON files: `{summary['json_files']}`",
        f"- Images: `{summary['images']}`",
        f"- Stats JSONL: `{summary['stats_jsonl']}`",
        f"- Status counts: `{summary['status_counts']}`",
        f"- Known-reference matches: `{summary['known_matches']}`",
    ]
    if summary["known_mismatches"]:
        lines.append(f"- Known-reference mismatches: `{summary['known_mismatches']}`")
    if summary["errors"]:
        lines.append(f"- Error records: `{summary['errors'][:5]}`")
    if squeue_text:
        lines.extend(["", "```text", squeue_text, "```"])
    log_path.open("a").write("\n".join(lines) + "\n")


def write_final(out_dir: Path, job_id: str, sacct_text: str, summary: dict[str, Any]) -> None:
    final_path = out_dir / "MONITOR_FINAL.md"
    lines = [
        "# peaked-circuit-simulation monitor final",
        "",
        f"Finished monitoring at: `{now()}`",
        f"Slurm job: `{job_id}`",
        "",
        "## Output Summary",
        "",
        f"- JSON files: `{summary['json_files']}`",
        f"- Images: `{summary['images']}`",
        f"- Stats JSONL: `{summary['stats_jsonl']}`",
        f"- Status counts: `{summary['status_counts']}`",
        f"- By difficulty: `{summary['by_difficulty']}`",
        f"- Known-reference matches: `{summary['known_matches']}`",
        f"- Known-reference mismatches: `{summary['known_mismatches']}`",
        f"- Error records: `{summary['errors']}`",
        "",
        "## Sacct",
        "",
        "```text",
        sacct_text or "(no sacct output)",
        "```",
        "",
        "## Suggested Next Action",
        "",
    ]
    if summary["errors"]:
        lines.append("- Inspect error JSON/logs and create a retry manifest for failed circuits.")
    if summary["known_mismatches"]:
        lines.append("- Rerun known-answer mismatches with stricter parameters, e.g. higher `max_bond` or lower `cutoff`.")
    if summary["status_counts"].get("started"):
        lines.append("- Some JSON files remained in `started`; check Slurm state for preemption/timeouts before trusting results.")
    if not summary["errors"] and not summary["known_mismatches"] and not summary["status_counts"].get("started"):
        lines.append("- No automatic retry suggested by the monitor.")
    final_path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", default="34607501")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out-dir", type=Path, default=Path("outputs/peaked_circuit_sim_all"))
    parser.add_argument("--interval-seconds", type=int, default=1800)
    parser.add_argument("--max-checks", type=int, default=96)
    parser.add_argument("--array-throttle", type=int, default=49)
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "RUN_LOG.md"
    status_path = out_dir / "MONITOR_STATUS.json"

    for check in range(args.max_checks):
        throttle_action = ensure_throttle(root, args.job_id, args.array_throttle)
        squeue_text = run_cmd(
            ["squeue", "-j", args.job_id, "-o", "%.30i %.9P %.30j %.8T %.10M %.6D %R"],
            cwd=root,
        )
        summary = summarize_outputs(out_dir)
        payload = {
            "timestamp": now(),
            "job_id": args.job_id,
            "check": check,
            "queue_active": bool(squeue_text),
            "throttle_action": throttle_action,
            "summary": summary,
        }
        status_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        append_log(log_path, args.job_id, squeue_text, summary, throttle_action)

        if not squeue_text:
            sacct_text = run_cmd(
                [
                    "sacct",
                    "-j",
                    args.job_id,
                    "--format=JobID,JobName%24,Partition,State,Elapsed,Timelimit,AllocTRES%40,ExitCode",
                    "-P",
                ],
                cwd=root,
            )
            write_final(out_dir, args.job_id, sacct_text, summary)
            return 0

        time.sleep(args.interval_seconds)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
