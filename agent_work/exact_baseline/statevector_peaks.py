#!/usr/bin/env python3
"""Run exact statevector simulation for small challenge circuits and report peaks."""

from __future__ import annotations

import argparse
import csv
import gc
import json
import os
import re
import resource
import sys
import time
import traceback
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector


ROOT = Path(__file__).resolve().parents[2]
QREG_RE = re.compile(r"^\s*qreg\s+\w+\[(\d+)\]\s*;")


def qreg_size(path: Path) -> int:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            match = QREG_RE.match(line)
            if match:
                return int(match.group(1))
    raise ValueError(f"Could not find qreg declaration in {path}")


def bitstring_from_index(index: int, num_qubits: int) -> str:
    return format(index, f"0{num_qubits}b")


def topk_probabilities(data: np.ndarray, num_qubits: int, topk: int, chunk_elems: int) -> tuple[list[dict], float]:
    best_indices = np.empty(0, dtype=np.int64)
    best_probs = np.empty(0, dtype=np.float64)
    norm = 0.0
    total = data.shape[0]

    for start in range(0, total, chunk_elems):
        stop = min(start + chunk_elems, total)
        chunk = data[start:stop]
        probs = chunk.real * chunk.real + chunk.imag * chunk.imag
        norm += float(np.sum(probs, dtype=np.float64))

        if probs.size <= topk:
            local = np.arange(probs.size)
        else:
            local = np.argpartition(probs, -topk)[-topk:]
        candidate_indices = local.astype(np.int64, copy=False) + start
        candidate_probs = probs[local].astype(np.float64, copy=False)

        if best_indices.size:
            candidate_indices = np.concatenate([best_indices, candidate_indices])
            candidate_probs = np.concatenate([best_probs, candidate_probs])

        keep = min(topk, candidate_probs.size)
        keep_local = np.argpartition(candidate_probs, -keep)[-keep:]
        best_indices = candidate_indices[keep_local]
        best_probs = candidate_probs[keep_local]

    order = np.argsort(best_probs)[::-1]
    top = []
    for rank, item in enumerate(order, start=1):
        index = int(best_indices[item])
        prob = float(best_probs[item])
        top.append(
            {
                "rank": rank,
                "index": index,
                "bitstring": bitstring_from_index(index, num_qubits),
                "probability": prob,
            }
        )
    return top, norm


def simulate_one(path: Path, topk: int, chunk_elems: int) -> dict:
    rel = path.relative_to(ROOT)
    num_qubits = qreg_size(path)
    started = time.monotonic()

    qc = QuantumCircuit.from_qasm_file(str(path))
    qc_no_meas = qc.remove_final_measurements(inplace=False)
    if qc_no_meas.num_qubits != num_qubits:
        raise ValueError(f"QASM qreg says {num_qubits}, Qiskit loaded {qc_no_meas.num_qubits}")

    sv = Statevector.from_instruction(qc_no_meas)
    data = np.asarray(sv.data)
    top, norm = topk_probabilities(data, num_qubits, topk, chunk_elems)

    elapsed = time.monotonic() - started
    maxrss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {
        "path": str(rel),
        "difficulty": path.parent.name,
        "challenge": path.stem.replace("challenge-", ""),
        "qubits": num_qubits,
        "gates": len(qc_no_meas.data),
        "peak_bitstring": top[0]["bitstring"],
        "peak_probability": top[0]["probability"],
        "second_bitstring": top[1]["bitstring"] if len(top) > 1 else None,
        "second_probability": top[1]["probability"] if len(top) > 1 else None,
        "gap_to_second": top[0]["probability"] - top[1]["probability"] if len(top) > 1 else None,
        "norm": norm,
        "top": top,
        "elapsed_seconds": elapsed,
        "maxrss_kb": maxrss_kb,
    }

    del sv, data, qc, qc_no_meas
    gc.collect()
    return result


def write_outputs(results: list[dict], out_dir: Path) -> None:
    jsonl_path = out_dir / "peaks_exact.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for result in results:
            fh.write(json.dumps(result, sort_keys=True) + "\n")

    csv_fields = [
        "challenge",
        "difficulty",
        "qubits",
        "path",
        "peak_bitstring",
        "peak_probability",
        "second_bitstring",
        "second_probability",
        "gap_to_second",
        "norm",
        "elapsed_seconds",
        "maxrss_kb",
    ]
    with (out_dir / "peaks_exact.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=csv_fields)
        writer.writeheader()
        for result in results:
            writer.writerow({field: result.get(field) for field in csv_fields})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-qubits", type=int, default=28)
    parser.add_argument("--topk", type=int, default=8)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "agent_work" / "exact_baseline")
    parser.add_argument("--chunk-elems", type=int, default=int(os.environ.get("SV_CHUNK_ELEMS", 1 << 20)))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    qasm_paths = sorted((ROOT / "challenges").glob("*/*.qasm"), key=lambda p: (qreg_size(p), str(p)))
    targets = [path for path in qasm_paths if qreg_size(path) <= args.max_qubits]

    print(f"Statevector exact targets: {len(targets)} circuits <= {args.max_qubits} qubits", flush=True)
    results: list[dict] = []
    failures: list[dict] = []
    for path in targets:
        rel = path.relative_to(ROOT)
        print(f"[start] {rel}", flush=True)
        try:
            result = simulate_one(path, args.topk, args.chunk_elems)
        except Exception as exc:  # Keep later circuits from being skipped.
            failure = {
                "path": str(rel),
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }
            failures.append(failure)
            print(f"[fail] {rel}: {exc!r}", flush=True)
            continue

        results.append(result)
        write_outputs(results, args.output_dir)
        print(
            f"[done] {rel} peak={result['peak_bitstring']} "
            f"p={result['peak_probability']:.12g} elapsed={result['elapsed_seconds']:.1f}s",
            flush=True,
        )

    if failures:
        (args.output_dir / "peaks_exact_failures.json").write_text(
            json.dumps(failures, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Completed with {len(failures)} failures", file=sys.stderr, flush=True)
        return 1

    print(f"Wrote {len(results)} exact peak results to {args.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
