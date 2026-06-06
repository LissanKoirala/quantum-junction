#!/usr/bin/env python3
"""
Spacetime unswapping diagnostics — Stage 1-3 prototype.

WARNING: running in proxy mode. Scores are structural diagnostics only.
They do not prove MPO compressibility and do not recover a bitstring.

Usage:
    # Load a QASM challenge circuit
    python run_spacetime_diagnostics.py --qasm ../challenges/easy/challenge-8_1.qasm

    # Run a synthetic test circuit
    python run_spacetime_diagnostics.py --test clean_mirror
    python run_spacetime_diagnostics.py --test shifted_mirror
    python run_spacetime_diagnostics.py --test swapped_mirror
    python run_spacetime_diagnostics.py --test modular_mirror
    python run_spacetime_diagnostics.py --test temporal_cluster
    python run_spacetime_diagnostics.py --test spread_boundary
    python run_spacetime_diagnostics.py --test dense_random
    python run_spacetime_diagnostics.py --test masked_inverse

    # Run all synthetic tests
    python run_spacetime_diagnostics.py --all-tests

    # Summarize saved JSON results
    python run_spacetime_diagnostics.py --summarize
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
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

# ── Test circuit registry ─────────────────────────────────────────────────────
_TESTS: dict[str, callable] = {}

def _register_tests():
    from test_circuits import (
        make_clean_mirror,
        make_shifted_mirror,
        make_swapped_mirror,
        make_modular_mirror,
        make_temporal_boundary_cluster,
        make_temporally_spread_boundary,
        make_dense_random,
        make_masked_toy_inverse,
    )
    _TESTS.update({
        "clean_mirror":    lambda: make_clean_mirror(6, 4),
        "shifted_mirror":  lambda: make_shifted_mirror(6, 4, 2),
        "swapped_mirror":  lambda: make_swapped_mirror(6, 4),
        "modular_mirror":  lambda: make_modular_mirror(4, 4, 4, 2),
        "temporal_cluster": lambda: make_temporal_boundary_cluster(4, 4, 8, 6),
        "spread_boundary": lambda: make_temporally_spread_boundary(4, 4, 8),
        "dense_random":    lambda: make_dense_random(8, 10),
        "masked_inverse":  lambda: make_masked_toy_inverse(6, 4, 0.3),
    })

# ── JSON helper ───────────────────────────────────────────────────────────────

def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


# ── Summarize saved results ───────────────────────────────────────────────────

def summarize_all(output_dir: Path) -> None:
    results = sorted(output_dir.glob("*.json"))
    if not results:
        print(f"No results found in {output_dir}")
        return

    rows = []
    for p in results:
        try:
            d = json.loads(p.read_text())
            rows.append({
                "label": d.get("label", p.stem),
                "mode": d.get("planner_mode", "?"),
                "n_qubits": d.get("n_qubits", "?"),
                "n_layers": d.get("n_layers", "?"),
                "best_center": d.get("plan", {}).get("best_center"),
                "cut_ratio": d.get("global_cut_ratio"),
                "fallback": d.get("plan", {}).get("fallback_recommended"),
                "h_unswaps": len(d.get("plan", {}).get("horizontal_unswaps", [])),
                "v_moves": len(d.get("plan", {}).get("vertical_unswaps", [])),
                "score": d.get("plan", {}).get("total_score"),
                "wall_s": d.get("wall_seconds"),
            })
        except Exception:
            pass

    header = (f"{'label':<22} {'mode':<18} {'n_q':<5} {'n_l':<5} "
              f"{'center':<8} {'cut':<7} {'fallbk':<7} "
              f"{'h_uns':<6} {'v_mv':<5} {'score':<8} {'wall_s':<6}")
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{str(r['label']):<22} {str(r['mode']):<18} "
            f"{str(r['n_qubits']):<5} {str(r['n_layers']):<5} "
            f"{str(r['best_center'] if r['best_center'] is not None else '-'):<8} "
            f"{str(round(r['cut_ratio'], 3) if r['cut_ratio'] is not None else '-'):<7} "
            f"{str(r['fallback']):<7} "
            f"{str(r['h_unswaps']):<6} {str(r['v_moves']):<5} "
            f"{str(round(r['score'], 3) if r['score'] is not None else '-'):<8} "
            f"{str(round(r['wall_s'], 1) if r['wall_s'] is not None else '-'):<6}"
        )


# ── Main run ──────────────────────────────────────────────────────────────────

def run_one(qc_raw, label: str, params, output_dir: Path) -> dict:
    from spacetime_planner import run_planner
    from diagnostics import plan_to_dict, print_plan_summary, write_plan_json
    from circuit_tools import remove_measurements, count_two_qubit_gates
    from layer_tools import greedy_layerize

    t0 = time.perf_counter()

    print(f"\n{'=' * 60}")
    print(f"Circuit : {label}")
    print(f"Planner : {params.planner_mode}  |  Score mode: {params.score_mode}")
    print("=" * 60)
    print("\nWARNING: running in proxy mode. Scores are structural diagnostics")
    print("only. They do not prove MPO compressibility and do not recover a bitstring.\n")

    qc_clean = remove_measurements(qc_raw)
    n_qubits = qc_clean.num_qubits
    n_twoq = count_two_qubit_gates(qc_clean)
    layers = greedy_layerize(qc_clean)
    n_layers = len(layers)

    log.info(f"[{label}] {n_qubits} qubits, {n_layers} layers, {n_twoq} two-qubit gates")

    plan = run_planner(qc_raw, params)

    wall = time.perf_counter() - t0

    print_plan_summary(plan, label)

    plan_dict = plan_to_dict(plan)

    # Global cut ratio for summary
    global_cut_ratio = None
    if plan.global_partition is not None and plan.cut_ratio_by_window:
        global_cut_ratio = sum(plan.cut_ratio_by_window.values()) / max(len(plan.cut_ratio_by_window), 1)

    result = {
        "label": label,
        "planner_mode": params.planner_mode,
        "score_mode": params.score_mode,
        "n_qubits": n_qubits,
        "n_layers": n_layers,
        "n_two_qubit_gates": n_twoq,
        "global_cut_ratio": global_cut_ratio,
        "plan": plan_dict,
        "wall_seconds": round(wall, 3),
    }

    out_path = output_dir / f"{label}.json"
    _write_json(out_path, result)
    log.info(f"[{label}] Results saved to {out_path}  ({wall:.1f}s)")
    print(f"\nSaved: {out_path}  ({wall:.1f}s)")

    return result


def main() -> None:
    _register_tests()

    parser = argparse.ArgumentParser(
        description="Spacetime unswapping diagnostics (Stage 1-3, proxy mode)"
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--qasm", type=Path, help="Path to QASM file")
    src.add_argument("--test", choices=list(_TESTS), metavar="TEST",
                     help=f"Synthetic test circuit. Choices: {', '.join(_TESTS)}")
    src.add_argument("--all-tests", action="store_true",
                     help="Run all synthetic test circuits")
    src.add_argument("--summarize", action="store_true",
                     help="Print summary of all saved JSON results")

    parser.add_argument("--planner-mode", default="horizontal_first",
                        choices=["horizontal_first", "vertical_first"],
                        help="Planner strategy (default: horizontal_first)")
    parser.add_argument("--score-mode", default="proxy",
                        choices=["proxy", "real"],
                        help="MPO scoring mode. 'real' raises NotImplementedError.")
    parser.add_argument("--window-sizes", type=int, nargs="+", default=[4, 8, 12, 16],
                        metavar="W",
                        help="Temporal window sizes to scan (default: 4 8 12 16)")
    parser.add_argument("--max-cut-ratio", type=float, default=0.15)
    parser.add_argument("--max-size-imbalance", type=int, default=2)
    parser.add_argument("--max-vertical-refinement-iter", type=int, default=50)
    parser.add_argument("--swap-weight", type=float, default=4.0,
                        help="Weight for SWAP gates in interaction graph (default: 4.0)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "outputs" / "spacetime_diagnostics")

    args = parser.parse_args()

    from params import SpacetimeParams
    params = SpacetimeParams(
        planner_mode=args.planner_mode,
        score_mode=args.score_mode,
        window_sizes=tuple(args.window_sizes),
        max_cut_ratio=args.max_cut_ratio,
        max_size_imbalance=args.max_size_imbalance,
        max_vertical_refinement_iter=args.max_vertical_refinement_iter,
        swap_weight=args.swap_weight,
        seed=args.seed,
    )

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.summarize:
        summarize_all(output_dir)
        return

    if args.all_tests:
        for name, factory in _TESTS.items():
            try:
                qc = factory()
                run_one(qc, f"test_{name}", params, output_dir)
            except Exception as exc:
                log.error(f"[test_{name}] Failed: {exc}", exc_info=True)
        return

    if args.test:
        qc = _TESTS[args.test]()
        label = f"test_{args.test}"
    elif args.qasm:
        from circuit_tools import load_circuit
        qc = load_circuit(args.qasm)
        label = args.qasm.stem
    else:
        parser.print_help()
        sys.exit(1)

    run_one(qc, label, params, output_dir)


if __name__ == "__main__":
    main()
