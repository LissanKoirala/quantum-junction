#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def top_counter(counter: Counter, limit: int = 5) -> list[dict]:
    total = sum(counter.values())
    return [
        {"bitstring": bitstring, "support": int(count), "fraction": count / total if total else 0.0}
        for bitstring, count in counter.most_common(limit)
    ]


def classify(summary: dict) -> str:
    if summary["ok_trials"] == 0:
        return "no_successful_trials"
    if summary["top1_winner"] != summary["aggregate_winner"]:
        return "unstable_top1_vs_aggregate"
    if summary["high_config_unique_top1"] == 1 and summary["top1_vote_fraction"] >= 0.50:
        return "stable_high_config"
    if summary["top1_vote_fraction"] >= 0.67 and summary["aggregate_gap_ratio"] >= 1.10:
        return "stable_votes"
    return "unstable"


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize MPS trial JSON files.")
    parser.add_argument(
        "--results-dir",
        default="agent_work/mps_distill/results",
        help="Directory containing per-trial JSON files.",
    )
    parser.add_argument(
        "--config-file",
        default="agent_work/mps_distill/configs/pilot_easy_hard.jsonl",
        help="JSONL config file used for expected task counts.",
    )
    parser.add_argument(
        "--out-dir",
        default="agent_work/mps_distill/summaries",
        help="Directory for summary outputs.",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    expected = read_jsonl(Path(args.config_file))
    expected_by_circuit = Counter(row["circuit"] for row in expected)

    records = []
    for path in sorted(results_dir.glob("*.json")):
        with path.open() as f:
            record = json.load(f)
        record["_path"] = str(path)
        records.append(record)

    grouped: dict[str, list[dict]] = defaultdict(list)
    failed = []
    for record in records:
        cfg = record.get("config", {})
        circuit = cfg.get("circuit", "unknown")
        if record.get("status") == "ok":
            grouped[circuit].append(record)
        else:
            failed.append(record)

    circuit_summaries = []
    for circuit in sorted(set(expected_by_circuit) | set(grouped)):
        trials = grouped.get(circuit, [])
        top1_votes = Counter()
        aggregate_counts = Counter()
        per_setting: dict[tuple[int, int], list[str]] = defaultdict(list)
        timings = []
        distinct_outcomes = []
        top_probs = []
        metadata = {}

        max_shots = 0
        max_bond = 0
        for record in trials:
            cfg = record["config"]
            sampling = record["sampling"]
            top = sampling["top_bitstring"]
            shots = int(cfg["shots"])
            bond_dim = int(cfg["bond_dim"])
            max_shots = max(max_shots, shots)
            max_bond = max(max_bond, bond_dim)
            top1_votes[top] += 1
            per_setting[(shots, bond_dim)].append(top)
            for bitstring, count in sampling["top_counts"]:
                aggregate_counts[bitstring] += int(count)
            timings.append(float(record["timing_seconds"]["total"]))
            distinct_outcomes.append(int(sampling["distinct_outcomes"]))
            top_probs.append(float(sampling["top_probability"]))
            metadata = record.get("circuit_metadata", metadata)

        top1_total = sum(top1_votes.values())
        top1_winner, top1_winner_votes = ("", 0)
        if top1_votes:
            top1_winner, top1_winner_votes = top1_votes.most_common(1)[0]

        aggregate_winner, aggregate_winner_support = ("", 0)
        aggregate_gap_ratio = 0.0
        if aggregate_counts:
            aggregate_ranked = aggregate_counts.most_common(2)
            aggregate_winner, aggregate_winner_support = aggregate_ranked[0]
            runner_up = aggregate_ranked[1][1] if len(aggregate_ranked) > 1 else 0
            aggregate_gap_ratio = (
                aggregate_winner_support / runner_up if runner_up else float("inf")
            )

        high_top1 = per_setting.get((max_shots, max_bond), [])
        row = {
            "circuit": circuit,
            "expected_trials": int(expected_by_circuit.get(circuit, 0)),
            "ok_trials": len(trials),
            "missing_trials": int(expected_by_circuit.get(circuit, 0)) - len(trials),
            "num_qubits": metadata.get("num_qubits"),
            "depth_original": metadata.get("depth_original"),
            "top1_winner": top1_winner,
            "top1_winner_votes": int(top1_winner_votes),
            "top1_vote_fraction": top1_winner_votes / top1_total if top1_total else 0.0,
            "aggregate_winner": aggregate_winner,
            "aggregate_winner_support": int(aggregate_winner_support),
            "aggregate_gap_ratio": aggregate_gap_ratio,
            "candidate": aggregate_winner,
            "high_config": {"shots": max_shots, "bond_dim": max_bond},
            "high_config_top1": high_top1,
            "high_config_unique_top1": len(set(high_top1)),
            "mean_total_seconds": sum(timings) / len(timings) if timings else None,
            "max_total_seconds": max(timings) if timings else None,
            "mean_distinct_outcomes": (
                sum(distinct_outcomes) / len(distinct_outcomes) if distinct_outcomes else None
            ),
            "mean_top_probability": sum(top_probs) / len(top_probs) if top_probs else None,
            "top1_vote_rank": top_counter(top1_votes),
            "aggregate_rank": top_counter(aggregate_counts),
            "per_setting_top1": {
                f"shots-{shots}__bd-{bond}": values
                for (shots, bond), values in sorted(per_setting.items())
            },
        }
        row["classification"] = classify(row)
        circuit_summaries.append(row)

    summary_payload = {
        "results_dir": str(results_dir),
        "config_file": args.config_file,
        "total_records": len(records),
        "failed_records": len(failed),
        "circuits": circuit_summaries,
        "failed": [
            {
                "path": record.get("_path"),
                "config": record.get("config"),
                "error": record.get("error"),
            }
            for record in failed
        ],
    }

    json_path = out_dir / "pilot_summary.json"
    with json_path.open("w") as f:
        json.dump(summary_payload, f, indent=2, sort_keys=True)

    candidates_path = out_dir / "pilot_candidates.tsv"
    with candidates_path.open("w") as f:
        f.write(
            "classification\tcircuit\tcandidate\ttop1_vote_fraction\taggregate_gap_ratio\t"
            "ok_trials\texpected_trials\thigh_config_top1\n"
        )
        for row in circuit_summaries:
            f.write(
                "\t".join(
                    [
                        row["classification"],
                        row["circuit"],
                        row["candidate"],
                        f"{row['top1_vote_fraction']:.3f}",
                        (
                            "inf"
                            if row["aggregate_gap_ratio"] == float("inf")
                            else f"{row['aggregate_gap_ratio']:.3f}"
                        ),
                        str(row["ok_trials"]),
                        str(row["expected_trials"]),
                        ",".join(row["high_config_top1"]),
                    ]
                )
                + "\n"
            )

    markdown_path = out_dir / "pilot_summary.md"
    with markdown_path.open("w") as f:
        f.write("# MPS pilot summary\n\n")
        f.write(
            "| classification | circuit | q | trials | candidate | top1 votes | "
            "agg gap | high config top1 | mean p(top1) | max sec |\n"
        )
        f.write("|---|---:|---:|---:|---|---:|---:|---|---:|---:|\n")
        for row in circuit_summaries:
            gap = "inf" if row["aggregate_gap_ratio"] == float("inf") else f"{row['aggregate_gap_ratio']:.2f}"
            mean_p = "" if row["mean_top_probability"] is None else f"{row['mean_top_probability']:.4f}"
            max_sec = "" if row["max_total_seconds"] is None else f"{row['max_total_seconds']:.1f}"
            f.write(
                "| {classification} | {circuit} | {q} | {ok}/{expected} | `{candidate}` | "
                "{vote:.2f} | {gap} | `{high}` | {mean_p} | {max_sec} |\n".format(
                    classification=row["classification"],
                    circuit=row["circuit"],
                    q=row["num_qubits"] or "",
                    ok=row["ok_trials"],
                    expected=row["expected_trials"],
                    candidate=row["candidate"],
                    vote=row["top1_vote_fraction"],
                    gap=gap,
                    high="`, `".join(row["high_config_top1"]),
                    mean_p=mean_p,
                    max_sec=max_sec,
                )
            )

        if failed:
            f.write("\n## Failed trials\n\n")
            for record in failed:
                f.write(f"- `{record.get('_path')}`: {record.get('error')}\n")

    print(f"wrote {json_path}")
    print(f"wrote {candidates_path}")
    print(f"wrote {markdown_path}")
    for row in circuit_summaries:
        print(
            row["classification"],
            row["circuit"],
            row["candidate"],
            f"vote={row['top1_vote_fraction']:.2f}",
            f"ok={row['ok_trials']}/{row['expected_trials']}",
        )


if __name__ == "__main__":
    main()
