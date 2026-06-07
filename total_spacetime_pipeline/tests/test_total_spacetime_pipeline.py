import sys
from pathlib import Path

import pytest

pytest.importorskip("qiskit")

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "spacetime_unswapping", ROOT / "multi_center_temporal"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from qiskit import QuantumCircuit

from params import SpacetimeParams
from test_circuits import make_clean_mirror
from total_spacetime_pipeline.boundary_slicing import run_boundary_ordering_audit
from total_spacetime_pipeline.graph_ordering import (
    build_weighted_twoq_graph,
    optimize_qubit_order,
    ordering_cost,
    remap_circuit_to_order,
    translate_ordered_bitstring_to_original,
)
from total_spacetime_pipeline.pipeline import (
    TotalPipelineParams,
    run_total_spacetime_pipeline,
    total_pipeline_result_to_dict,
)
from total_spacetime_pipeline.spawned_bridge_executor import run_spawned_bridge_contraction
from total_spacetime_pipeline.window_partitions import build_window_partition_plan


def test_graph_ordering_reduces_weighted_edge_length():
    qc = QuantumCircuit(4)
    for _ in range(3):
        qc.cx(0, 3)
        qc.cz(1, 2)
    params = SpacetimeParams()
    G = build_weighted_twoq_graph(qc, params)

    result = optimize_qubit_order(qc, params)

    assert set(result.optimized_order) == {0, 1, 2, 3}
    assert result.optimized_cost <= result.initial_cost
    assert ordering_cost(G, result.optimized_order) <= ordering_cost(G, [0, 1, 2, 3])


def test_graph_remap_bitstring_translation_roundtrip():
    qc = QuantumCircuit(3)
    qc.x(0)
    qc.x(2)
    order = [2, 0, 1]

    remapped = remap_circuit_to_order(qc, order)

    assert remapped.num_qubits == 3
    assert translate_ordered_bitstring_to_original("101", order) == "110"
    assert translate_ordered_bitstring_to_original("011", order) == "101"


def test_boundary_audit_flags_noncommuting_deferred_boundary():
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    qc.h(0)

    audit = run_boundary_ordering_audit(qc, {0}, {1}, max_exact_qubits=2)

    assert audit.n_boundary_gates == 1
    assert audit.n_violations >= 1
    assert "final_boundary_deferral_invalid" in audit.risk_flags
    assert audit.deferred_boundary_unitary_error is not None
    assert audit.deferred_boundary_unitary_error > 1e-9


def test_window_partition_plan_records_migrations():
    qc = make_clean_mirror(n=4, depth=1)
    params = SpacetimeParams(window_sizes=(2,), trial_absorb_layers=1)

    plan = build_window_partition_plan(qc, params, window_size=2)

    assert plan.partitions
    assert len(plan.migrations) == max(0, len(plan.partitions) - 1)
    assert "transition_penalty_included" in plan.risk_flags


def test_total_pipeline_smoke_without_heavy_temporal_ensemble():
    qc = make_clean_mirror(n=4, depth=1)
    spacetime_params = SpacetimeParams(
        window_sizes=(2,),
        trial_absorb_layers=1,
        max_bond=64,
        cutoff_window=1e-8,
        cutoff_final=1e-8,
    )
    total_params = TotalPipelineParams(
        apply_graph_order=True,
        run_temporal_ensemble=False,
        run_baby_multi_front_exact=True,
        run_spawned_bridge_executor=True,
        window_size=2,
        identity_error_threshold=10.0,
        exact_validate=True,
        max_exact_qubits=6,
    )

    result = run_total_spacetime_pipeline(qc, "smoke", spacetime_params, total_params)
    data = total_pipeline_result_to_dict(result)

    assert data["graph_ordering"]["optimized_order"]
    assert data["temporal_ensemble"] is None
    assert data["window_partition_plan"]["partitions"]
    assert data["spawned_bridge_result"]["bitstring_working_order"] is not None
    assert data["spawned_bridge_result"]["exact_match"] is True
    assert data["tracks"]["temporal"]["progress"]["ran"] is False
    assert data["tracks"]["spacetime_block"]["progress"]["peak_detected"] is True
    assert data["progress_summary"]["spacetime_peak_detected"] is True
    assert data["boundary_ordering_audit"]["boundary_event_count"] >= 0
    assert "total_spacetime_pipeline" in data["risk_flags"]


def test_total_pipeline_can_run_temporal_track_only():
    qc = make_clean_mirror(n=4, depth=1)
    spacetime_params = SpacetimeParams(
        window_sizes=(2,),
        trial_absorb_layers=1,
        max_bond=64,
        cutoff_window=1e-8,
        cutoff_final=1e-8,
    )
    total_params = TotalPipelineParams(
        run_temporal_track=True,
        run_spacetime_block_track=False,
        num_spawn_centers=1,
        top_k_centers=1,
        executor_mode="no_rewire",
        exact_validate=True,
        max_exact_qubits=6,
    )

    result = run_total_spacetime_pipeline(qc, "temporal_only", spacetime_params, total_params)
    data = total_pipeline_result_to_dict(result)

    assert data["tracks"]["temporal"]["progress"]["ran"] is True
    assert data["tracks"]["temporal"]["progress"]["peak_detected"] is True
    assert data["tracks"]["spacetime_block"]["progress"]["ran"] is False
    assert data["progress_summary"]["temporal_peak_detected"] is True


def test_total_pipeline_can_run_spacetime_track_only():
    qc = make_clean_mirror(n=4, depth=1)
    spacetime_params = SpacetimeParams(
        window_sizes=(2,),
        trial_absorb_layers=1,
        max_bond=64,
        cutoff_window=1e-8,
        cutoff_final=1e-8,
    )
    total_params = TotalPipelineParams(
        run_temporal_track=False,
        run_spacetime_block_track=True,
        window_size=2,
        identity_error_threshold=10.0,
        exact_validate=True,
        max_exact_qubits=6,
    )

    result = run_total_spacetime_pipeline(qc, "spacetime_only", spacetime_params, total_params)
    data = total_pipeline_result_to_dict(result)

    assert data["tracks"]["temporal"]["progress"]["ran"] is False
    assert data["tracks"]["spacetime_block"]["progress"]["ran"] is True
    assert data["tracks"]["spacetime_block"]["progress"]["peak_detected"] is True
    assert data["temporal_ensemble"] is None


def test_spawned_bridge_respects_chronological_boundary_ordering():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    qc.h(0)

    params = SpacetimeParams(
        window_sizes=(1,),
        trial_absorb_layers=1,
        max_bond=64,
        cutoff_window=1e-10,
        cutoff_final=1e-10,
    )
    plan = build_window_partition_plan(
        qc,
        params,
        window_size=1,
        side_change_weight=100.0,
        position_change_weight=0.0,
    )
    for p in plan.partitions:
        p.A = {0}
        p.B = {1}
        p.qubit_order = [0, 1]

    result = run_spawned_bridge_contraction(
        qc,
        plan,
        params,
        exact_validate=True,
        max_exact_qubits=2,
    )

    assert result.exact_match is True
    assert any(s.kind == "chronological_boundary_gate" for s in result.block_stats)
    assert result.bitstring_working_order == result.exact_peak_bitstring
