#!/usr/bin/env python3
"""
Run the temporal global MPO pipeline.

This is the first end-to-end temporal-only executable:

1. validated temporal center selection,
2. full global MPO compression at that center,
3. MPS conversion,
4. peak-candidate extraction.

It does not perform spatial rewiring design or spacetime blocking.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
PEAKED_SIM = ROOT / "peaked-circuit-simulation"
if str(PEAKED_SIM) not in sys.path:
    sys.path.insert(0, str(PEAKED_SIM))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    level=logging.INFO,
)


def _tests() -> dict[str, callable]:
    from test_circuits import (
        make_clean_mirror,
        make_dense_random,
        make_masked_toy_inverse,
        make_shifted_mirror,
        make_swapped_mirror,
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


def _backend(name: str):
    if name not in {"auto", "cpu", "cuda"}:
        raise ValueError(f"unknown backend: {name}")
    if name in {"auto", "cuda"}:
        try:
            import torch
            if torch.cuda.is_available():
                from utils import to_backend_cuda
                return to_backend_cuda
        except Exception:
            if name == "cuda":
                raise
    return None


def run_one(qc_raw, label: str, params, args, to_backend=None) -> dict:
    from temporal_global_executor import (
        run_temporal_global_mpo,
        temporal_global_result_to_dict,
    )

    result = run_temporal_global_mpo(
        qc_raw,
        label,
        params,
        top_k=args.top_k,
        center=args.center,
        run_trial_unswap=args.run_trial_unswap,
        run_global_unswap=args.run_global_unswap,
        max_global_unswap_its=args.max_global_unswap_its,
        early_stopping_gates=args.early_stopping_gates,
        global_hows=tuple(args.global_hows),
        global_equal=args.global_equal,
        flip_freq=args.flip_freq,
        sabre_trials=args.sabre_trials,
        executor_mode=args.executor_mode,
        peak_num_samples=args.peak_num_samples,
        peak_sample_top_k=args.peak_sample_top_k,
        peak_sample_max_distance=args.peak_sample_max_distance,
        refine_bitflips=not args.disable_bitflip_refinement,
        bitflip_rounds=args.bitflip_rounds,
        min_bitflip_improvement=args.min_bitflip_improvement,
        peak_optimize=args.peak_optimize,
        to_backend=to_backend,
        exact_validate=args.exact_validate,
        max_exact_qubits=args.max_exact_qubits,
    )
    payload = temporal_global_result_to_dict(
        result,
        include_stats=not args.no_stats,
        include_validation_stats=not args.no_validation_stats,
    )
    payload["parameters"] = {
        "top_k": args.top_k,
        "trial_absorb_layers": params.trial_absorb_layers,
        "trial_absorb_mode": params.trial_absorb_mode,
        "trial_absorb_policy": params.trial_absorb_policy,
        "run_trial_unswap": args.run_trial_unswap,
        "trial_unswap_trigger": params.trial_unswap_trigger,
        "trial_unswap_threshold_elems": params.trial_unswap_threshold_elems,
        "executor_mode": args.executor_mode,
        "run_global_unswap": args.run_global_unswap,
        "global_unswap_threshold": params.unswap_threshold,
        "max_global_unswap_its": args.max_global_unswap_its,
        "early_stopping_gates": args.early_stopping_gates,
        "max_bond": params.max_bond,
        "cutoff_final": params.cutoff_final,
        "peak_num_samples": args.peak_num_samples,
        "peak_sample_top_k": args.peak_sample_top_k,
        "bitflip_refinement": not args.disable_bitflip_refinement,
        "bitflip_rounds": args.bitflip_rounds,
        "min_bitflip_improvement": args.min_bitflip_improvement,
        "seed": params.seed,
    }

    out_path = args.output_dir / f"{label}.json"
    _write_json(out_path, payload)

    print("\n" + "=" * 72)
    print(f"Temporal global MPO pipeline: {label}")
    print("=" * 72)
    print(f"qubits={payload['n_qubits']} gates={payload['n_gates']} layers={payload['n_layers']}")
    print(f"center layer/instruction: {payload['center_layer']} / {payload['center_instruction']}")
    print(f"raw site bits          : {payload['raw_site_bitstring']}")
    print(f"original-order bits   : {payload['bitstring_original_order']}")
    print(f"probability estimate  : {payload['extracted_probability_estimate']}")
    if payload.get("peak_extraction"):
        print(
            "marginal bits         : "
            f"{payload['peak_extraction']['marginal_original_order']}"
        )
        print(
            "prob evals            : "
            f"{payload['peak_extraction']['n_probability_evaluations']}"
        )
    print(f"mps max bond          : {payload['mps_max_bond']}")
    if payload["exact_peak_bitstring"] is not None:
        print(f"exact peak            : {payload['exact_peak_bitstring']} p={payload['exact_peak_probability']}")
        print(f"exact match           : {payload['exact_match']}")
    print(f"risk flags            : {', '.join(payload['risk_flags'])}")
    print(f"saved                 : {out_path}")
    return payload


def main() -> None:
    tests = _tests()
    parser = argparse.ArgumentParser(description="Temporal global MPO pipeline")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--test", choices=list(tests))
    src.add_argument("--all-tests", action="store_true")
    src.add_argument("--qasm", type=Path)

    parser.add_argument("--center", type=int, default=None,
                        help="Force a layer center. If omitted, validate top proxy centers.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--trial-absorb-layers", type=int, default=8)
    parser.add_argument("--trial-absorb-mode", choices=["per_side", "total"],
                        default="per_side")
    parser.add_argument("--trial-absorb-policy", choices=["greedy", "symmetric"],
                        default="greedy")
    parser.add_argument("--run-trial-unswap", action="store_true",
                        help="Enable limited unswap during center validation.")
    parser.add_argument("--max-trial-unswap-its", type=int, default=2)
    parser.add_argument("--trial-unswap-trigger", choices=["threshold", "final", "never"],
                        default="threshold")
    parser.add_argument("--trial-unswap-threshold-elems", type=int, default=1_000_000)
    parser.add_argument("--executor-mode", choices=["no_rewire", "explicit_rewire", "existing_unswap"],
                        default="no_rewire",
                        help="Use no_rewire baseline, explicit_rewire for transparent unswap+rewire, or existing_unswap for old executor comparison.")
    parser.add_argument("--run-global-unswap", action="store_true",
                        help="Enable threshold unswapping in executor modes that support it.")
    parser.add_argument("--disable-global-unswap", dest="run_global_unswap",
                        action="store_false",
                        help="Compatibility flag; global unswapping is off by default.")
    parser.add_argument("--global-unswap-threshold", type=float, default=1e6)
    parser.add_argument("--max-global-unswap-its", type=int, default=20)
    parser.add_argument("--global-hows", nargs="+", choices=["both", "left", "right"],
                        default=["both", "left", "right"])
    parser.add_argument("--global-equal", action="store_true")
    parser.add_argument("--flip-freq", type=int, default=None)
    parser.add_argument("--early-stopping-gates", type=int, default=100)
    parser.add_argument("--sabre-trials", type=int, default=10000)
    parser.add_argument("--max-bond", type=int, default=8192)
    parser.add_argument("--cutoff-window", type=float, default=1e-5)
    parser.add_argument("--cutoff-final", type=float, default=1e-3)
    parser.add_argument("--mpo-cost-eta", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--backend", choices=["auto", "cpu", "cuda"], default="cpu")
    parser.add_argument("--peak-num-samples", type=int, default=0,
                        help="Optional MPS samples to add as peak candidates.")
    parser.add_argument("--peak-sample-top-k", type=int, default=32,
                        help="Number of most common sampled strings to rescore.")
    parser.add_argument("--peak-sample-max-distance", type=int, default=0)
    parser.add_argument("--disable-bitflip-refinement", action="store_true",
                        help="Disable greedy one-bit-flip probability refinement.")
    parser.add_argument("--bitflip-rounds", type=int, default=2,
                        help="Maximum greedy single-bit-flip improvement rounds.")
    parser.add_argument("--min-bitflip-improvement", type=float, default=0.0,
                        help="Minimum MPS-probability gain required to accept a flip.")
    parser.add_argument("--peak-optimize", default="auto-hq",
                        help="Contraction optimizer for candidate probability checks.")
    parser.add_argument("--exact-validate", action="store_true",
                        help="For baby cases, compute exact peak and compare.")
    parser.add_argument("--max-exact-qubits", type=int, default=10)
    parser.add_argument("--no-stats", action="store_true")
    parser.add_argument("--no-validation-stats", action="store_true")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "outputs" / "temporal_global_pipeline")
    args = parser.parse_args()

    from params import SpacetimeParams
    params = SpacetimeParams(
        score_mode="real",
        trial_absorb_layers=args.trial_absorb_layers,
        trial_absorb_mode=args.trial_absorb_mode,
        trial_absorb_policy=args.trial_absorb_policy,
        run_trial_unswap=args.run_trial_unswap,
        max_trial_unswap_its=args.max_trial_unswap_its,
        trial_unswap_trigger=args.trial_unswap_trigger,
        trial_unswap_threshold_elems=args.trial_unswap_threshold_elems,
        max_bond=args.max_bond,
        cutoff_window=args.cutoff_window,
        cutoff_final=args.cutoff_final,
        unswap_threshold=args.global_unswap_threshold,
        mpo_cost_eta=args.mpo_cost_eta,
        seed=args.seed,
    )

    to_backend = _backend(args.backend)
    if args.all_tests:
        for name, factory in tests.items():
            run_one(factory(), f"test_{name}", params, args, to_backend=to_backend)
        return

    if args.test:
        run_one(tests[args.test](), f"test_{args.test}", params, args, to_backend=to_backend)
        return

    from circuit_tools import load_circuit
    qc = load_circuit(args.qasm)
    run_one(qc, args.qasm.stem, params, args, to_backend=to_backend)


if __name__ == "__main__":
    main()
