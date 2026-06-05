#!/usr/bin/env python3
"""Collect cheap, non-simulation metadata for the challenge QASM files."""

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "agent_work" / "exact_baseline"
QREG_RE = re.compile(r"^\s*qreg\s+\w+\[(\d+)\]\s*;")
OP_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]*)\b")
SKIP_OPS = {"OPENQASM", "include", "qreg", "creg", "barrier"}
TWO_QUBIT_OPS = {"cx", "swap"}


def parse_qasm(path: Path) -> dict:
    qubits = None
    gates = Counter()
    measurements = 0
    nonempty = 0

    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            nonempty += 1
            qreg_match = QREG_RE.match(stripped)
            if qreg_match:
                qubits = int(qreg_match.group(1))
            op_match = OP_RE.match(stripped)
            if not op_match:
                continue
            op = op_match.group(1)
            if op == "measure":
                measurements += 1
            if op not in SKIP_OPS and op != "measure":
                gates[op] += 1

    if qubits is None:
        raise ValueError(f"Could not find qreg declaration in {path}")

    statevector_bytes = 16 * (1 << qubits)
    statevector_gib = statevector_bytes / (1024**3)
    peak_scan_extra_gib = min(0.25, 8 * (1 << min(qubits, 22)) / (1024**3))
    rel = path.relative_to(ROOT)

    return {
        "path": str(rel),
        "difficulty": path.parent.name,
        "challenge": path.stem.replace("challenge-", ""),
        "qubits": qubits,
        "file_bytes": path.stat().st_size,
        "nonempty_qasm_lines": nonempty,
        "gates": sum(gates.values()),
        "one_qubit_gates": sum(count for op, count in gates.items() if op not in TWO_QUBIT_OPS),
        "two_qubit_gates": sum(count for op, count in gates.items() if op in TWO_QUBIT_OPS),
        "measurements": measurements,
        "gate_set": ",".join(sorted(gates)),
        "gate_counts": dict(sorted(gates.items())),
        "statevector_gib": statevector_gib,
        "peak_scan_extra_gib": peak_scan_extra_gib,
        "exact_statevector_safe": qubits <= 28,
    }


def write_csv(rows: list[dict], path: Path) -> None:
    fieldnames = [
        "path",
        "difficulty",
        "challenge",
        "qubits",
        "file_bytes",
        "nonempty_qasm_lines",
        "gates",
        "one_qubit_gates",
        "two_qubit_gates",
        "measurements",
        "gate_set",
        "statevector_gib",
        "peak_scan_extra_gib",
        "exact_statevector_safe",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row[name] for name in fieldnames})


def write_markdown(rows: list[dict], path: Path) -> None:
    by_diff: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_diff[row["difficulty"]].append(row)

    difficulty_order = ["very easy", "easy", "moderate", "hard", "very_hard"]
    lines = [
        "# Exact Baseline Feasibility",
        "",
        "Statevector memory assumes complex128 amplitudes only: `16 * 2^n` bytes.",
        "Actual simulator memory is higher, so this baseline caps exact statevector runs at 28 qubits.",
        "",
        "## Summary By Difficulty",
        "",
        "| difficulty | circuits | qubits | gate range | two-qubit gate range | safe exact SV |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for difficulty in difficulty_order:
        items = by_diff.get(difficulty, [])
        if not items:
            continue
        qubits = sorted({item["qubits"] for item in items})
        gates = [item["gates"] for item in items]
        twoq = [item["two_qubit_gates"] for item in items]
        safe = sum(1 for item in items if item["exact_statevector_safe"])
        lines.append(
            f"| {difficulty} | {len(items)} | {qubits[0]}-{qubits[-1]} | "
            f"{min(gates)}-{max(gates)} | {min(twoq)}-{max(twoq)} | {safe} |"
        )

    lines.extend(
        [
            "",
            "## Safe Exact Statevector Targets",
            "",
            "| challenge | difficulty | qubits | gates | two-qubit gates | statevector GiB |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        if row["exact_statevector_safe"]:
            lines.append(
                f"| {row['challenge']} | {row['difficulty']} | {row['qubits']} | "
                f"{row['gates']} | {row['two_qubit_gates']} | {row['statevector_gib']:.6g} |"
            )

    lines.extend(
        [
            "",
            "## 32+ Qubit Exact Statevector Limit",
            "",
            "A 32-qubit complex128 statevector alone is 64 GiB before simulator overhead. "
            "The `interruptible_cpu` partition reports roughly 62 GB or higher nodes, so 32-qubit "
            "statevector is not a safe default target here. Larger sizes grow by a factor of two "
            "per added qubit.",
            "",
            "| qubits | statevector GiB |",
            "|---:|---:|",
        ]
    )
    for qubits in [28, 29, 30, 31, 32, 36, 40, 48, 56, 64, 72, 80, 88, 96, 104]:
        lines.append(f"| {qubits} | {16 * (1 << qubits) / (1024**3):.6g} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    qasm_paths = sorted((ROOT / "challenges").glob("*/*.qasm"))
    rows = [parse_qasm(path) for path in qasm_paths]
    rows.sort(key=lambda row: (row["qubits"], row["difficulty"], row["challenge"]))

    write_csv(rows, OUT_DIR / "challenge_metadata.csv")
    (OUT_DIR / "challenge_metadata.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_markdown(rows, OUT_DIR / "feasibility.md")

    total_safe = sum(1 for row in rows if row["exact_statevector_safe"])
    print(f"Wrote metadata for {len(rows)} circuits; {total_safe} are <=28 qubits.")


if __name__ == "__main__":
    main()
