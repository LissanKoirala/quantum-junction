"""CLI for the total graph/temporal/spacetime experimental pipeline."""
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

from params import SpacetimeParams
from test_circuits import (
    make_clean_mirror,
    make_dense_random,
    make_masked_toy_inverse,
    make_modular_mirror,
    make_shifted_mirror,
    make_swapped_mirror,
)
from total_spacetime_pipeline.pipeline import (
    TotalPipelineParams,
    run_total_spacetime_pipeline,
    total_pipeline_result_to_dict,
)


TESTS = {
    "clean_mirror": lambda: make_clean_mirror(4, 2),
    "shifted_mirror": lambda: make_shifted_mirror(4, 2, 1),
    "swapped_mirror": lambda: make_swapped_mirror(4, 2),
    "masked_inverse": lambda: make_masked_toy_inverse(4, 2, 0.3),
    "modular_mirror": lambda: make_modular_mirror(2, 2, 2, 1),
    "dense_random": lambda: make_dense_random(4, 3),
}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--test", choices=sorted(TESTS))
    src.add_argument("--qasm", type=Path)

    parser.add_argument("--track", choices=("both", "temporal", "spacetime"), default="both")
    parser.add_argument("--no-graph-remap", action="store_true")
    parser.add_argument("--num-spawn-centers", type=int, default=2)
    parser.add_argument("--executor-mode", choices=("no_rewire", "explicit_rewire", "existing_unswap"),
                        default="explicit_rewire")
    parser.add_argument("--run-global-unswap", dest="run_global_unswap",
                        action="store_true", default=True,
                        help="Enable threshold-based unswapping (default: on).")
    parser.add_argument("--disable-global-unswap", dest="run_global_unswap",
                        action="store_false",
                        help="Disable global unswapping.")
    parser.add_argument("--max-global-unswap-its", type=int, default=4)
    parser.add_argument("--early-stopping-gates", type=int, default=100)
    parser.add_argument("--sabre-trials", type=int, default=16)
    parser.add_argument("--top-k-centers", type=int, default=4)
    parser.add_argument("--min-center-separation", type=int, default=1,
                        help="Minimum layer gap between spawned centers.")
    parser.add_argument("--graph-method",
                        choices=("spectral_local", "spectral", "kl_local", "kl",
                                 "degree_local", "degree"),
                        default="spectral_local",
                        help="Qubit chain ordering method (default: spectral_local).")
    parser.add_argument("--graph-local-passes", type=int, default=25,
                        help="Adjacent-swap refinement passes for graph ordering.")
    parser.add_argument("--window-size", type=int, default=2)
    parser.add_argument("--identity-error-threshold", type=float, default=1e-3)
    parser.add_argument("--max-segments", type=int, default=4)
    parser.add_argument("--skip-spawned-bridge", action="store_true")
    parser.add_argument("--max-bond", type=int, default=256)
    parser.add_argument("--cutoff-window", type=float, default=1e-8)
    parser.add_argument("--cutoff-final", type=float, default=1e-8)
    parser.add_argument("--exact-validate", action="store_true")
    parser.add_argument("--max-exact-qubits", type=int, default=8)
    parser.add_argument("--trial-absorb-layers", type=int, default=8)
    parser.add_argument("--peak-num-samples", type=int, default=0)
    parser.add_argument("--bitflip-rounds", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--backend", choices=("auto", "cpu", "cuda"), default="cpu")
    parser.add_argument("--include-temporal-stats", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.test:
        qc = TESTS[args.test]()
        label = f"test_{args.test}"
    else:
        from circuit_tools import load_circuit
        qc = load_circuit(args.qasm)
        label = args.qasm.stem

    to_backend = None
    if args.backend in {"auto", "cuda"}:
        try:
            import torch
            if torch.cuda.is_available():
                from utils import to_backend_cuda
                to_backend = to_backend_cuda
            elif args.backend == "cuda":
                raise RuntimeError("CUDA requested but torch.cuda.is_available() is False")
        except ImportError:
            if args.backend == "cuda":
                raise

    spacetime_params = SpacetimeParams(
        score_mode="real",
        max_bond=args.max_bond,
        cutoff_window=args.cutoff_window,
        cutoff_final=args.cutoff_final,
        trial_absorb_layers=args.trial_absorb_layers,
        seed=args.seed,
    )
    total_params = TotalPipelineParams(
        apply_graph_order=not args.no_graph_remap,
        graph_method=args.graph_method,
        graph_local_passes=args.graph_local_passes,
        run_temporal_track=args.track in {"both", "temporal"},
        run_spacetime_block_track=args.track in {"both", "spacetime"},
        num_spawn_centers=args.num_spawn_centers,
        min_center_separation_layers=args.min_center_separation,
        top_k_centers=args.top_k_centers,
        executor_mode=args.executor_mode,
        run_global_unswap=args.run_global_unswap,
        max_global_unswap_its=args.max_global_unswap_its,
        early_stopping_gates=args.early_stopping_gates,
        sabre_trials=args.sabre_trials,
        window_size=args.window_size,
        identity_error_threshold=args.identity_error_threshold,
        max_segments=args.max_segments,
        run_spawned_bridge_executor=not args.skip_spawned_bridge,
        peak_num_samples=args.peak_num_samples,
        bitflip_rounds=args.bitflip_rounds,
        exact_validate=args.exact_validate,
        max_exact_qubits=args.max_exact_qubits,
    )
    result = run_total_spacetime_pipeline(qc, label, spacetime_params, total_params, to_backend=to_backend)
    data = total_pipeline_result_to_dict(
        result,
        include_temporal_stats=args.include_temporal_stats,
    )

    text = json.dumps(data, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        _write_json(args.output, data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
