#!/usr/bin/env python3
"""Run exact Aer statevector simulation for small challenge circuits."""

from __future__ import annotations

import argparse
import csv
import gc
import json
import os
import resource
import sys
import time
import traceback
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

from statevector_peaks import ROOT, qreg_size, topk_probabilities


def simulate_one(path: Path, topk: int, chunk_elems: int, threads: int) -> dict:
    rel = path.relative_to(ROOT)
    num_qubits = qreg_size(path)
    started = time.monotonic()

    qc = QuantumCircuit.from_qasm_file(str(path))
    qc_no_meas = qc.remove_final_measurements(inplace=False)
    if qc_no_meas.num_qubits != num_qubits:
        raise ValueError(f"QASM qreg says {num_qubits}, Qiskit loaded {qc_no_meas.num_qubits}")

    qc_no_meas.save_statevector()
    sim = AerSimulator(method="statevector", precision="double", max_parallel_threads=threads)
    result = sim.run(qc_no_meas).result()
    sv = result.get_statevector(qc_no_meas)
    data = np.asarray(sv.data)
    top, norm = topk_probabilities(data, num_qubits, topk, chunk_elems)

    elapsed = time.monotonic() - started
    maxrss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    output = {
        "path": str(rel),
        "difficulty": path.parent.name,
        "challenge": path.stem.replace("challenge-", ""),
        "qubits": num_qubits,
        "gates": len(qc_no_meas.data) - 1,
        "peak_bitstring": top[0]["bitstring"],
        "peak_probability": top[0]["probability"],
        "second_bitstring": top[1]["bitstring"] if len(top) > 1 else None,
        "second_probability": top[1]["probability"] if len(top) > 1 else None,
        "gap_to_second": top[0]["probability"] - top[1]["probability"] if len(top) > 1 else None,
        "norm": norm,
        "top": top,
        "elapsed_seconds": elapsed,
        "maxrss_kb": maxrss_kb,
        "backend": "qiskit-aer-statevector",
    }

    del result, sv, data, qc, qc_no_meas, sim
    gc.collect()
    return output


def write_outputs(results: list[dict], out_dir: Path) -> None:
    with (out_dir / "peaks_exact_aer.jsonl").open("w", encoding="utf-8") as fh:
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
        "backend",
    ]
    with (out_dir / "peaks_exact_aer.csv").open("w", newline="", encoding="utf-8") as fh:
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
    parser.add_argument("--threads", type=int, default=int(os.environ.get("SLURM_CPUS_PER_TASK", "8")))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    qasm_paths = sorted((ROOT / "challenges").glob("*/*.qasm"), key=lambda p: (qreg_size(p), str(p)))
    targets = [path for path in qasm_paths if qreg_size(path) <= args.max_qubits]

    print(f"Aer exact statevector targets: {len(targets)} circuits <= {args.max_qubits} qubits", flush=True)
    results: list[dict] = []
    failures: list[dict] = []
    for path in targets:
        rel = path.relative_to(ROOT)
        print(f"[start] {rel}", flush=True)
        try:
            result = simulate_one(path, args.topk, args.chunk_elems, args.threads)
        except Exception as exc:
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
        (args.output_dir / "peaks_exact_aer_failures.json").write_text(
            json.dumps(failures, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Completed with {len(failures)} failures", file=sys.stderr, flush=True)
        return 1

    print(f"Wrote {len(results)} exact Aer peak results to {args.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
