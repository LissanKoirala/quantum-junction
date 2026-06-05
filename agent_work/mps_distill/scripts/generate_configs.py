#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


PILOT_CIRCUITS = [
    "challenges/easy/challenge-8_11.qasm",
    "challenges/easy/challenge-16_12.qasm",
    "challenges/easy/challenge-40_16.qasm",
    "challenges/hard/challenge-40_35.qasm",
    "challenges/hard/challenge-48_36.qasm",
    "challenges/hard/challenge-64_41.qasm",
]

PILOT_SETTINGS = [
    {"shots": 512, "bond_dim": 16},
    {"shots": 2048, "bond_dim": 32},
    {"shots": 4096, "bond_dim": 64},
]

PILOT_SEEDS = [101, 202]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate JSONL configs for MPS sampling trials."
    )
    parser.add_argument(
        "--output",
        default="agent_work/mps_distill/configs/pilot_easy_hard.jsonl",
        help="Output JSONL config path.",
    )
    parser.add_argument(
        "--label",
        default="pilot_easy_hard",
        help="Experiment label embedded in each config.",
    )
    args = parser.parse_args()

    rows = []
    task_id = 1
    for circuit in PILOT_CIRCUITS:
        for setting in PILOT_SETTINGS:
            for seed in PILOT_SEEDS:
                rows.append(
                    {
                        "task_id": task_id,
                        "label": args.label,
                        "circuit": circuit,
                        "shots": setting["shots"],
                        "bond_dim": setting["bond_dim"],
                        "seed": seed,
                        "truncation_threshold": 1e-12,
                    }
                )
                task_id += 1

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    print(f"wrote {len(rows)} configs to {out_path}")


if __name__ == "__main__":
    main()
