#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import time
import traceback
from pathlib import Path

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit.transpiler.exceptions import CircuitTooWideForTarget


def load_config(config_file: Path, task_id: int) -> dict:
    with config_file.open() as f:
        for index, line in enumerate(f, start=1):
            if index == task_id:
                return json.loads(line)
    raise IndexError(f"task id {task_id} not found in {config_file}")


def count_ops(qc: QuantumCircuit) -> dict[str, int]:
    return {name: int(count) for name, count in qc.count_ops().items()}


def sort_counts(counts: dict[str, int]) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def result_path(out_dir: Path, cfg: dict) -> Path:
    circuit_name = Path(cfg["circuit"]).stem
    label = cfg.get("label", "mps")
    filename = (
        f"{label}__task-{int(cfg['task_id']):04d}__{circuit_name}"
        f"__shots-{int(cfg['shots'])}__bd-{int(cfg['bond_dim'])}"
        f"__seed-{int(cfg['seed'])}.json"
    )
    return out_dir / filename


def run_trial(cfg: dict, max_top_counts: int) -> dict:
    started = time.time()
    circuit_path = Path(cfg["circuit"])
    shots = int(cfg["shots"])
    bond_dim = int(cfg["bond_dim"])
    seed = int(cfg["seed"])
    truncation_threshold = float(cfg.get("truncation_threshold", 1e-12))
    cpus = int(os.environ.get("SLURM_CPUS_PER_TASK", "1") or "1")

    t0 = time.time()
    qc_original = QuantumCircuit.from_qasm_file(str(circuit_path))
    qasm_load_seconds = time.time() - t0

    qc_sample = qc_original.remove_final_measurements(inplace=False)
    qc_sample.measure_all()

    simulator = AerSimulator(
        method="matrix_product_state",
        matrix_product_state_max_bond_dimension=bond_dim,
        matrix_product_state_truncation_threshold=truncation_threshold,
        seed_simulator=seed,
        max_parallel_threads=cpus,
        max_parallel_experiments=1,
    )

    t0 = time.time()
    transpile_status = "ok"
    transpile_error = None
    try:
        qc_executable = transpile(
            qc_sample, simulator, seed_transpiler=seed, optimization_level=1
        )
    except CircuitTooWideForTarget as exc:
        # AerSimulator's transpiler target can report a 63-qubit width even
        # when direct simulation of the supported gates is still valid.
        qc_executable = qc_sample
        transpile_status = "skipped_circuit_too_wide_for_target"
        transpile_error = repr(exc)
    transpile_seconds = time.time() - t0

    t0 = time.time()
    job = simulator.run(qc_executable, shots=shots)
    result = job.result()
    run_seconds = time.time() - t0

    counts = result.get_counts()
    ranked = sort_counts(counts)
    top_counts = ranked if max_top_counts <= 0 else ranked[:max_top_counts]
    top_bitstring, top_count = ranked[0]

    return {
        "status": "ok",
        "config": cfg,
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "qiskit_count_order": "left-most bit is highest qubit; right-most bit is q0",
        "circuit_metadata": {
            "num_qubits": qc_original.num_qubits,
            "num_clbits_original": qc_original.num_clbits,
            "depth_original": qc_original.depth(),
            "ops_original": count_ops(qc_original),
            "depth_sampled": qc_sample.depth(),
            "ops_sampled": count_ops(qc_sample),
            "depth_executable": qc_executable.depth(),
            "ops_executable": count_ops(qc_executable),
            "transpile_status": transpile_status,
            "transpile_error": transpile_error,
        },
        "timing_seconds": {
            "qasm_load": qasm_load_seconds,
            "transpile": transpile_seconds,
            "run": run_seconds,
            "total": time.time() - started,
        },
        "sampling": {
            "shots": shots,
            "distinct_outcomes": len(counts),
            "top_bitstring": top_bitstring,
            "top_count": int(top_count),
            "top_probability": top_count / shots,
            "top_counts": [[bitstring, int(count)] for bitstring, count in top_counts],
            "top_counts_truncated": max_top_counts > 0 and len(ranked) > max_top_counts,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Qiskit Aer MPS sampling trial.")
    parser.add_argument(
        "--config-file",
        default="agent_work/mps_distill/configs/pilot_easy_hard.jsonl",
        help="JSONL config file.",
    )
    parser.add_argument(
        "--task-id",
        type=int,
        default=int(os.environ.get("SLURM_ARRAY_TASK_ID", "1")),
        help="1-indexed JSONL line number to run.",
    )
    parser.add_argument(
        "--out-dir",
        default="agent_work/mps_distill/results",
        help="Directory for result JSON files.",
    )
    parser.add_argument(
        "--max-top-counts",
        type=int,
        default=200,
        help="Store this many ranked outcomes; use 0 for all counts.",
    )
    args = parser.parse_args()

    config_file = Path(args.config_file)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = load_config(config_file, args.task_id)
    out_path = result_path(out_dir, cfg)
    tmp_path = out_path.with_suffix(".tmp")

    try:
        payload = run_trial(cfg, args.max_top_counts)
    except Exception as exc:
        payload = {
            "status": "failed",
            "config": cfg,
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "error": repr(exc),
            "traceback": traceback.format_exc(),
        }
        with tmp_path.open("w") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
        tmp_path.replace(out_path)
        raise

    with tmp_path.open("w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    tmp_path.replace(out_path)

    top = payload["sampling"]["top_bitstring"]
    prob = payload["sampling"]["top_probability"]
    elapsed = payload["timing_seconds"]["total"]
    print(f"wrote {out_path}")
    print(f"top={top} p_hat={prob:.6f} elapsed={elapsed:.2f}s")


if __name__ == "__main__":
    main()
