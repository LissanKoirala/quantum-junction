"""CLI for multi-center temporal experiments."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[0]
SPACETIME = ROOT / "spacetime_unswapping"
for path in (ROOT, SPACETIME):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from multi_center_temporal.ensemble import ensemble_result_to_dict, run_multi_center_ensemble
from multi_center_temporal.identity_windows import detect_identity_windows, identity_candidate_to_dict
from multi_center_temporal.multi_front_executor import execute_multi_front_exact, multi_front_result_to_dict
from multi_center_temporal.segment_planner import plan_multi_front_segments, segment_plan_to_dict
from params import SpacetimeParams
from test_circuits import (
    make_clean_mirror,
    make_masked_toy_inverse,
    make_modular_mirror,
    make_shifted_mirror,
    make_swapped_mirror,
)


TESTS = {
    "clean_mirror": make_clean_mirror,
    "shifted_mirror": make_shifted_mirror,
    "swapped_mirror": make_swapped_mirror,
    "masked_inverse": make_masked_toy_inverse,
    "modular_mirror": make_modular_mirror,
}


def _build_test(name: str):
    if name == "modular_mirror":
        return make_modular_mirror(na=2, nb=2, depth=1, n_cross=1)
    return TESTS[name](n=4, depth=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", choices=sorted(TESTS), default="clean_mirror")
    parser.add_argument("--stage", choices=("ensemble", "plan", "multi_front"), default="plan")
    parser.add_argument("--num-spawn-centers", type=int, default=4)
    parser.add_argument("--min-center-separation-layers", type=int, default=1)
    parser.add_argument("--window-size", type=int, default=2)
    parser.add_argument("--identity-error-threshold", type=float, default=1e-3)
    parser.add_argument("--max-segments", type=int, default=4)
    parser.add_argument("--max-exact-qubits", type=int, default=10)
    parser.add_argument("--executor-mode", choices=("no_rewire", "explicit_rewire", "existing_unswap"),
                        default="explicit_rewire")
    parser.add_argument("--run-global-unswap", action="store_true")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--max-bond", type=int, default=128)
    parser.add_argument("--cutoff-final", type=float, default=1e-8)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    qc = _build_test(args.test)
    params = SpacetimeParams(
        max_bond=args.max_bond,
        cutoff_final=args.cutoff_final,
    )

    candidates = detect_identity_windows(
        qc,
        params,
        window_size=args.window_size,
        max_exact_qubits=args.max_exact_qubits,
        identity_error_threshold=None,
    )
    plan = plan_multi_front_segments(
        candidates,
        max_segments=args.max_segments,
        identity_error_threshold=args.identity_error_threshold,
    )

    if args.stage == "ensemble":
        result = run_multi_center_ensemble(
            qc,
            args.test,
            params,
            num_spawn_centers=args.num_spawn_centers,
            min_center_separation_layers=args.min_center_separation_layers,
            top_k=args.top_k,
            executor_mode=args.executor_mode,
            run_global_unswap=args.run_global_unswap,
            exact_validate=qc.num_qubits <= args.max_exact_qubits,
            max_exact_qubits=args.max_exact_qubits,
        )
        data = ensemble_result_to_dict(result, include_stats=False)
    elif args.stage == "multi_front":
        result = execute_multi_front_exact(qc, plan, max_exact_qubits=args.max_exact_qubits)
        data = multi_front_result_to_dict(result)
    else:
        data = {
            "mode": "multi_center_temporal_plan",
            "identity_window_candidates": [identity_candidate_to_dict(c) for c in candidates],
            "segment_plan": segment_plan_to_dict(plan),
        }

    text = json.dumps(data, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
