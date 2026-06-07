#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
import time
from typing import Any

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[2]
HELPER = ROOT / "agent_work" / "checkpoint_unswap_48_42.py"
PEAKED_SIM = ROOT / "peaked-circuit-simulation"
if str(PEAKED_SIM) not in sys.path:
    sys.path.insert(0, str(PEAKED_SIM))


def load_helper() -> Any:
    spec = importlib.util.spec_from_file_location("checkpoint_unswap_48_42_mod", HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper from {HELPER}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def json_safe(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [json_safe(v) for v in x]
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    return repr(x)


def all_variants(raw_bits: str, perm: list[int]) -> dict[str, str]:
    out = {
        "raw_site_order": raw_bits,
        "raw_site_order_reversed": raw_bits[::-1],
    }
    if len(perm) == len(raw_bits):
        permuted = "".join(raw_bits[i] for i in perm)
        inv = [0] * len(perm)
        for i, p in enumerate(perm):
            inv[p] = i
        inv_permuted = "".join(raw_bits[i] for i in inv)
        out.update(
            {
                "permuted_measurement_order": permuted,
                "permuted_measurement_order_reversed_qiskit": permuted[::-1],
                "inverse_permuted_order": inv_permuted,
                "inverse_permuted_order_reversed": inv_permuted[::-1],
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-dir", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--max-bond", type=int, default=32)
    parser.add_argument("--cutoff", type=float, default=0.01)
    parser.add_argument("--progress-every", type=int, default=100)
    parser.add_argument("--sample-count", type=int, default=0)
    args = parser.parse_args()

    mod = load_helper()
    from qiskit import QuantumCircuit
    from qiskit_quimb import quimb_circuit
    from quimb.tensor import Circuit, CircuitMPS
    import circuit_mpo

    q2c = lambda qc: quimb_circuit(qc.decompose("unitary"), Circuit, to_backend=None)
    state = mod.load_checkpoint((ROOT / args.checkpoint_dir).resolve())
    if state is None:
        raise RuntimeError(f"no checkpoint in {args.checkpoint_dir}")

    nq = state["num_qubits"]
    started = time.perf_counter()
    left_remaining = state["layers_left"][state["ii_left"] :] if state["ii_left"] < len(state["layers_left"]) else []
    right_remaining = state["layers_right"][state["ii_right"] :] if state["ii_right"] < len(state["layers_right"]) else []
    left_unitary = [layer for layer in left_remaining if not mod.is_nonunitary_layer(layer)]
    right_unitary = [layer for layer in right_remaining if not mod.is_nonunitary_layer(layer)]
    final_meas = [layer for layer in right_remaining + state["final_meas"] if mod.is_nonunitary_layer(layer)]
    perm = mod.final_perm_from_measure_layers(final_meas, nq)

    mps = quimb_circuit(QuantumCircuit(nq), quimb_circuit_class=CircuitMPS, to_backend=None).psi
    print(
        "start",
        {
            "checkpoint": str(args.checkpoint_dir),
            "left_unitary": len(left_unitary),
            "right_unitary": len(right_unitary),
            "mpo_info": mod.tn_info(state["mpo_core"]),
            "max_bond": args.max_bond,
            "cutoff": args.cutoff,
        },
        flush=True,
    )

    for offset, layer in enumerate(reversed(left_unitary), 1):
        layer_mpo = circuit_mpo.mpo_from_circuit(q2c(layer.inverse()))
        mps = layer_mpo.apply(mps, compress=True, max_bond=args.max_bond, cutoff=args.cutoff)
        if offset % args.progress_every == 0 or offset == len(left_unitary):
            print("left", offset, len(left_unitary), mod.tn_info(mps), flush=True)

    mps = state["mpo_core"].apply(mps, compress=True, max_bond=args.max_bond, cutoff=args.cutoff)
    print("core", mod.tn_info(mps), flush=True)

    for offset, layer in enumerate(right_unitary, 1):
        layer_mpo = circuit_mpo.mpo_from_circuit(q2c(layer))
        mps = layer_mpo.apply(mps, compress=True, max_bond=args.max_bond, cutoff=args.cutoff)
        if offset % args.progress_every == 0 or offset == len(right_unitary):
            print("right", offset, len(right_unitary), mod.tn_info(mps), flush=True)

    raw, p0s = mod.extract_marginal_bitstring(mps)
    variants = all_variants(raw, perm)
    p1_margins = [abs((1.0 - p0) - 0.5) for p0 in p0s]
    result = {
        "status": "ok",
        "checkpoint_dir": str(args.checkpoint_dir),
        "source_total_u_consumed": state.get("total_u_consumed"),
        "source_cycles": state.get("cycles"),
        "left_unitary_layers": len(left_unitary),
        "right_unitary_layers": len(right_unitary),
        "max_bond": args.max_bond,
        "cutoff": args.cutoff,
        "final_perm": perm,
        "raw_site_order": raw,
        "variants": variants,
        "final_candidate_qiskit_order": variants.get("permuted_measurement_order_reversed_qiskit"),
        "p0s_raw_site_order": p0s,
        "p1_margin_min": min(p1_margins),
        "p1_margin_mean": float(np.mean(p1_margins)),
        "p1_margin_max": max(p1_margins),
        "mps_info": mod.tn_info(mps),
        "elapsed_seconds": time.perf_counter() - started,
    }
    if args.sample_count > 0:
        result["sampling"] = mod.sample_mps(mps, args.sample_count, perm)

    out = (ROOT / args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(json_safe(result), indent=2, sort_keys=True) + "\n")
    print("wrote", out, "candidate", result["final_candidate_qiskit_order"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
