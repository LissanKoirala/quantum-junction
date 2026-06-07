#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHALLENGE_RE = re.compile(r"challenge-(\d+)_(\d+)\.qasm$")


def label_from_qasm(path: str) -> str:
    match = CHALLENGE_RE.search(Path(path).name)
    if not match:
        return ""
    return f"{match.group(1)}_{match.group(2)}"


def local_qasm_path(path: str, root: Path) -> str:
    candidate = Path(path)
    if not candidate.is_absolute():
        return candidate.as_posix()

    parts = candidate.parts
    if "challenges" in parts:
        idx = parts.index("challenges")
        return Path(*parts[idx:]).as_posix()

    try:
        return candidate.relative_to(root).as_posix()
    except ValueError:
        return candidate.as_posix()


def route_id(row: dict[str, str]) -> str:
    first_action = row.get("first_action", "")
    if first_action == "Exact statevector baseline":
        return "exact_statevector_baseline"
    if first_action.startswith("Exact if memory allows"):
        return "exact_statevector_optional"
    return row.get("best_method_id") or "unknown"


def default_route(row: dict[str, str], qasm: str) -> dict[str, Any]:
    route = route_id(row)
    best_method = row.get("best_method_id", "")
    qubits = int(row.get("num_qubits") or 0)

    if route.startswith("exact_statevector"):
        max_qubits = min(max(qubits, 1), 28)
        args = {
            "max_qubits": max_qubits,
            "topk": 8,
            "output_dir": "agent_work/exact_baseline",
        }
        command = [
            "python3",
            "agent_work/exact_baseline/aer_statevector_peaks.py",
            "--max-qubits",
            str(max_qubits),
            "--topk",
            "8",
            "--output-dir",
            args["output_dir"],
        ]
        return {
            "route_id": route,
            "route_scope": "batch_by_qubit_limit",
            "runner": "agent_work/exact_baseline/aer_statevector_peaks.py",
            "args": args,
            "command_preview": command,
            "fallback_method_id": best_method if route == "exact_statevector_optional" else "",
        }

    if route == "low_bond_mps_distillation":
        max_bond = 512 if qubits <= 48 else 1024
        samples = 2048 if qubits <= 48 else 4096
        args = {
            "qasm": qasm,
            "out_dir": "outputs/method_plan/low_bond_mps_distillation",
            "backend": "auto",
            "max_bond": max_bond,
            "cutoff": 1e-7,
            "gate_contract": "swap+split",
            "order_method": "weighted_spectral",
            "samples": samples,
            "sample_top_k": 12,
        }
        command = [
            "python3",
            "jobs/quimb_tree_tensor_runner.py",
            "--qasm",
            qasm,
            "--out-dir",
            args["out_dir"],
            "--backend",
            args["backend"],
            "--max-bond",
            str(max_bond),
            "--cutoff",
            str(args["cutoff"]),
            "--gate-contract",
            args["gate_contract"],
            "--order-method",
            args["order_method"],
            "--samples",
            str(samples),
            "--sample-top-k",
            str(args["sample_top_k"]),
        ]
        return {
            "route_id": route,
            "route_scope": "single_challenge",
            "runner": "jobs/quimb_tree_tensor_runner.py",
            "args": args,
            "command_preview": command,
            "fallback_method_id": "",
        }

    if route == "tno_contraction":
        args = {
            "qasm": qasm,
            "out_dir": "outputs/method_plan/tno_contraction",
            "backend": "numpy",
            "max_bond_tno": 32,
            "max_bond_tne": 16,
            "cutoff": 0.01,
            "chunk_size": 2,
            "method": "local-late",
        }
        command = [
            "python3",
            "jobs/tno_runner.py",
            "--qasm",
            qasm,
            "--out-dir",
            args["out_dir"],
            "--backend",
            args["backend"],
            "--max-bond-tno",
            str(args["max_bond_tno"]),
            "--max-bond-tne",
            str(args["max_bond_tne"]),
            "--cutoff",
            str(args["cutoff"]),
            "--chunk-size",
            str(args["chunk_size"]),
            "--method",
            args["method"],
        ]
        return {
            "route_id": route,
            "route_scope": "single_challenge",
            "runner": "jobs/tno_runner.py",
            "args": args,
            "command_preview": command,
            "fallback_method_id": "",
        }

    if route == "mpo_unswapping":
        args = {
            "qasm": qasm,
            "out_dir": "outputs/method_plan/mpo_unswapping",
            "backend": "auto",
            "max_bond": 8192,
            "mps_max_bond": 4096,
            "cutoff": 0.002,
            "unswap_threshold": 1_000_000,
            "center_ratio": 0.5,
            "max_its": 20,
            "sabre_trials": 512,
            "samples": 1000,
        }
        command = [
            "python3",
            "jobs/peaked_mpo_unswap_runner.py",
            "--qasm",
            qasm,
            "--out-dir",
            args["out_dir"],
            "--backend",
            args["backend"],
            "--max-bond",
            str(args["max_bond"]),
            "--mps-max-bond",
            str(args["mps_max_bond"]),
            "--cutoff",
            str(args["cutoff"]),
            "--unswap-threshold",
            str(args["unswap_threshold"]),
            "--center-ratio",
            str(args["center_ratio"]),
            "--max-its",
            str(args["max_its"]),
            "--sabre-trials",
            str(args["sabre_trials"]),
            "--samples",
            str(args["samples"]),
        ]
        return {
            "route_id": route,
            "route_scope": "single_challenge",
            "runner": "jobs/peaked_mpo_unswap_runner.py",
            "args": args,
            "command_preview": command,
            "fallback_method_id": "",
        }

    return {
        "route_id": route,
        "route_scope": "unmapped",
        "runner": "",
        "args": {},
        "command_preview": [],
        "fallback_method_id": "",
    }


