#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
import argparse
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "peaked-circuit-simulation"))

from utils import contract_core, iter_layers, tno_to_tne  # noqa: E402


def extract_candidate(tne):
    pi0 = np.array([[1.0, 0.0], [0.0, 0.0]], dtype=np.complex128)
    p0s = []
    bits = []
    for site in range(len(tne.sites)):
        try:
            val = tne.local_expectation_canonical(pi0, where=site, normalized=True)
        except Exception:
            val = tne.local_expectation(
                pi0,
                where=[site],
                normalized=True,
                max_bond=4,
                optimize="greedy",
            )
        p0 = float(np.real(val))
        p0s.append(p0)
        bits.append("1" if p0 < 0.5 else "0")
    margins = [abs(p - 0.5) for p in p0s]
    return {
        "raw_q0_order": "".join(bits),
        "qiskit_order": "".join(reversed(bits)),
        "p0s_q0_order": p0s,
        "margin_min": min(margins),
        "margin_mean": float(np.mean(margins)),
        "margin_max": max(margins),
    }


def parse_setting(text: str) -> tuple[int, float, int]:
    parts = text.split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("settings must be max_bond,cutoff,chunk")
    return int(parts[0]), float(parts[1]), int(parts[2])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qasm", type=Path, default=ROOT / "challenges" / "hard" / "challenge-64_41.qasm")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "solve_64_41" / "tno_midpoint.jsonl")
    parser.add_argument(
        "--setting",
        action="append",
        type=parse_setting,
        help="Run setting as max_bond,cutoff,chunk. Can be repeated.",
    )
    args = parser.parse_args()

    qasm = args.qasm if args.qasm.is_absolute() else ROOT / args.qasm
    qc = QuantumCircuit.from_qasm_file(str(qasm)).remove_final_measurements(inplace=False)
    layers = list(iter_layers(qc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    header = {"qasm": str(qasm), "qubits": qc.num_qubits, "layers": len(layers), "ops": len(qc)}
    print(json.dumps(header), flush=True)
    with args.out.open("a") as f:
        f.write(json.dumps({"event": "start", **header}, sort_keys=True) + "\n")

    settings = args.setting or [
        (4, 0.20, 12),
        (8, 0.15, 10),
        (8, 0.10, 8),
        (16, 0.08, 6),
    ]
    for max_bond, cutoff, chunk in settings:
        row = {"max_bond": max_bond, "cutoff": cutoff, "chunk": chunk}
        print("RUN " + json.dumps(row), flush=True)
        started = time.time()
        try:
            tno, stats = contract_core(
                layers,
                chunk_size=chunk,
                method="local-late",
                max_bond=max_bond,
                cutoff=cutoff,
                equalize_norms=True,
                to_backend=None,
            )
            print(
                "CONTRACTED "
                + json.dumps(
                    {
                        **row,
                        "seconds": time.time() - started,
                        "last_stat": stats[-1] if stats else None,
                    }
                ),
                flush=True,
            )
            tne = tno_to_tne(tno, max_bond=max_bond, cutoff=cutoff, to_backend=None)
            result = {
                "event": "candidate",
                **row,
                **extract_candidate(tne),
                "seconds": time.time() - started,
                "last_stat": stats[-1] if stats else None,
            }
            print("CAND " + json.dumps(result), flush=True)
            with args.out.open("a") as f:
                f.write(json.dumps(result, sort_keys=True) + "\n")
        except Exception as exc:
            import traceback

            result = {
                "event": "error",
                **row,
                "error_type": type(exc).__name__,
                "error": repr(exc),
                "traceback_tail": traceback.format_exc()[-1200:],
            }
            print("ERR " + json.dumps(result), flush=True)
            with args.out.open("a") as f:
                f.write(json.dumps(result, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
