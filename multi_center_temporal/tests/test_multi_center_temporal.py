import sys
from pathlib import Path

import pytest

pytest.importorskip("qiskit")

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "multi_center_temporal"
SPACETIME = ROOT / "spacetime_unswapping"
for path in (str(ROOT), str(PKG), str(SPACETIME)):
    if path not in sys.path:
        sys.path.insert(0, path)

from multi_center_temporal.ensemble import rank_temporal_results
from multi_center_temporal.identity_windows import detect_identity_windows
from multi_center_temporal.multi_front_executor import execute_multi_front_exact
from multi_center_temporal.segment_planner import plan_multi_front_segments
from params import SpacetimeParams
from temporal_global_executor import TemporalGlobalResult
from test_circuits import make_clean_mirror


def test_identity_window_detector_finds_clean_mirror_candidates():
    qc = make_clean_mirror(n=4, depth=1)
    params = SpacetimeParams(window_sizes=(2,), trial_absorb_layers=1)

    candidates = detect_identity_windows(
        qc,
        params,
        window_size=2,
        max_exact_qubits=6,
    )

    assert candidates
    assert candidates[0].identity_error >= 0.0
    assert candidates[0].layer_start <= candidates[0].layer_end


def test_segment_planner_selects_non_overlapping_segments():
    qc = make_clean_mirror(n=4, depth=1)
    params = SpacetimeParams(window_sizes=(2,), trial_absorb_layers=1)
    candidates = detect_identity_windows(qc, params, window_size=2, max_exact_qubits=6)

    plan = plan_multi_front_segments(
        candidates,
        max_segments=2,
        min_separation_layers=0,
        identity_error_threshold=10.0,
    )

    assert len(plan.segments) <= 2
    for a, b in zip(plan.segments, plan.segments[1:]):
        assert a.layer_end < b.layer_start


def test_multi_front_exact_returns_bridge_diagnostics():
    qc = make_clean_mirror(n=4, depth=1)
    params = SpacetimeParams(window_sizes=(2,), trial_absorb_layers=1)
    candidates = detect_identity_windows(qc, params, window_size=2, max_exact_qubits=6)
    plan = plan_multi_front_segments(candidates, max_segments=2, identity_error_threshold=10.0)

    result = execute_multi_front_exact(qc, plan, max_exact_qubits=6)

    assert result.exact_peak_bitstring is not None
    assert result.bridge_diagnostics
    assert "chronological_segment_order" in result.risk_flags


def _fake_result(center, prob, exact, mpo_bond):
    return TemporalGlobalResult(
        label=f"center_{center}",
        n_qubits=2,
        n_gates=0,
        n_layers=0,
        validated_plan=None,
        center_layer=center,
        center_instruction=center,
        center_ratio=0.0,
        raw_site_bitstring="00",
        bitstring_original_order="00",
        site_to_qubit=[0, 1],
        marginal_p0s=[],
        extracted_probability_estimate=prob,
        peak_extraction=None,
        exact_peak_bitstring="00",
        exact_peak_probability=1.0,
        exact_match=exact,
        mpo_max_bond=mpo_bond,
        mps_max_bond=mpo_bond,
        stats=[],
        risk_flags=[],
        wall_seconds=0.0,
    )


def test_rank_temporal_results_prefers_exact_then_probability_then_bond():
    low_prob_exact = _fake_result(1, 0.4, True, 4)
    high_prob_inexact = _fake_result(2, 0.9, False, 2)
    high_prob_exact = _fake_result(3, 0.8, True, 8)

    ranked = rank_temporal_results([low_prob_exact, high_prob_inexact, high_prob_exact])

    assert [r.center_layer for r in ranked] == [3, 1, 2]
