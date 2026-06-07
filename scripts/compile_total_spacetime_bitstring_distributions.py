#!/usr/bin/env python3
"""Compile reported total-spacetime bitstrings into compact plot artifacts.

The pipeline JSONs contain several bitstring observations: extracted temporal
peaks, spacetime-block peaks, exact/small-case candidates, and peak-extraction
candidate lists. This script aggregates those observations by bitstring and
writes compact JSON/CSV summaries plus GitHub-viewable PNG bar charts.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


BITSTRING_FIELDS = {
    "best_bitstring_original_order": "original",
    "best_bitstring_working_order": "working",
    "bitstring_original_order": "original",
    "bitstring_working_order": "working",
    "spawned_bridge_bitstring_original_order": "original",
    "exact_peak_bitstring": "working",
    "peak_bitstring": "working",
    "raw_site_bitstring": "site",
    "best_site_bitstring": "site",
    "marginal_site_bitstring": "site",
    "site_bitstring": "site",
}

PROBABILITY_FIELDS = (
    "probability_estimate",
    "peak_probability",
    "exact_peak_probability",
    "best_probability_estimate",
    "extracted_probability_estimate",
    "marginal_probability_estimate",
)


@dataclass
class Bucket:
    bitstring: str
    order: str
    observation_count: int = 0
    probability_sum: float = 0.0
    probability_count: int = 0
    sample_count_sum: int = 0
    sources: set[str] = field(default_factory=set)

    def add(self, *, probability: float | None, sample_count: int | None, source: str) -> None:
        self.observation_count += 1
        if probability is not None and math.isfinite(probability):
            self.probability_sum += probability
            self.probability_count += 1
        if sample_count is not None:
            self.sample_count_sum += sample_count
        self.sources.add(source)

    def as_dict(self) -> dict[str, Any]:
        mean_probability = (
            self.probability_sum / self.probability_count
            if self.probability_count
            else None
        )
        return {
            "bitstring": self.bitstring,
            "order": self.order,
            "observation_count": self.observation_count,
            "probability_sum": self.probability_sum,
            "probability_count": self.probability_count,
            "mean_probability": mean_probability,
            "sample_count_sum": self.sample_count_sum,
            "sources": sorted(self.sources),
        }


def is_bitstring(value: Any, n_qubits: int | None) -> bool:
    if not isinstance(value, str):
        return False
    if not value or any(ch not in "01" for ch in value):
        return False
    if n_qubits is not None and len(value) != n_qubits:
        return False
    return True


def first_float(obj: dict[str, Any]) -> float | None:
    for key in PROBABILITY_FIELDS:
        value = obj.get(key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
    return None


def sample_count(obj: dict[str, Any]) -> int | None:
    value = obj.get("sample_count")
    if isinstance(value, int):
        return value
    return None


def walk_observations(
    obj: Any,
    *,
    n_qubits: int | None,
    path: str,
    out: list[dict[str, Any]],
) -> None:
    if isinstance(obj, dict):
        probability = first_float(obj)
        samples = sample_count(obj)
        for field_name, order in BITSTRING_FIELDS.items():
            value = obj.get(field_name)
            if is_bitstring(value, n_qubits):
                out.append(
                    {
                        "bitstring": value,
                        "order": order,
                        "probability": probability,
                        "sample_count": samples,
                        "source": f"{path}.{field_name}" if path else field_name,
                    }
                )
        for key, value in obj.items():
            child_path = f"{path}.{key}" if path else str(key)
            walk_observations(value, n_qubits=n_qubits, path=child_path, out=out)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            walk_observations(value, n_qubits=n_qubits, path=f"{path}[{index}]", out=out)


def aggregate(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], Bucket] = {}
    for obs in observations:
        key = (obs["order"], obs["bitstring"])
        bucket = buckets.setdefault(key, Bucket(bitstring=obs["bitstring"], order=obs["order"]))
        bucket.add(
            probability=obs.get("probability"),
            sample_count=obs.get("sample_count"),
            source=obs["source"],
        )
    return sorted(
        (bucket.as_dict() for bucket in buckets.values()),
        key=lambda row: (
            row["observation_count"],
            row["sample_count_sum"],
            row["probability_sum"],
            row["bitstring"],
        ),
        reverse=True,
    )


def safe_stem(path: Path) -> str:
    parts = path.with_suffix("").parts
    if "total_spacetime" in parts:
        parts = parts[parts.index("total_spacetime") + 1 :]
    return "__".join(parts).replace("/", "__")


def plot_distribution(rows: list[dict[str, Any]], title: str, out_path: Path, top_n: int) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_rows = rows[:top_n]
    if not plot_rows:
        return

    labels = [f"{row['bitstring']} ({row['order'][0]})" for row in plot_rows]
    counts = [row["observation_count"] for row in plot_rows]
    probabilities = [row["probability_sum"] for row in plot_rows]
    y = list(range(len(plot_rows)))

    fig, axes = plt.subplots(1, 2, figsize=(15, max(5, 0.34 * len(plot_rows) + 1.8)))
    axes[0].barh(y, counts, color="#2f6f8f")
    axes[0].set_title("observations")
    axes[0].set_yticks(y, labels)
    axes[0].invert_yaxis()
    axes[0].set_xlabel("count")

    axes[1].barh(y, probabilities, color="#9b5f25")
    axes[1].set_title("summed probability estimates")
    axes[1].set_yticks(y, labels)
    axes[1].invert_yaxis()
    axes[1].set_xlabel("probability sum")

    fig.suptitle(title)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def write_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rank",
                "bitstring",
                "order",
                "observation_count",
                "probability_sum",
                "probability_count",
                "mean_probability",
                "sample_count_sum",
                "sources",
            ],
        )
        writer.writeheader()
        for rank, row in enumerate(rows, 1):
            writer.writerow({**row, "rank": rank, "sources": ";".join(row["sources"])})


def discover_inputs(root: Path) -> list[Path]:
    skip_parts = {"bitstring_distributions"}
    paths = []
    for path in root.rglob("*.json"):
        if skip_parts.intersection(path.parts):
            continue
        paths.append(path)
    return sorted(paths)


def process_file(path: Path, out_dir: Path, top_n: int) -> dict[str, Any]:
    data = json.loads(path.read_text())
    n_qubits = data.get("n_qubits")
    if not isinstance(n_qubits, int):
        n_qubits = None

    observations: list[dict[str, Any]] = []
    walk_observations(data, n_qubits=n_qubits, path="", out=observations)
    rows = aggregate(observations)

    stem = safe_stem(path)
    dist_path = out_dir / "json" / f"{stem}.distribution.json"
    csv_path = out_dir / "csv" / f"{stem}.distribution.csv"
    plot_path = out_dir / "plots" / f"{stem}.top_bitstrings.png"

    dist_path.parent.mkdir(parents=True, exist_ok=True)
    dist_payload = {
        "source_json": str(path),
        "label": data.get("label", path.stem),
        "n_qubits": n_qubits,
        "n_observations": len(observations),
        "n_unique_bitstrings": len(rows),
        "best_reported_original_order": data.get("best_bitstring_original_order"),
        "best_reported_working_order": data.get("best_bitstring_working_order"),
        "top_bitstrings": rows,
    }
    dist_path.write_text(json.dumps(dist_payload, indent=2, sort_keys=True) + "\n")
    write_csv(rows, csv_path)
    if rows:
        plot_distribution(rows, f"{data.get('label', path.stem)} bitstring distribution", plot_path, top_n)

    top = rows[0] if rows else None
    top_original = next((row for row in rows if row["order"] == "original"), None)
    top_working = next((row for row in rows if row["order"] == "working"), None)
    return {
        "source_json": str(path),
        "label": data.get("label", path.stem),
        "n_qubits": n_qubits,
        "n_observations": len(observations),
        "n_unique_bitstrings": len(rows),
        "best_reported_original_order": data.get("best_bitstring_original_order"),
        "best_reported_working_order": data.get("best_bitstring_working_order"),
        "most_common_bitstring": top["bitstring"] if top else None,
        "most_common_order": top["order"] if top else None,
        "most_common_observation_count": top["observation_count"] if top else 0,
        "most_common_original_bitstring": top_original["bitstring"] if top_original else None,
        "most_common_original_count": top_original["observation_count"] if top_original else 0,
        "most_common_working_bitstring": top_working["bitstring"] if top_working else None,
        "most_common_working_count": top_working["observation_count"] if top_working else 0,
        "plot": str(plot_path),
        "distribution_json": str(dist_path),
        "distribution_csv": str(csv_path),
    }


def write_index(summaries: list[dict[str, Any]], out_dir: Path) -> None:
    lines = [
        "# Total Spacetime Bitstring Distributions",
        "",
        "Compiled from completed `outputs/total_spacetime/**/*.json` files.",
        "Bars count reported bitstring observations from temporal and spacetime peak extraction fields; probability bars sum any probability estimates attached to those observations.",
        "",
        "| source | label | qubits | observations | unique | most common | original-order top | final original | plot |",
        "|---|---|---:|---:|---:|---|---|---|---|",
    ]
    for row in summaries:
        plot_rel = Path(row["plot"]).relative_to(out_dir)
        source_name = Path(row["source_json"]).name
        lines.append(
            f"| `{source_name}` | {row['label']} | {row['n_qubits']} | {row['n_observations']} | "
            f"{row['n_unique_bitstrings']} | `{row['most_common_bitstring']}` "
            f"({row['most_common_order']}, {row['most_common_observation_count']}) | "
            f"`{row['most_common_original_bitstring']}` ({row['most_common_original_count']}) | "
            f"`{row['best_reported_original_order']}` | "
            f"[png]({plot_rel.as_posix()}) |"
        )
    lines.append("")
    for row in summaries:
        plot_rel = Path(row["plot"]).relative_to(out_dir)
        lines.append(f"## {row['label']}")
        lines.append("")
        lines.append(f"Most common: `{row['most_common_bitstring']}` ({row['most_common_order']})")
        lines.append("")
        lines.append(f"![{row['label']}]({plot_rel.as_posix()})")
        lines.append("")
    (out_dir / "README.md").write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("outputs/total_spacetime"))
    parser.add_argument("--out", type=Path, default=Path("outputs/total_spacetime/bitstring_distributions"))
    parser.add_argument("--top-n", type=int, default=30)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    summaries = [process_file(path, args.out, args.top_n) for path in discover_inputs(args.root)]
    summaries.sort(key=lambda row: row["label"])
    (args.out / "summary.json").write_text(json.dumps(summaries, indent=2, sort_keys=True) + "\n")
    write_index(summaries, args.out)
    print(f"wrote {len(summaries)} distribution summaries to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
