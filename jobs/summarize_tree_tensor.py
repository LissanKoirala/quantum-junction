#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def summarize(out_dir: Path) -> Path:
    out_dir = out_dir.resolve()
    rows = []
    for path in sorted((out_dir / "json").glob("*.tree_tensor_mps.json")):
        data = load_json(path)
        final = data.get("final_candidate", {})
        validation = data.get("validation", {})
        trials = [t for t in data.get("trials", []) if t.get("status") == "ok"]
        best = None
        if trials:
            best = max(
                trials,
                key=lambda t: (
                    float(t.get("top_probability") or 0.0),
                    float(t.get("p1_margin_mean") or 0.0),
                ),
            )
        rows.append((data, final, validation, best, path))

    lines = [
        "# tree_tensor_sim summary",
        "",
        "Method: graph/mincut-derived qubit orderings with Aer matrix-product-state sampling.",
        "Status: this is a graph-aware MPS fallback, not the full TensorNetworkQuantumSimulator.jl boundary-MPS TNS implementation.",
        "",
        "| challenge | difficulty | q | status | final | source | known | match | best order | best bond | best top p | trials | json |",
        "|---|---|---:|---|---|---|---|---|---|---:|---:|---:|---|",
    ]
    for data, final, validation, best, path in rows:
        rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        lines.append(
            "| "
            + " | ".join(
                [
                    fmt(data.get("challenge_label")),
                    fmt(data.get("difficulty")),
                    fmt(data.get("num_qubits")),
                    fmt(data.get("status")),
                    f"`{fmt(final.get('candidate_qiskit_order'))}`",
                    fmt(final.get("source")),
                    f"`{fmt(validation.get('known_answer'))}`",
                    fmt(validation.get("final_matches_known")),
                    fmt(best.get("order_method") if best else None),
                    fmt(best.get("bond_dim") if best else None),
                    fmt(best.get("top_probability") if best else None),
                    fmt(len(data.get("trials", []))),
                    f"`{rel}`",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "Bit order: candidates are in Qiskit/counts order; the right-most bit is qubit 0.",
            "",
            "Next checks:",
            "",
            "- Compare all known-answer pilot rows before submitting the full 49-circuit sweep.",
            "- If pilot rows are unstable, increase shots first, then bond dimension, and inspect graph order span stats.",
        ]
    )
    summary_path = out_dir / "SUMMARY.md"
    summary_path.write_text("\n".join(lines) + "\n")
    return summary_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs" / "tree_tensor_sim" / "pilot")
    args = parser.parse_args()
    path = summarize(args.out_dir)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
