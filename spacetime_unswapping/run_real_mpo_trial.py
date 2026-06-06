#!/usr/bin/env python3
"""
Real partial MPO trial scorer for temporal center validation.

This script is Step 2 of the pipeline:

1. load/generate a circuit,
2. remove measurements,
3. layerize,
4. optionally use proxy center scan to select top-k candidate centers,
5. run real partial MPO absorption at those centers,
6. write JSON telemetry.

It does not recover a bitstring.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


def _tests() -> dict[str, callable]:
    from test_circuits import (
        make_clean_mirror,
        make_shifted_mirror,
        make_swapped_mirror,
        make_masked_toy_inverse,
        make_dense_random,
    )
    return {
        "clean_mirror": lambda: make_clean_mirror(4, 3),
        "shifted_mirror": lambda: make_shifted_mirror(4, 3, 1),
        "swapped_mirror": lambda: make_swapped_mirror(4, 3),
        "masked_inverse": lambda: make_masked_toy_inverse(4, 3, 0.3),
        "dense_random": lambda: make_dense_random(4, 4),
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def run_one(qc_raw, label: str, params, args) -> dict:
    from circuit_tools import remove_measurements, count_two_qubit_gates
    from layer_tools import greedy_layerize
    from temporal_validation import (
        validate_temporal_centers,
        validated_temporal_plan_to_dict,
    )

    t0 = time.perf_counter()
    qc_clean = remove_measurements(qc_raw)
    layers = greedy_layerize(qc_clean)
    centers = [args.center] if args.center is not None else None
    validated = validate_temporal_centers(
        qc_clean,
        params,
        top_k=args.top_k,
        centers=centers,
        trial_absorb_layers=args.trial_absorb_layers,
        absorb_policy=args.absorb_policy,
        run_unswap=args.run_unswap,
        use_rewire=args.use_rewire,
    )
    validated_dict = validated_temporal_plan_to_dict(
        validated,
        include_stats=not args.no_stats,
    )

    payload = {
        "label": label,
        "mode": "validated_real_partial_mpo_trial",
        "warning": "Partial center validation only; no bitstring recovery.",
        "n_qubits": qc_clean.num_qubits,
        "n_layers": len(layers),
        "n_two_qubit_gates": count_two_qubit_gates(qc_clean),
        "candidate_centers": validated.candidate_centers,
        "trial_absorb_layers": args.trial_absorb_layers,
        "trial_absorb_mode": params.trial_absorb_mode,
        "absorb_policy": args.absorb_policy,
        "run_unswap": args.run_unswap,
        "trial_unswap_trigger": params.trial_unswap_trigger,
        "trial_unswap_threshold_elems": params.trial_unswap_threshold_elems,
        "trial_unswap_hows": list(params.trial_unswap_hows),
        "use_rewire": args.use_rewire,
        "best_center": validated.best_center,
        "best_score": validated_dict["best_score"],
        "validated_temporal_plan": validated_dict,
        "wall_seconds": round(time.perf_counter() - t0, 3),
    }

    out_path = args.output_dir / f"{label}.json"
    _write_json(out_path, payload)

    print("\n" + "=" * 72)
    print(f"Real partial MPO trial: {label}")
    print("=" * 72)
    print(f"qubits={qc_clean.num_qubits} layers={len(layers)} centers={validated.candidate_centers}")
    if validated.best_score:
        s = validated_dict["best_score"]
        print(f"best center : {validated.best_center}")
        print(f"cost        : {s['cost']:.6f}")
        print(f"max bond    : {s['max_bond_dim']}")
        print(f"sum log bond: {s['sum_log_bond_dim']}")
        print(f"size        : {s['size']}")
        print(f"risk flags  : {', '.join(s['risk_flags'])}")
    print(f"saved       : {out_path}")

    return payload


def main() -> None:
    tests = _tests()
    parser = argparse.ArgumentParser(description="Real partial MPO center trials")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--test", choices=list(tests))
    src.add_argument("--all-tests", action="store_true")
    src.add_argument("--qasm", type=Path)

    parser.add_argument("--center", type=int, default=None,
                        help="Layer center to trial. If omitted, use top proxy centers.")
    parser.add_argument("--top-k", type=int, default=5,
                        help="Number of proxy-suggested centers to validate.")
    parser.add_argument("--trial-absorb-layers", type=int, default=8)
    parser.add_argument("--trial-absorb-mode", choices=["per_side", "total"],
                        default="per_side")
    parser.add_argument("--absorb-policy", choices=["greedy", "symmetric"],
                        default="greedy")
    parser.add_argument("--run-unswap", action="store_true",
                        help="Run limited trial unswapping during/after absorption.")
    parser.add_argument("--max-trial-unswap-its", type=int, default=2)
    parser.add_argument("--trial-unswap-trigger", choices=["threshold", "final", "never"],
                        default="threshold")
    parser.add_argument("--trial-unswap-threshold-elems", type=int, default=1_000_000)
    parser.add_argument("--trial-unswap-hows", nargs="+",
                        choices=["both", "left", "right"],
                        default=["both", "left", "right"])
    parser.add_argument("--use-rewire", action="store_true",
                        help="Reserved hook. Currently reports not implemented.")
    parser.add_argument("--max-bond", type=int, default=8192)
    parser.add_argument("--cutoff-window", type=float, default=1e-5)
    parser.add_argument("--mpo-cost-eta", type=float, default=0.01)
    parser.add_argument("--no-stats", action="store_true",
                        help="Omit per-step absorption telemetry from JSON.")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "outputs" / "real_mpo_trials")
    args = parser.parse_args()

    from params import SpacetimeParams
    params = SpacetimeParams(
        score_mode="real",
        trial_absorb_layers=args.trial_absorb_layers,
        trial_absorb_mode=args.trial_absorb_mode,
        trial_absorb_policy=args.absorb_policy,
        run_trial_unswap=args.run_unswap,
        max_trial_unswap_its=args.max_trial_unswap_its,
        trial_unswap_trigger=args.trial_unswap_trigger,
        trial_unswap_threshold_elems=args.trial_unswap_threshold_elems,
        trial_unswap_hows=tuple(args.trial_unswap_hows),
        use_trial_rewire=args.use_rewire,
        max_bond=args.max_bond,
        cutoff_window=args.cutoff_window,
        mpo_cost_eta=args.mpo_cost_eta,
    )

    if args.all_tests:
        for name, factory in tests.items():
            run_one(factory(), f"test_{name}", params, args)
        return

    if args.test:
        run_one(tests[args.test](), f"test_{args.test}", params, args)
        return

    from circuit_tools import load_circuit
    qc = load_circuit(args.qasm)
    run_one(qc, args.qasm.stem, params, args)


if __name__ == "__main__":
    main()
