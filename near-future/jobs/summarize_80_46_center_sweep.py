#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any


def hamming(a: str, b: str) -> int | None:
    if not a or not b or len(a) != len(b):
        return None
    return sum(x != y for x, y in zip(a, b))


def top_fraction(record: dict[str, Any]) -> float | None:
    value = (record.get("sampling") or {}).get("top_fraction")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path("outputs/tree_tensor_sim/solve_80_46_centers"),
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    rows = []
    for path in sorted(args.root.glob("*/json/*.json")):
        data = json.loads(path.read_text())
        params = data.get("parameters") or {}
        candidate = data.get("final_candidate_qiskit_order")
        rows.append(
            {
                "tag": path.parts[-3],
                "status": data.get("status"),
                "candidate": candidate,
                "top_fraction": top_fraction(data),
                "max_bond": (data.get("mps_info") or {}).get("max_bond"),
                "seconds": data.get("total_seconds"),
                "center_ratio": params.get("center_ratio"),
                "core_window_gates": params.get("core_window_gates"),
                "cutoff": params.get("cutoff"),
                "json": path,
            }
        )

    counts = collections.Counter(row["candidate"] for row in rows if row["candidate"])
    best = counts.most_common(1)[0][0] if counts else None

    lines = [
        "# 80_46 Center Sweep Summary",
        "",
        f"Runs found: {len(rows)}",
        "",
        "| tag | status | candidate | votes | hamming to best | top fraction | max bond | sec | center | window | cutoff | json |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        cand = row["candidate"] or ""
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["tag"]),
                    str(row["status"]),
                    f"`{cand}`" if cand else "",
                    str(counts.get(cand, 0) if cand else 0),
                    str(hamming(cand, best) if cand and best else ""),
                    "" if row["top_fraction"] is None else f"{row['top_fraction']:.6g}",
                    str(row["max_bond"] or ""),
                    "" if row["seconds"] is None else f"{float(row['seconds']):.1f}",
                    str(row["center_ratio"]),
                    str(row["core_window_gates"]),
                    str(row["cutoff"]),
                    f"`{row['json']}`",
                ]
            )
            + " |"
        )

    lines.extend(["", "## Candidate Vote Counts", ""])
    for candidate, count in counts.most_common():
        lines.append(f"- `{candidate}`: {count}")

    text = "\n".join(lines) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
