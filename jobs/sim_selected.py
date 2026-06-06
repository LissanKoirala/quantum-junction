#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import re
import traceback
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from qiskit import QuantumCircuit


ROOT = Path(__file__).resolve().parents[1]
TARGET_IDS = [11, 26, 34, 41, 49]
CHALLENGE_RE = re.compile(r"challenge-(\d+)_(\d+)\.qasm$")


def resolve_challenge(challenge_id: int) -> Path:
    matches = []
    for path in (ROOT / "challenges").glob("*/*.qasm"):
        match = CHALLENGE_RE.match(path.name)
        if match and int(match.group(2)) == challenge_id:
            matches.append(path)
    if len(matches) != 1:
        raise ValueError(f"expected one match for challenge id {challenge_id}, found {matches}")
    return matches[0]


def load_circuit(path: Path) -> QuantumCircuit:
    return QuantumCircuit.from_qasm_file(str(path))


def ensure_dirs(out_dir: Path) -> dict[str, Path]:
    out_dir = out_dir.resolve()
    dirs = {
        "json": out_dir / "json",
        "images": out_dir / "images",
        "statevector_images": out_dir / "images" / "statevector",
        "mps_images": out_dir / "images" / "mps",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def save_bar_image(title: str, values: dict[str, float], out_path: Path, ylabel: str) -> None:
    items = sorted(values.items(), key=lambda kv: kv[1], reverse=True)
    labels = [k for k, _ in items]
    heights = [v for _, v in items]

    plt.figure(figsize=(max(10, min(24, len(labels) * 0.55)), 6))
    plt.bar(range(len(labels)), heights, color="#2f6f9f")
    plt.xticks(range(len(labels)), labels, rotation=75, ha="right", fontsize=8)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close()


def save_text_image(title: str, lines: list[str], out_path: Path) -> None:
    plt.figure(figsize=(11, 4.5))
    plt.axis("off")
    plt.title(title, loc="left", fontsize=14, pad=14)
    plt.text(0.01, 0.82, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=10)
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close()


def statevector_memory_bytes(num_qubits: int) -> int:
    # complex128 amplitude array only. Real simulator overhead is higher.
    return (2**num_qubits) * 16


def gib(num_bytes: int) -> float:
    return num_bytes / (1024**3)


def run_statevector(challenge_id: int, out_dir: Path, max_qubits: int, top_k: int) -> dict:
    from qiskit.quantum_info import Statevector

    dirs = ensure_dirs(out_dir)
    qasm_path = resolve_challenge(challenge_id)
    qc = load_circuit(qasm_path)
    n = qc.num_qubits
    base = f"challenge-{n}_{challenge_id}"
    image_path = dirs["statevector_images"] / f"{base}.png"
    json_path = dirs["json"] / f"{base}.statevector.json"
    mem_bytes = statevector_memory_bytes(n)

    result = {
        "method": "statevector",
        "challenge_id": challenge_id,
        "path": str(qasm_path.relative_to(ROOT)),
        "num_qubits": n,
        "estimated_statevector_gib": gib(mem_bytes),
        "max_qubits": max_qubits,
    }

    if n > max_qubits:
        result.update({
            "status": "skipped",
            "reason": f"statevector requires about {gib(mem_bytes):.3g} GiB for amplitudes only",
            "image": str(image_path.relative_to(ROOT)),
        })
        save_text_image(
            f"Statevector skipped: challenge {challenge_id}",
            [
                f"path: {qasm_path.relative_to(ROOT)}",
                f"qubits: {n}",
                f"raw statevector memory: {gib(mem_bytes):.3g} GiB",
                f"max_qubits setting: {max_qubits}",
                "status: skipped before simulation",
            ],
            image_path,
        )
    else:
        qc_no_meas = qc.remove_final_measurements(inplace=False)
        sv = Statevector.from_instruction(qc_no_meas)
        probs = sv.probabilities_dict()
        peak = max(probs, key=probs.get)
        top = dict(sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[:top_k])
        result.update({
            "status": "ok",
            "peak": peak,
            "peak_probability": probs[peak],
            "top_probabilities": top,
            "image": str(image_path.relative_to(ROOT)),
        })
        save_bar_image(
            f"Statevector top {len(top)} probabilities: challenge {challenge_id}",
            top,
            image_path,
            "probability",
        )

    json_path.write_text(json.dumps(result, indent=2) + "\n")
    return result


def run_mps(
    challenge_id: int,
    out_dir: Path,
    shots: int,
    bond_dim: int,
    seed: int,
    top_k: int,
    max_parallel_threads: int,
) -> dict:
    from qiskit_aer import AerSimulator

    dirs = ensure_dirs(out_dir)
    qasm_path = resolve_challenge(challenge_id)
    qc = load_circuit(qasm_path)
    n = qc.num_qubits
    base = f"challenge-{n}_{challenge_id}"
    image_path = dirs["mps_images"] / f"{base}.png"
    json_path = dirs["json"] / f"{base}.mps.json"

    result = {
        "method": "mps",
        "challenge_id": challenge_id,
        "path": str(qasm_path.relative_to(ROOT)),
        "num_qubits": n,
        "shots": shots,
        "bond_dim": bond_dim,
        "seed": seed,
        "max_parallel_threads": max_parallel_threads,
    }

    try:
        qc_meas = qc.copy()
        if "measure" not in qc_meas.count_ops():
            qc_meas.measure_all()

        sim = AerSimulator(
            method="matrix_product_state",
            matrix_product_state_max_bond_dimension=bond_dim,
            seed_simulator=seed,
            max_parallel_threads=max_parallel_threads,
        )
        # Direct execution avoids Aer transpiler target-size issues seen at 64+ qubits.
        counts = sim.run(qc_meas, shots=shots).result().get_counts()
        peak = max(counts, key=counts.get)
        top_counts = dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:top_k])
        top_probabilities = {k: v / shots for k, v in top_counts.items()}
        result.update({
            "status": "ok",
            "peak": peak,
            "peak_count": counts[peak],
            "peak_probability_estimate": counts[peak] / shots,
            "unique_samples": len(counts),
            "top_counts": top_counts,
            "top_probability_estimates": top_probabilities,
            "image": str(image_path.relative_to(ROOT)),
        })
        save_bar_image(
            f"MPS top {len(top_counts)} counts: challenge {challenge_id} "
            f"(shots={shots}, bond={bond_dim})",
            top_counts,
            image_path,
            "counts",
        )
    except Exception as exc:
        result.update({
            "status": "error",
            "error": repr(exc),
            "traceback": traceback.format_exc(),
            "image": str(image_path.relative_to(ROOT)),
        })
        save_text_image(
            f"MPS error: challenge {challenge_id}",
            [
                f"path: {qasm_path.relative_to(ROOT)}",
                f"qubits: {n}",
                f"shots: {shots}",
                f"bond_dim: {bond_dim}",
                f"error: {repr(exc)}",
            ],
            image_path,
        )

    json_path.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=["statevector", "mps"], required=True)
    parser.add_argument("--ids", nargs="*", type=int, default=TARGET_IDS)
    parser.add_argument("--id", type=int, default=None)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs" / "sim_11_26_34_41_49")
    parser.add_argument("--max-qubits", type=int, default=30)
    parser.add_argument("--shots", type=int, default=int(os.environ.get("MPS_SHOTS", "4096")))
    parser.add_argument("--bond-dim", type=int, default=int(os.environ.get("MPS_BOND_DIM", "64")))
    parser.add_argument("--seed", type=int, default=int(os.environ.get("MPS_SEED", "12345")))
    parser.add_argument("--top-k", type=int, default=25)
    parser.add_argument(
        "--max-parallel-threads",
        type=int,
        default=int(os.environ.get("SLURM_CPUS_PER_TASK", "1")),
    )
    args = parser.parse_args()
    if args.out_dir.is_absolute():
        args.out_dir = args.out_dir.resolve()
    else:
        args.out_dir = (ROOT / args.out_dir).resolve()

    ids = [args.id] if args.id is not None else args.ids
    args.out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for challenge_id in ids:
        if args.method == "statevector":
            result = run_statevector(challenge_id, args.out_dir, args.max_qubits, args.top_k)
        else:
            result = run_mps(
                challenge_id,
                args.out_dir,
                args.shots,
                args.bond_dim,
                args.seed,
                args.top_k,
                args.max_parallel_threads,
            )
        print(json.dumps(result, sort_keys=True), flush=True)
        results.append(result)

    summary_path = args.out_dir / f"{args.method}.summary.jsonl"
    with summary_path.open("a") as f:
        for result in results:
            f.write(json.dumps(result, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