def read_report(path: Path, root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            qasm = local_qasm_path(row.get("path", ""), root)
            label = label_from_qasm(qasm)
            route = default_route(row, qasm)
            rows.append(
                {
                    "challenge": label,
                    "qasm": qasm,
                    "qasm_exists": (root / qasm).exists(),
                    "difficulty": row.get("difficulty_group", ""),
                    "qubits": int(row.get("num_qubits") or 0),
                    "total_ops": int(row.get("total_ops") or 0),
                    "entangling_ops": int(row.get("entangling_ops") or 0),
                    "graph_density": float(row.get("graph_density") or 0.0),
                    "swap_count": int(row.get("swap_count") or 0),
                    "estimated_band": row.get("estimated_band", ""),
                    "exact_baseline": row.get("exact_baseline", ""),
                    "first_action": row.get("first_action", ""),
                    "best_method_id": row.get("best_method_id", ""),
                    "best_method_name": row.get("best_method_name", ""),
                    "scores": {
                        "best": int(row.get("best_score") or 0),
                        "mps": int(row.get("mps_score") or 0),
                        "tno": int(row.get("tno_score") or 0),
                        "mpo_unswapping": int(row.get("mpo_unswapping_score") or 0),
                    },
                    "planned_route": route,
                    "source_report": path.relative_to(root).as_posix(),
                }
            )
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "challenge",
        "difficulty",
        "qubits",
        "qasm",
        "qasm_exists",
        "first_action",
        "best_method_id",
        "best_score",
        "planned_route",
        "route_scope",
        "runner",
        "command_preview",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            route = row["planned_route"]
            writer.writerow(
                {
                    "challenge": row["challenge"],
                    "difficulty": row["difficulty"],
                    "qubits": row["qubits"],
                    "qasm": row["qasm"],
                    "qasm_exists": row["qasm_exists"],
                    "first_action": row["first_action"],
                    "best_method_id": row["best_method_id"],
                    "best_score": row["scores"]["best"],
                    "planned_route": route["route_id"],
                    "route_scope": route["route_scope"],
                    "runner": route["runner"],
                    "command_preview": " ".join(route["command_preview"]),
                }
            )


def write_readme(path: Path, rows: list[dict[str, Any]]) -> None:
    route_counts = Counter(row["planned_route"]["route_id"] for row in rows)
    method_counts = Counter(row["best_method_id"] for row in rows)
    missing_qasm = [row for row in rows if not row["qasm_exists"]]

    lines = [
        "# Method Plan",
        "",
        "Generated from `reports/qmill_method_report.csv` by `jobs/build_method_plan.py`.",
        "This is a routing plan only; it does not execute any simulations.",
        "",
        "## Summary",
        "",
        f"- Challenges planned: {len(rows)}",
        f"- Missing QASM paths: {len(missing_qasm)}",
        "",
        "## Planned Routes",
        "",
        "| route | challenges |",
        "|---|---:|",
    ]
    for route, count in sorted(route_counts.items()):
        lines.append(f"| `{route}` | {count} |")

    lines.extend(["", "## Best Paper Methods", "", "| method | challenges |", "|---|---:|"])
    for method, count in sorted(method_counts.items()):
        lines.append(f"| `{method}` | {count} |")

    lines.extend(
        [
            "",
            "## Challenge Plan",
            "",
            "| challenge | difficulty | q | first action | best paper method | planned route | runner |",
            "|---|---|---:|---|---|---|---|",
        ]
    )
    for row in rows:
        route = row["planned_route"]
        lines.append(
            "| "
            + " | ".join(
                [
                    row["challenge"],
                    row["difficulty"],
                    str(row["qubits"]),
                    row["first_action"],
                    row["best_method_id"],
                    route["route_id"],
                    f"`{route['runner']}`" if route["runner"] else "",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "- `plan.jsonl`: full structured route plan with arguments and command previews.",
            "- `plan.tsv`: compact tabular view for quick inspection.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a concrete route plan from the method selector report.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, default=ROOT / "reports" / "qmill_method_report.csv")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "research" / "method_plan")
    args = parser.parse_args()

    root = args.root.resolve()
    report = args.report if args.report.is_absolute() else root / args.report
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir

    rows = read_report(report, root)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "plan.jsonl", rows)
    write_tsv(out_dir / "plan.tsv", rows)
    write_readme(out_dir / "README.md", rows)
    print(f"wrote {len(rows)} planned routes under {out_dir.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
