#!/usr/bin/env python3
"""Run the full first-pass spacetime block MPO pipeline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in [HERE, ROOT / "peaked-circuit-simulation", ROOT / "separator_mpo_attack"]:
    if str(p) not in sys.path:
        sys.path.append(str(p))


def _tests() -> dict[str, callable]:
    from test_circuits import (
        make_clean_mirror,
        make_dense_random,
        make_masked_toy_inverse,
        make_modular_mirror,
        make_shifted_mirror,
        make_swapped_mirror,
    )
    return {
        "clean_mirror": lambda: make_clean_mirror(4, 3),
        "shifted_mirror": lambda: make_shifted_mirror(4, 3, 1),
        "swapped_mirror": lambda: make_swapped_mirror(4, 3),
        "masked_inverse": lambda: make_masked_toy_inverse(4, 3, 0.3),
        "modular_mirror": lambda: make_modular_mirror(2, 2, 2, 1),
        "dense_random": lambda: make_dense_random(4, 4),
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _jsonable_args(args) -> dict:
    out = {}
    for k, v in vars(args).items():
        out[k] = str(v) if isinstance(v, Path) else v
    return out


def run_one(qc, label: str, params, args) -> dict:
    from spacetime_block_executor import (
        run_spacetime_block_mpo,
        spacetime_block_result_to_dict,
    )

    result = run_spacetime_block_mpo(
        qc,
        label,
        params,
        top_k=args.top_k,
        center=args.center,
        window_size=args.window_size,
        executor_mode=args.executor_mode,
        run_global_unswap=args.run_global_unswap,
        max_global_unswap_its=args.max_global_unswap_its,
        early_stopping_gates=args.early_stopping_gates,
        global_hows=tuple(args.global_hows),
        global_equal=args.global_equal,
        sabre_trials=args.sabre_trials,
        peak_num_samples=args.peak_num_samples,
        peak_sample_top_k=args.peak_sample_top_k,
        refine_bitflips=not args.disable_bitflip_refinement,
        bitflip_rounds=args.bitflip_rounds,
        exact_validate=args.exact_validate,
        max_exact_qubits=args.max_exact_qubits,
    )
    data = spacetime_block_result_to_dict(
        result,
        include_stats=not args.no_stats,
        include_validation_stats=not args.no_validation_stats,
    )
    data["parameters"] = _jsonable_args(args) | {
        "max_bond": params.max_bond,
        "cutoff_final": params.cutoff_final,
        "trial_absorb_layers": params.trial_absorb_layers,
    }
    out = args.output_dir / f"{label}.json"
    _write_json(out, data)

    print("\n" + "=" * 72)
    print(f"Spacetime block MPO pipeline: {label}")
    print("=" * 72)
    print(f"qubits={data['n_qubits']} gates={data['n_gates']} layers={data['n_layers']}")
    print(f"center layer      : {data['center_layer']}")
    print(f"partition sizes   : {len(data['partition_A'])} / {len(data['partition_B'])}")
    print(f"boundary gates    : {data['boundary_gate_count']}")
    print(f"bitstring         : {data['bitstring_original_order']}")
    if data["exact_peak_bitstring"] is not None:
        print(f"exact peak        : {data['exact_peak_bitstring']} p={data['exact_peak_probability']}")
        print(f"exact match       : {data['exact_match']}")
    print(f"risk flags        : {', '.join(data['risk_flags'])}")
    print(f"saved             : {out}")
    return data


def main() -> None:
    tests = _tests()
    parser = argparse.ArgumentParser(description="Spacetime block MPO pipeline")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--test", choices=list(tests))
    src.add_argument("--all-tests", action="store_true")
    src.add_argument("--qasm", type=Path)

    parser.add_argument("--center", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--window-size", type=int, default=None)
    parser.add_argument("--trial-absorb-layers", type=int, default=4)
    parser.add_argument("--executor-mode", choices=["no_rewire", "explicit_rewire"], default="no_rewire")
    parser.add_argument("--run-global-unswap", action="store_true")
    parser.add_argument("--global-unswap-threshold", type=float, default=1e6)
    parser.add_argument("--max-global-unswap-its", type=int, default=4)
    parser.add_argument("--global-hows", nargs="+", choices=["both", "left", "right"],
                        default=["both", "left", "right"])
    parser.add_argument("--global-equal", action="store_true")
    parser.add_argument("--early-stopping-gates", type=int, default=100)
    parser.add_argument("--sabre-trials", type=int, default=16)
    parser.add_argument("--max-bond", type=int, default=512)
    parser.add_argument("--cutoff-window", type=float, default=1e-8)
    parser.add_argument("--cutoff-final", type=float, default=1e-8)
    parser.add_argument("--peak-num-samples", type=int, default=0)
    parser.add_argument("--peak-sample-top-k", type=int, default=16)
    parser.add_argument("--disable-bitflip-refinement", action="store_true")
    parser.add_argument("--bitflip-rounds", type=int, default=2)
    parser.add_argument("--exact-validate", action="store_true")
    parser.add_argument("--max-exact-qubits", type=int, default=10)
    parser.add_argument("--no-stats", action="store_true")
    parser.add_argument("--no-validation-stats", action="store_true")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "outputs" / "spacetime_block_pipeline")
    args = parser.parse_args()

    from params import SpacetimeParams
    params = SpacetimeParams(
        score_mode="real",
        trial_absorb_layers=args.trial_absorb_layers,
        max_bond=args.max_bond,
        cutoff_window=args.cutoff_window,
        cutoff_final=args.cutoff_final,
        unswap_threshold=args.global_unswap_threshold,
        seed=args.seed,
    )

    if args.all_tests:
        for name, factory in tests.items():
            run_one(factory(), f"test_{name}", params, args)
        return
    if args.test:
        run_one(tests[args.test](), f"test_{args.test}", params, args)
        return

    from circuit_tools import load_circuit
    run_one(load_circuit(args.qasm), args.qasm.stem, params, args)


if __name__ == "__main__":
    main()
