"""Total pipeline combining graph ordering, temporal MPOs, and spacetime plans."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .boundary_slicing import (
    BoundaryOrderingAudit,
    boundary_ordering_audit_to_dict,
    run_boundary_ordering_audit,
)
from .compat import ensure_repo_paths
from .graph_ordering import (
    graph_ordering_result_to_dict,
    optimize_qubit_order,
    remap_circuit_to_order,
    translate_ordered_bitstring_to_original,
)
from .spawned_bridge_executor import run_spawned_bridge_contraction, spawned_bridge_result_to_dict
from .window_partitions import build_window_partition_plan, window_partition_plan_to_dict

ensure_repo_paths()

from circuit_tools import remove_measurements
from params import SpacetimeParams

from multi_center_temporal.ensemble import ensemble_result_to_dict, run_multi_center_ensemble
from multi_center_temporal.identity_windows import detect_identity_windows, identity_candidate_to_dict
from multi_center_temporal.multi_front_executor import execute_multi_front_exact, multi_front_result_to_dict
from multi_center_temporal.segment_planner import plan_multi_front_segments, segment_plan_to_dict


@dataclass
class TrackProgress:
    """Compact evidence that a track helped compression and/or peak recovery."""
    track: str
    ran: bool
    compression_metric_before: float | None
    compression_metric_after: float | None
    compression_improved: bool | None
    peak_bitstring: str | None
    peak_probability: float | None
    exact_match: bool | None
    peak_detected: bool
    risk_flags: list[str]


@dataclass
class TemporalTrackResult:
    """Multi-center temporal compression track."""
    ensemble: Any
    best_bitstring_working_order: str | None
    best_bitstring_original_order: str | None
    progress: TrackProgress


@dataclass
class SpacetimeBlockTrackResult:
    """Spacetime block execution track."""
    identity_window_candidates: list[Any]
    multi_front_segment_plan: Any
    baby_multi_front_result: Any
    window_partition_plan: Any
    spawned_bridge_result: Any
    spawned_bridge_bitstring_original_order: str | None
    boundary_ordering_audit: Any
    progress: TrackProgress


@dataclass
class TotalPipelineParams:
    """Controls for the combined experimental pipeline."""
    apply_graph_order: bool = True
    graph_method: str = "spectral_local"
    graph_local_passes: int = 25
    graph_edge_power: float = 1.0

    num_spawn_centers: int = 4
    min_center_separation_layers: int = 1
    top_k_centers: int = 8
    executor_mode: str = "explicit_rewire"
    run_trial_unswap: bool | None = None
    run_global_unswap: bool = True
    max_global_unswap_its: int = 4
    early_stopping_gates: int = 100
    global_hows: tuple[str, ...] = ("both", "left", "right")
    global_equal: bool = False
    sabre_trials: int = 16

    window_size: int | None = None
    identity_error_threshold: float = 1e-3
    max_segments: int = 4
    min_segment_separation_layers: int = 0
    side_change_weight: float = 4.0
    position_change_weight: float = 0.1

    peak_num_samples: int = 0
    peak_sample_top_k: int = 32
    refine_bitflips: bool = True
    bitflip_rounds: int = 2
    exact_validate: bool = False
    max_exact_qubits: int = 8

    run_temporal_track: bool = True
    run_spacetime_block_track: bool = True
    run_temporal_ensemble: bool = True
    run_baby_multi_front_exact: bool = True
    run_spawned_bridge_executor: bool = True


@dataclass
class TotalPipelineResult:
    """Output of the combined experimental pipeline."""
    label: str
    n_qubits: int
    n_gates: int
    graph_ordering: Any
    optimized_qubit_order: list[int]
    temporal_track: TemporalTrackResult
    spacetime_block_track: SpacetimeBlockTrackResult
    temporal_ensemble: Any
    best_bitstring_working_order: str | None
    best_bitstring_original_order: str | None
    identity_window_candidates: list[Any]
    multi_front_segment_plan: Any
    baby_multi_front_result: Any
    window_partition_plan: Any
    spawned_bridge_result: Any
    spawned_bridge_bitstring_original_order: str | None
    boundary_ordering_audit: Any
    progress_summary: dict[str, Any]
    risk_flags: list[str]
    wall_seconds: float


def _audit_all_partitions(
    working_qc,
    partitions: list,
    fallback_n_qubits: int,
    max_exact_qubits: int,
) -> BoundaryOrderingAudit:
    """Run boundary audit over every distinct A/B partition and merge results."""
    if not partitions:
        A, B = _fallback_partition(fallback_n_qubits)
        return run_boundary_ordering_audit(working_qc, A, B, max_exact_qubits=max_exact_qubits)

    seen: set = set()
    audits: list[BoundaryOrderingAudit] = []
    for p in partitions:
        key = (frozenset(p.A), frozenset(p.B))
        if key in seen:
            continue
        seen.add(key)
        audits.append(run_boundary_ordering_audit(
            working_qc, set(p.A), set(p.B), max_exact_qubits=max_exact_qubits,
        ))

    if len(audits) == 1:
        return audits[0]

    all_violations = [v for a in audits for v in a.violations]
    all_flags = list(dict.fromkeys(
        [f for a in audits for f in a.risk_flags] + ["multi_partition_boundary_audit"]
    ))
    worst_error = max(
        (a.deferred_boundary_unitary_error for a in audits if a.deferred_boundary_unitary_error is not None),
        default=None,
    )
    return BoundaryOrderingAudit(
        n_boundary_gates=max(a.n_boundary_gates for a in audits),
        n_local_gates=min(a.n_local_gates for a in audits),
        n_violations=len(all_violations),
        violations=all_violations,
        deferred_boundary_unitary_error=worst_error,
        boundary_event_count=max(a.boundary_event_count for a in audits),
        local_block_count=min(a.local_block_count for a in audits),
        risk_flags=all_flags,
    )


def _fallback_partition(n_qubits: int) -> tuple[set[int], set[int]]:
    half = max(1, n_qubits // 2)
    return set(range(half)), set(range(half, n_qubits))


def _track_progress_to_dict(progress: TrackProgress) -> dict[str, Any]:
    return {
        "track": progress.track,
        "ran": progress.ran,
        "compression_metric_before": progress.compression_metric_before,
        "compression_metric_after": progress.compression_metric_after,
        "compression_improved": progress.compression_improved,
        "peak_bitstring": progress.peak_bitstring,
        "peak_probability": progress.peak_probability,
        "exact_match": progress.exact_match,
        "peak_detected": progress.peak_detected,
        "risk_flags": progress.risk_flags,
    }


def _temporal_progress(ensemble, *, ran: bool) -> TrackProgress:
    if not ran or ensemble is None:
        return TrackProgress(
            track="multi_center_temporal",
            ran=False,
            compression_metric_before=None,
            compression_metric_after=None,
            compression_improved=None,
            peak_bitstring=None,
            peak_probability=None,
            exact_match=None,
            peak_detected=False,
            risk_flags=["temporal_track_not_run"],
        )
    mps_bonds = [
        float(r.mps_max_bond)
        for r in (ensemble.results or [])
        if r.mps_max_bond is not None
    ]
    before = max(mps_bonds) if mps_bonds else None
    best = ensemble.best_result
    after = min(mps_bonds) if mps_bonds else (
        float(best.mps_max_bond) if best is not None and best.mps_max_bond is not None else None
    )
    prob = best.extracted_probability_estimate if best is not None else None
    bitstring = best.bitstring_original_order if best is not None else None
    exact_match = best.exact_match if best is not None else None
    return TrackProgress(
        track="multi_center_temporal",
        ran=True,
        compression_metric_before=before,
        compression_metric_after=after,
        compression_improved=(after is not None and (before is None or after <= before)),
        peak_bitstring=bitstring,
        peak_probability=prob,
        exact_match=exact_match,
        peak_detected=bitstring is not None and (prob is None or prob > 0.0),
        risk_flags=["temporal_progress_evaluated"],
    )


def _spacetime_progress(spawned_bridge, window_partition_plan, *, ran: bool) -> TrackProgress:
    if not ran or spawned_bridge is None:
        return TrackProgress(
            track="spacetime_block",
            ran=False,
            compression_metric_before=None,
            compression_metric_after=None,
            compression_improved=None,
            peak_bitstring=None,
            peak_probability=None,
            exact_match=None,
            peak_detected=False,
            risk_flags=["spacetime_block_track_not_run"],
        )
    before_candidates = [
        s.max_bond_before
        for s in spawned_bridge.block_stats
    ]
    before = float(max(before_candidates)) if before_candidates else 1.0
    after = float(spawned_bridge.final_max_bond)
    prob = (
        spawned_bridge.peak_extraction.probability_estimate
        if spawned_bridge.peak_extraction is not None else None
    )
    transition_cost = getattr(window_partition_plan, "total_transition_cost", 0.0)
    flags = ["spacetime_progress_evaluated"]
    if transition_cost > 0:
        flags.append("migration_cost_nonzero")
    return TrackProgress(
        track="spacetime_block",
        ran=True,
        compression_metric_before=before,
        compression_metric_after=after,
        compression_improved=after <= before,
        peak_bitstring=spawned_bridge.bitstring_working_order,
        peak_probability=prob,
        exact_match=spawned_bridge.exact_match,
        peak_detected=spawned_bridge.bitstring_working_order is not None and (prob is None or prob > 0.0),
        risk_flags=flags,
    )


def _progress_summary(
    graph_result,
    temporal_progress: TrackProgress,
    spacetime_progress: TrackProgress,
) -> dict[str, Any]:
    exact_matches = [
        p.exact_match
        for p in (temporal_progress, spacetime_progress)
        if p.ran and p.exact_match is not None
    ]
    peak_detected = [
        p.peak_detected
        for p in (temporal_progress, spacetime_progress)
        if p.ran
    ]
    return {
        "graph_ordering_improved": graph_result.optimized_cost <= graph_result.initial_cost,
        "graph_ordering_cost_reduction_fraction": graph_result.cost_reduction_fraction,
        "temporal_peak_detected": temporal_progress.peak_detected,
        "spacetime_peak_detected": spacetime_progress.peak_detected,
        "any_peak_detected": any(peak_detected) if peak_detected else False,
        "all_available_exact_matches": all(exact_matches) if exact_matches else None,
        "temporal_compression_improved": temporal_progress.compression_improved,
        "spacetime_compression_improved": spacetime_progress.compression_improved,
    }


def run_temporal_track(
    working_qc,
    label: str,
    spacetime_params: SpacetimeParams,
    total_params: TotalPipelineParams,
    optimized_order: list[int],
    *,
    to_backend=None,
) -> TemporalTrackResult:
    """Run only the multi-center temporal compression track."""
    ensemble = None
    best_working = None
    best_original = None
    if total_params.run_temporal_ensemble:
        ensemble = run_multi_center_ensemble(
            working_qc,
            label,
            spacetime_params,
            num_spawn_centers=total_params.num_spawn_centers,
            min_center_separation_layers=total_params.min_center_separation_layers,
            top_k=total_params.top_k_centers,
            executor_mode=total_params.executor_mode,
            run_trial_unswap=total_params.run_trial_unswap,
            run_global_unswap=total_params.run_global_unswap,
            max_global_unswap_its=total_params.max_global_unswap_its,
            early_stopping_gates=total_params.early_stopping_gates,
            global_hows=total_params.global_hows,
            global_equal=total_params.global_equal,
            sabre_trials=total_params.sabre_trials,
            peak_num_samples=total_params.peak_num_samples,
            peak_sample_top_k=total_params.peak_sample_top_k,
            refine_bitflips=total_params.refine_bitflips,
            bitflip_rounds=total_params.bitflip_rounds,
            exact_validate=total_params.exact_validate,
            max_exact_qubits=total_params.max_exact_qubits,
            to_backend=to_backend,
        )
        if ensemble.best_result is not None:
            best_working = ensemble.best_result.bitstring_original_order
            best_original = translate_ordered_bitstring_to_original(best_working, optimized_order)
    progress = _temporal_progress(
        ensemble,
        ran=total_params.run_temporal_ensemble and ensemble is not None,
    )
    return TemporalTrackResult(
        ensemble=ensemble,
        best_bitstring_working_order=best_working,
        best_bitstring_original_order=best_original,
        progress=progress,
    )


def run_spacetime_block_track(
    working_qc,
    spacetime_params: SpacetimeParams,
    total_params: TotalPipelineParams,
    optimized_order: list[int],
    *,
    to_backend=None,
) -> SpacetimeBlockTrackResult:
    """Run only the spacetime block execution track."""
    identity_candidates = detect_identity_windows(
        working_qc,
        spacetime_params,
        window_size=total_params.window_size,
        max_exact_qubits=total_params.max_exact_qubits,
    )
    segment_plan = plan_multi_front_segments(
        identity_candidates,
        max_segments=total_params.max_segments,
        min_separation_layers=total_params.min_segment_separation_layers,
        identity_error_threshold=total_params.identity_error_threshold,
    )

    baby_multi_front = None
    if total_params.run_baby_multi_front_exact:
        baby_multi_front = execute_multi_front_exact(
            working_qc,
            segment_plan,
            max_exact_qubits=total_params.max_exact_qubits,
        )

    window_partition_plan = build_window_partition_plan(
        working_qc,
        spacetime_params,
        window_size=total_params.window_size,
        side_change_weight=total_params.side_change_weight,
        position_change_weight=total_params.position_change_weight,
    )

    spawned_bridge = None
    spawned_bridge_original = None
    if total_params.run_spawned_bridge_executor:
        spawned_bridge = run_spawned_bridge_contraction(
            working_qc,
            window_partition_plan,
            spacetime_params,
            max_bond=spacetime_params.max_bond,
            cutoff=spacetime_params.cutoff_final,
            peak_num_samples=total_params.peak_num_samples,
            peak_sample_top_k=total_params.peak_sample_top_k,
            refine_bitflips=total_params.refine_bitflips,
            bitflip_rounds=total_params.bitflip_rounds,
            exact_validate=total_params.exact_validate,
            max_exact_qubits=total_params.max_exact_qubits,
            to_backend=to_backend,
        )
        spawned_bridge_original = translate_ordered_bitstring_to_original(
            spawned_bridge.bitstring_working_order,
            optimized_order,
        )

    boundary_audit = _audit_all_partitions(
        working_qc,
        window_partition_plan.partitions,
        working_qc.num_qubits,
        total_params.max_exact_qubits,
    )
    progress = _spacetime_progress(
        spawned_bridge,
        window_partition_plan,
        ran=spawned_bridge is not None,
    )
    return SpacetimeBlockTrackResult(
        identity_window_candidates=identity_candidates,
        multi_front_segment_plan=segment_plan,
        baby_multi_front_result=baby_multi_front,
        window_partition_plan=window_partition_plan,
        spawned_bridge_result=spawned_bridge,
        spawned_bridge_bitstring_original_order=spawned_bridge_original,
        boundary_ordering_audit=boundary_audit,
        progress=progress,
    )


def run_total_spacetime_pipeline(
    qc_raw,
    label: str,
    spacetime_params: SpacetimeParams,
    total_params: TotalPipelineParams | None = None,
    *,
    to_backend=None,
) -> TotalPipelineResult:
    """
    Run the combined graph, temporal, multi-front, and spacetime planning stack.

    The temporal ensemble is a real MPO execution path. The multi-front and
    per-window spacetime components currently produce exact baby-case checks and
    explicit migration/ordering plans so that later scalable tensor execution can
    be added without changing the physical semantics.
    """
    tp = total_params or TotalPipelineParams()
    t0 = time.perf_counter()
    qc_clean = remove_measurements(qc_raw)
    risk_flags = ["total_spacetime_pipeline", "measurements_removed"]

    graph_result = optimize_qubit_order(
        qc_clean,
        spacetime_params,
        method=tp.graph_method,
        max_passes=tp.graph_local_passes,
        edge_power=tp.graph_edge_power,
    )
    optimized_order = graph_result.optimized_order if tp.apply_graph_order else graph_result.natural_order
    working_qc = remap_circuit_to_order(qc_clean, optimized_order) if tp.apply_graph_order else qc_clean
    if tp.apply_graph_order:
        risk_flags.append("graph_order_remapped_circuit")
    else:
        risk_flags.append("graph_order_diagnostic_only")

    if tp.run_temporal_track:
        temporal_track = run_temporal_track(
            working_qc,
            label,
            spacetime_params,
            tp,
            optimized_order,
            to_backend=to_backend,
        )
    else:
        temporal_track = TemporalTrackResult(
            ensemble=None,
            best_bitstring_working_order=None,
            best_bitstring_original_order=None,
            progress=_temporal_progress(None, ran=False),
        )
        risk_flags.append("temporal_ensemble_skipped")

    if tp.run_spacetime_block_track:
        spacetime_track = run_spacetime_block_track(
            working_qc,
            spacetime_params,
            tp,
            optimized_order,
            to_backend=to_backend,
        )
    else:
        # Empty shell used only so old result fields serialize consistently.
        empty_partition_plan = build_window_partition_plan(
            working_qc,
            spacetime_params,
            window_size=tp.window_size,
            side_change_weight=tp.side_change_weight,
            position_change_weight=tp.position_change_weight,
        )
        spacetime_track = SpacetimeBlockTrackResult(
            identity_window_candidates=[],
            multi_front_segment_plan=plan_multi_front_segments([]),
            baby_multi_front_result=None,
            window_partition_plan=empty_partition_plan,
            spawned_bridge_result=None,
            spawned_bridge_bitstring_original_order=None,
            boundary_ordering_audit=_audit_all_partitions(
                working_qc,
                empty_partition_plan.partitions,
                working_qc.num_qubits,
                tp.max_exact_qubits,
            ),
            progress=_spacetime_progress(None, empty_partition_plan, ran=False),
        )
        risk_flags.append("spacetime_block_track_skipped")

    if spacetime_track.multi_front_segment_plan.segments:
        risk_flags.append("horizontal_identity_segments_planned")
    else:
        risk_flags.append("no_horizontal_identity_segments_selected")

    progress_summary = _progress_summary(
        graph_result,
        temporal_track.progress,
        spacetime_track.progress,
    )
    if spacetime_track.spawned_bridge_result is not None:
        risk_flags.extend(spacetime_track.spawned_bridge_result.risk_flags)
    risk_flags.extend(spacetime_track.boundary_ordering_audit.risk_flags)
    risk_flags.extend(spacetime_track.window_partition_plan.risk_flags)
    if tp.run_global_unswap:
        risk_flags.append("global_unswap_enabled")
    if tp.executor_mode == "explicit_rewire":
        risk_flags.append("explicit_rewire_executor")

    return TotalPipelineResult(
        label=label,
        n_qubits=qc_clean.num_qubits,
        n_gates=qc_clean.size(),
        graph_ordering=graph_result,
        optimized_qubit_order=optimized_order,
        temporal_track=temporal_track,
        spacetime_block_track=spacetime_track,
        temporal_ensemble=temporal_track.ensemble,
        best_bitstring_working_order=temporal_track.best_bitstring_working_order,
        best_bitstring_original_order=temporal_track.best_bitstring_original_order,
        identity_window_candidates=spacetime_track.identity_window_candidates,
        multi_front_segment_plan=spacetime_track.multi_front_segment_plan,
        baby_multi_front_result=spacetime_track.baby_multi_front_result,
        window_partition_plan=spacetime_track.window_partition_plan,
        spawned_bridge_result=spacetime_track.spawned_bridge_result,
        spawned_bridge_bitstring_original_order=spacetime_track.spawned_bridge_bitstring_original_order,
        boundary_ordering_audit=spacetime_track.boundary_ordering_audit,
        progress_summary=progress_summary,
        risk_flags=list(dict.fromkeys(risk_flags)),
        wall_seconds=time.perf_counter() - t0,
    )


def total_pipeline_result_to_dict(
    result: TotalPipelineResult,
    *,
    include_temporal_stats: bool = False,
    include_validation_stats: bool = False,
) -> dict[str, Any]:
    """JSON-friendly TotalPipelineResult."""
    temporal_track_dict = {
        "mode": "multi_center_temporal_track",
        "ensemble": (
            ensemble_result_to_dict(
                result.temporal_track.ensemble,
                include_stats=include_temporal_stats,
                include_validation_stats=include_validation_stats,
            )
            if result.temporal_track.ensemble is not None else None
        ),
        "best_bitstring_working_order": result.temporal_track.best_bitstring_working_order,
        "best_bitstring_original_order": result.temporal_track.best_bitstring_original_order,
        "progress": _track_progress_to_dict(result.temporal_track.progress),
    }
    spacetime_track_dict = {
        "mode": "spacetime_block_track",
        "identity_window_candidates": [
            identity_candidate_to_dict(c)
            for c in result.spacetime_block_track.identity_window_candidates
        ],
        "multi_front_segment_plan": segment_plan_to_dict(
            result.spacetime_block_track.multi_front_segment_plan
        ),
        "baby_multi_front_result": (
            multi_front_result_to_dict(result.spacetime_block_track.baby_multi_front_result)
            if result.spacetime_block_track.baby_multi_front_result is not None else None
        ),
        "window_partition_plan": window_partition_plan_to_dict(
            result.spacetime_block_track.window_partition_plan
        ),
        "spawned_bridge_result": (
            spawned_bridge_result_to_dict(result.spacetime_block_track.spawned_bridge_result)
            if result.spacetime_block_track.spawned_bridge_result is not None else None
        ),
        "spawned_bridge_bitstring_original_order": (
            result.spacetime_block_track.spawned_bridge_bitstring_original_order
        ),
        "boundary_ordering_audit": boundary_ordering_audit_to_dict(
            result.spacetime_block_track.boundary_ordering_audit
        ),
        "progress": _track_progress_to_dict(result.spacetime_block_track.progress),
    }
    return {
        "label": result.label,
        "mode": "total_spacetime_pipeline",
        "n_qubits": result.n_qubits,
        "n_gates": result.n_gates,
        "optimized_qubit_order": result.optimized_qubit_order,
        "graph_ordering": graph_ordering_result_to_dict(result.graph_ordering),
        "tracks": {
            "temporal": temporal_track_dict,
            "spacetime_block": spacetime_track_dict,
        },
        "progress_summary": result.progress_summary,
        "temporal_ensemble": (
            ensemble_result_to_dict(
                result.temporal_ensemble,
                include_stats=include_temporal_stats,
                include_validation_stats=include_validation_stats,
            )
            if result.temporal_ensemble is not None else None
        ),
        "best_bitstring_working_order": result.best_bitstring_working_order,
        "best_bitstring_original_order": result.best_bitstring_original_order,
        "identity_window_candidates": [
            identity_candidate_to_dict(c)
            for c in result.identity_window_candidates
        ],
        "multi_front_segment_plan": segment_plan_to_dict(result.multi_front_segment_plan),
        "baby_multi_front_result": (
            multi_front_result_to_dict(result.baby_multi_front_result)
            if result.baby_multi_front_result is not None else None
        ),
        "window_partition_plan": window_partition_plan_to_dict(result.window_partition_plan),
        "spawned_bridge_result": (
            spawned_bridge_result_to_dict(result.spawned_bridge_result)
            if result.spawned_bridge_result is not None else None
        ),
        "spawned_bridge_bitstring_original_order": result.spawned_bridge_bitstring_original_order,
        "boundary_ordering_audit": boundary_ordering_audit_to_dict(result.boundary_ordering_audit),
        "risk_flags": result.risk_flags,
        "wall_seconds": result.wall_seconds,
    }
