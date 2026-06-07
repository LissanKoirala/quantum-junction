#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "peaked-circuit-simulation"))

# Cotengra's default "auto" path search tries to create a process pool on
# macOS, which is blocked in this sandbox. Threads keep the same algorithmic
# path but avoid OS semaphore creation.
os.environ.setdefault("COTENGRA_NUM_WORKERS", "1")
try:
    import cotengra.parallel as cotengra_parallel

    cotengra_parallel._DEFAULT_BACKEND = "threads"
except Exception:
    pass

from utils import contract_core, iter_layers, sample_tns, tno_to_tne  # noqa: E402


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


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
    order = np.argsort(margins).tolist()
    return {
        "raw_q0_order": "".join(bits),
        "qiskit_order": "".join(reversed(bits)),
        "margin_min": float(min(margins)),
        "margin_mean": float(np.mean(margins)),
        "margin_max": float(max(margins)),
        "weakest_sites_raw_q0_order": [
            {"site": int(i), "p0": float(p0s[i]), "margin": float(margins[i])}
            for i in order[:12]
        ],
        "p0s_raw_q0_order": p0s,
    }


def sample_candidate(tne, samples: int) -> dict:
    if samples <= 0:
        return {"status": "skipped"}
    from collections import Counter

    try:
        draws = sample_tns(tne, samples, max_distance=0, optimize="greedy")
        qiskit_draws = ["".join(reversed(bits)) for bits in draws]
        counts = Counter(qiskit_draws)
        total = sum(counts.values())
        return {
            "status": "ok",
            "samples": total,
            "top": [
                {"bitstring": bits, "count": count, "fraction": count / total}
                for bits, count in counts.most_common(10)
            ],
        }
    except Exception as exc:
        return {"status": "error", "error_type": type(exc).__name__, "error": repr(exc)}


def run_setting(qasm: Path, layers, setting: dict, samples: int) -> dict:
    row = dict(setting)
    started = time.time()
    try:
        tno, stats = contract_core(
            layers,
            chunk_size=setting["chunk"],
            method=setting["method"],
            max_bond=setting["max_bond"],
            cutoff=setting["cutoff"],
            equalize_norms=True,
            to_backend=None,
        )
        row["contract_seconds"] = time.time() - started
        row["contract_rss_mb"] = rss_mb()
        row["contract_stats_last"] = stats[-1] if stats else None
        row["contract_stats_len"] = len(stats)

        tne_started = time.time()
        tne = tno_to_tne(
            tno,
            max_bond=setting["state_max_bond"],
            cutoff=setting["state_cutoff"],
            to_backend=None,
        )
        row["tne_seconds"] = time.time() - tne_started
        row["tne_rss_mb"] = rss_mb()
        row["candidate"] = extract_candidate(tne)
        row["sampling"] = sample_candidate(tne, samples)
        row["status"] = "ok"
    except Exception as exc:
        import traceback

        row.update(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "error": repr(exc),
                "traceback_tail": traceback.format_exc()[-1600:],
                "seconds": time.time() - started,
                "rss_mb": rss_mb(),
            }
        )
    row["qasm"] = str(qasm)
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--qasm",
        type=Path,
        default=ROOT / "challenges" / "hard" / "challenge-64_40.qasm",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "tno_64_40" / "challenge-64_40.tno.jsonl",
    )
    parser.add_argument("--samples", type=int, default=0)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    qc = QuantumCircuit.from_qasm_file(str(args.qasm)).remove_final_measurements(inplace=False)
    layers = list(iter_layers(qc))
    header = {
        "event": "start",
        "qasm": str(args.qasm),
        "num_qubits": qc.num_qubits,
        "ops": len(qc),
        "op_counts": dict(qc.count_ops()),
        "layers": len(layers),
        "rss_mb": rss_mb(),
    }
    print(json.dumps(header), flush=True)
    with args.out.open("a") as f:
        f.write(json.dumps(header, sort_keys=True) + "\n")

    settings = [
        {"max_bond": 4, "cutoff": 0.25, "chunk": 16, "state_max_bond": 4, "state_cutoff": 0.25, "method": "local-late"},
        {"max_bond": 8, "cutoff": 0.20, "chunk": 12, "state_max_bond": 8, "state_cutoff": 0.20, "method": "local-late"},
        {"max_bond": 8, "cutoff": 0.15, "chunk": 10, "state_max_bond": 8, "state_cutoff": 0.15, "method": "local-late"},
        {"max_bond": 16, "cutoff": 0.12, "chunk": 8, "state_max_bond": 12, "state_cutoff": 0.12, "method": "local-late"},
    ]

    for setting in settings:
        print("RUN " + json.dumps(setting), flush=True)
        row = run_setting(args.qasm, layers, setting, args.samples)
        print("RESULT " + json.dumps({k: row.get(k) for k in ["status", "max_bond", "cutoff", "chunk", "candidate"]}), flush=True)
        with args.out.open("a") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
