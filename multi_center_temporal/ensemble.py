"""Multi-center temporal ensemble execution."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .compat import ensure_spacetime_on_path

ensure_spacetime_on_path()

from circuit_tools import remove_measurements
from layer_tools import greedy_layerize
from params import SpacetimeParams
from temporal_global_executor import (
    TemporalGlobalResult,
    run_temporal_global_mpo,
    temporal_global_result_to_dict,
)
from temporal_validation import validate_temporal_centers, validated_temporal_plan_to_dict


@dataclass
class MultiCenterEnsembleResult:
    """Several full temporal MPO executions launched at different centers."""
    label: str
    centers: list[int]
    results: list[TemporalGlobalResult]
    best_result: TemporalGlobalResult | None
    validation_plan: Any
    risk_flags: list[str]
    wall_seconds: float


def _result_score(result: TemporalGlobalResult) -> tuple:
    prob = result.extracted_probability_estimate
    exact = 1 if result.exact_match is True else 0
    has_bits = 1 if result.bitstring_original_order is not None else 0
    mpo_bond = result.mpo_max_bond if result.mpo_max_bond is not None else 10**18
    mps_bond = result.mps_max_bond if result.mps_max_bond is not None else 10**18
    return (
        exact,
        has_bits,
        prob if prob is not None else -1.0,
        -mpo_bond,
        -mps_bond,
    )


def rank_temporal_results(results: list[TemporalGlobalResult]) -> list[TemporalGlobalResult]:
    """Rank temporal runs by validation, candidate probability, then bond size."""
    return sorted(results, key=_result_score, reverse=True)


def ensemble_result_to_dict(
    result: MultiCenterEnsembleResult,
    *,
    include_stats: bool = True,
    include_validation_stats: bool = False,
) -> dict[str, Any]:
    """JSON-friendly MultiCenterEnsembleResult."""
    return {
        "label": result.label,
        "mode": "multi_center_temporal_ensemble",
        "centers": list(result.centers),
        "best_center": None if result.best_result is None else result.best_result.center_layer,
        "best_bitstring_original_order": (
            None if result.best_result is None else result.best_result.bitstring_original_order
        ),
        "best_probability_estimate": (
            None if result.best_result is None else result.best_result.extracted_probability_estimate
        ),
        "validation_plan": validated_temporal_plan_to_dict(
            result.validation_plan,
            include_stats=include_validation_stats,
        ) if result.validation_plan is not None else None,
        "runs": [
            temporal_global_result_to_dict(
                r,
                include_stats=include_stats,
                include_validation_stats=include_validation_stats,
            )
            for r in result.results
        ],
        "risk_flags": list(result.risk_flags),
        "wall_seconds": result.wall_seconds,
    }


def run_multi_center_ensemble(
    qc_raw,
    label: str,
    params: SpacetimeParams,
    *,
    centers: list[int] | None = None,
    num_spawn_centers: int = 4,
    min_center_separation_layers: int = 1,
    top_k: int = 8,
    executor_mode: str = "explicit_rewire",
    run_trial_unswap: bool | None = None,
    run_global_unswap: bool = True,
    max_global_unswap_its: int = 20,
    early_stopping_gates: int = 100,
    global_hows: tuple[str, ...] = ("both", "left", "right"),
    global_equal: bool = False,
    flip_freq: int | None = None,
    sabre_trials: int = 10000,
    peak_num_samples: int = 0,
    peak_sample_top_k: int = 32,
    peak_sample_max_distance: int = 0,
    refine_bitflips: bool = True,
    bitflip_rounds: int = 2,
    min_bitflip_improvement: float = 0.0,
    peak_optimize: str = "auto-hq",
    exact_validate: bool = False,
    max_exact_qubits: int = 10,
    to_backend=None,
) -> MultiCenterEnsembleResult:
    """
    Run several complete temporal MPO executions from distinct centers.

    This is the safest multi-center version: each spawned MPO run is a normal
    temporal pipeline execution, so gate ownership and temporal order are
    unchanged.
    """
    t0 = time.perf_counter()
    qc_clean = remove_measurements(qc_raw)
    layers = greedy_layerize(qc_clean)
    validation = validate_temporal_centers(
        qc_clean,
        params,
        top_k=max(top_k, num_spawn_centers),
        centers=centers,
        run_unswap=run_trial_unswap,
        to_backend=to_backend,
    )

    if centers is None:
        proposed = list(validation.candidate_centers)
    else:
        proposed = list(dict.fromkeys(centers))

    selected: list[int] = []
    for c in proposed:
        if c < 0 or c > len(layers):
            continue
        if all(abs(c - prev) >= min_center_separation_layers for prev in selected):
            selected.append(c)
        if len(selected) >= num_spawn_centers:
            break

    risk_flags = ["multi_center_temporal_ensemble", "independent_full_temporal_runs"]
    if not selected:
        risk_flags.append("no_centers_selected")

    results: list[TemporalGlobalResult] = []
    for c in selected:
        results.append(run_temporal_global_mpo(
            qc_clean,
            f"{label}_center_{c}",
            params,
            top_k=1,
            center=c,
            run_trial_unswap=run_trial_unswap,
            run_global_unswap=run_global_unswap,
            max_global_unswap_its=max_global_unswap_its,
            early_stopping_gates=early_stopping_gates,
            global_hows=global_hows,
            global_equal=global_equal,
            flip_freq=flip_freq,
            sabre_trials=sabre_trials,
            executor_mode=executor_mode,
            peak_num_samples=peak_num_samples,
            peak_sample_top_k=peak_sample_top_k,
            peak_sample_max_distance=peak_sample_max_distance,
            refine_bitflips=refine_bitflips,
            bitflip_rounds=bitflip_rounds,
            min_bitflip_improvement=min_bitflip_improvement,
            peak_optimize=peak_optimize,
            exact_validate=exact_validate,
            max_exact_qubits=max_exact_qubits,
            to_backend=to_backend,
        ))

    ranked = rank_temporal_results(results)
    return MultiCenterEnsembleResult(
        label=label,
        centers=selected,
        results=ranked,
        best_result=ranked[0] if ranked else None,
        validation_plan=validation,
        risk_flags=risk_flags,
        wall_seconds=time.perf_counter() - t0,
    )

