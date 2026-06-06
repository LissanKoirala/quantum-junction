#!/usr/bin/env python3
"""
Exact temporal baby pipeline.

This is a small-circuit correctness harness for the spacetime diagnostics.
It uses exact Qiskit Operator/Statevector calculations to test whether temporal
center/window logic finds identity-like cancellation on toy circuits.

It does not perform scalable MPO contraction and is not a full peak-recovery
pipeline.
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


def run_one(qc_raw, label: str, params, output_dir: Path, max_exact_qubits: int) -> dict:
    from circuit_tools import remove_measurements, count_two_qubit_gates
    from layer_tools import greedy_layerize
    from window_tools import make_fixed_layer_windows
    from mpo_scoring import make_scorer
    from horizontal_unswapping import scan_temporal_centers
    from temporal_pipeline import (
        scan_temporal_centers_exact,
        scan_adjacent_window_products_exact,
        exact_score_to_dict,
        exact_peak_bitstring,
    )

    t0 = time.perf_counter()
    qc = remove_measurements(qc_raw)
    layers = greedy_layerize(qc)
    windows = make_fixed_layer_windows(layers, params.window_sizes[0])
    scorer = make_scorer(params)

    proxy_centers = scan_temporal_centers(layers, scorer, params)
    exact_centers = scan_temporal_centers_exact(
        layers,
        qc.num_qubits,
        params,
        max_exact_qubits=max_exact_qubits,
    )
    exact_window_products = scan_adjacent_window_products_exact(
        windows,
        qc.num_qubits,
        max_exact_qubits=max_exact_qubits,
    )

    full_peak_bitstring = None
    full_peak_probability = None
    if qc.num_qubits <= max_exact_qubits:
        full_peak_bitstring, full_peak_probability = exact_peak_bitstring(qc)

    best_proxy_center = proxy_centers[0]["center"] if proxy_centers else None
    best_exact_center = exact_centers[0].center if exact_centers else None
    center_agreement = (
        best_proxy_center is not None
        and best_exact_center is not None
        and best_proxy_center == best_exact_center
    )

    result = {
        "label": label,
        "mode": "exact_temporal_baby_pipeline",
        "warning": (
            "Exact small-circuit temporal sanity check only. "
            "Not scalable MPO contraction and not full peak recovery."
        ),
        "n_qubits": qc.num_qubits,
        "n_layers": len(layers),
        "n_two_qubit_gates": count_two_qubit_gates(qc),
        "window_size": params.window_sizes[0],
        "n_windows": len(windows),
        "trial_absorb_layers": params.trial_absorb_layers,
        "max_exact_qubits": max_exact_qubits,
        "full_peak_bitstring": full_peak_bitstring,
        "full_peak_probability": full_peak_probability,
        "best_proxy_center": best_proxy_center,
        "best_exact_center": best_exact_center,
        "proxy_exact_center_agreement": center_agreement,
        "proxy_center_scores": proxy_centers[:10],
        "exact_center_scores": [exact_score_to_dict(s) for s in exact_centers[:10]],
        "exact_adjacent_window_product_scores": [
            exact_score_to_dict(s) for s in exact_window_products[:10]
        ],
        "wall_seconds": round(time.perf_counter() - t0, 3),
    }

    out_path = output_dir / f"{label}.json"
    _write_json(out_path, result)

    print("\n" + "=" * 72)
    print(f"Temporal baby pipeline: {label}")
    print("=" * 72)
    print(f"qubits={qc.num_qubits} layers={len(layers)} windows={len(windows)}")
    print(f"best proxy center : {best_proxy_center}")
    if exact_centers:
        best = exact_centers[0]
        print(f"best exact center : {best.center}  identity_error={best.identity_error:.3e}")
        print(f"segment peak      : {best.peak_bitstring} p={best.peak_probability:.6f}")
    print(f"full peak         : {full_peak_bitstring} p={full_peak_probability}")
    print(f"proxy/exact agree : {center_agreement}")
    if exact_window_products:
        best_wp = exact_window_products[0]
        print(f"best adjacent product: windows={best_wp.window_pair} "
              f"identity_error={best_wp.identity_error:.3e}")
    print(f"saved             : {out_path}")

    return result


def main() -> None:
    tests = _tests()
    parser = argparse.ArgumentParser(description="Exact temporal baby pipeline")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--test", choices=list(tests))
    src.add_argument("--all-tests", action="store_true")
    src.add_argument("--qasm", type=Path)

    parser.add_argument("--window-size", type=int, default=4)
    parser.add_argument("--trial-absorb-layers", type=int, default=8)
    parser.add_argument("--center-margin", type=int, default=1)
    parser.add_argument("--center-stride", type=int, default=1)
    parser.add_argument("--max-exact-qubits", type=int, default=10)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "outputs" / "temporal_baby_pipeline")
    args = parser.parse_args()

    from params import SpacetimeParams
    params = SpacetimeParams(
        window_sizes=(args.window_size,),
        trial_absorb_layers=args.trial_absorb_layers,
        center_margin=args.center_margin,
        center_stride=args.center_stride,
        score_mode="proxy",
        planner_mode="horizontal_first",
    )

    if args.all_tests:
        for name, factory in tests.items():
            run_one(factory(), f"test_{name}", params, args.output_dir,
                    args.max_exact_qubits)
        return

    if args.test:
        run_one(tests[args.test](), f"test_{args.test}", params, args.output_dir,
                args.max_exact_qubits)
        return

    from circuit_tools import load_circuit
    qc = load_circuit(args.qasm)
    run_one(qc, args.qasm.stem, params, args.output_dir, args.max_exact_qubits)


if __name__ == "__main__":
    main()

