#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import resource
import time
from pathlib import Path

import numpy as np
import quimb.tensor as qtn
import quimb.tensor.decomp as qdecomp
from qiskit import QuantumCircuit
from qiskit_quimb import quimb_circuit


ROOT = Path(__file__).resolve().parents[1]


def patch_quimb_swap_back_kwarg() -> None:
    for name, fn in list(qdecomp._SPLIT_FNS.items()):
        if getattr(fn, "_qj_swap_back_patched", False):
            continue

        def wrapped(x, _fn=fn, **kwargs):
            kwargs.pop("swap_back", None)
            return _fn(x, **kwargs)

        wrapped._qj_swap_back_patched = True
        qdecomp._SPLIT_FNS[name] = wrapped


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def parse_setting(text: str) -> tuple[int, float]:
    parts = text.split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("settings must be max_bond,cutoff")
    return int(parts[0]), float(parts[1])


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def run_setting(qc: QuantumCircuit, max_bond: int, cutoff: float, seed: int, samples: int) -> dict:
    start = time.perf_counter()
    circ = quimb_circuit(
        qc,
        quimb_circuit_class=qtn.CircuitPermMPS,
        max_bond=max_bond,
        cutoff=cutoff,
        gate_contract="auto-mps",
        dtype="complex128",
    )
    pi1 = np.array([[0.0, 0.0], [0.0, 1.0]], dtype=np.complex128)
    p1s = [0.0] * qc.num_qubits
    site_to_logical = list(getattr(circ, "qubits", range(qc.num_qubits)))
    for site, logical in enumerate(site_to_logical):
        val = circ.local_expectation(pi1, site, normalized=True)
        p1s[int(logical)] = float(np.real(np.asarray(val)).item())

    logical_q0_first = "".join("1" if p >= 0.5 else "0" for p in p1s)
    qiskit_order = logical_q0_first[::-1]
    margins = [abs(p - 0.5) for p in p1s]

    out = {
        "event": "candidate",
        "max_bond": max_bond,
        "cutoff": cutoff,
        "candidate_logical_q0_first": logical_q0_first,
        "candidate_qiskit_order": qiskit_order,
        "p1_logical_q0_first": p1s,
        "site_to_logical": site_to_logical,
        "margin_min": float(min(margins)),
        "margin_mean": float(np.mean(margins)),
        "margin_max": float(max(margins)),
        "fidelity_estimate": None,
        "error_estimate": None,
        "seconds": time.perf_counter() - start,
        "max_rss_mb": rss_mb(),
    }
    try:
        out["fidelity_estimate"] = float(circ.fidelity_estimate())
        out["error_estimate"] = float(circ.error_estimate())
    except Exception as exc:  # noqa: BLE001
        out["fidelity_error"] = repr(exc)

    if samples > 0:
        counts: dict[str, int] = {}
        for sample in circ.sample(samples, seed=seed):
            bits = sample if isinstance(sample, str) else "".join(str(int(b)) for b in sample)
            logical_bits = ["0"] * qc.num_qubits
            for site, bit in enumerate(bits):
                logical_bits[int(site_to_logical[site])] = bit
            qiskit_bits = "".join(logical_bits[::-1])
            counts[qiskit_bits] = counts.get(qiskit_bits, 0) + 1
        top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20]
        out["sample_top_qiskit_order"] = [{"bitstring": bitstring, "count": count} for bitstring, count in top]
    return out


def main() -> int:
    patch_quimb_swap_back_kwarg()
    parser = argparse.ArgumentParser()
    parser.add_argument("--qasm", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "solve_64_41" / "perm_mps_marginals.jsonl")
    parser.add_argument("--setting", action="append", type=parse_setting)
    parser.add_argument("--seed", type=int, default=20260607)
    parser.add_argument("--samples", type=int, default=0)
    args = parser.parse_args()

    qasm = args.qasm if args.qasm.is_absolute() else ROOT / args.qasm
    qc = QuantumCircuit.from_qasm_file(str(qasm)).remove_final_measurements(inplace=False)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    settings = args.setting or [(32, 1e-5), (64, 1e-6)]
    header = {
        "event": "start",
        "qasm": str(qasm),
        "qubits": qc.num_qubits,
        "ops": len(qc),
        "settings": settings,
    }
    print(json.dumps(json_safe(header), sort_keys=True), flush=True)
    with args.out.open("a") as f:
        f.write(json.dumps(json_safe(header), sort_keys=True) + "\n")

    for max_bond, cutoff in settings:
        try:
            result = run_setting(qc, max_bond=max_bond, cutoff=cutoff, seed=args.seed, samples=args.samples)
        except Exception as exc:  # noqa: BLE001
            import traceback

            result = {
                "event": "error",
                "max_bond": max_bond,
                "cutoff": cutoff,
                "error_type": type(exc).__name__,
                "error": repr(exc),
                "traceback_tail": traceback.format_exc()[-1600:],
                "max_rss_mb": rss_mb(),
            }
        print(json.dumps(json_safe(result), sort_keys=True), flush=True)
        with args.out.open("a") as f:
            f.write(json.dumps(json_safe(result), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
