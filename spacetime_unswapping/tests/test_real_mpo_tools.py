import sys
from pathlib import Path

import pytest

pytest.importorskip("qiskit")
pytest.importorskip("quimb")
pytest.importorskip("qiskit_quimb")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from params import SpacetimeParams
from real_mpo_tools import (
    gate_layer_to_circuit,
    trial_middle_mpo_score,
    trial_result_to_dict,
)
from temporal_validation import validate_temporal_centers, validated_temporal_plan_to_dict
from circuit_tools import remove_measurements
from layer_tools import greedy_layerize
from test_circuits import make_clean_mirror, make_dense_random


def test_gate_layer_to_circuit_builds_layer_circuit():
    qc = remove_measurements(make_clean_mirror(n=3, depth=1))
    layers = greedy_layerize(qc)

    layer_circ = gate_layer_to_circuit(layers[0], qc.num_qubits)

    assert layer_circ.num_qubits == qc.num_qubits
    assert layer_circ.size() == len(layers[0])


def test_trial_middle_mpo_score_returns_real_score_on_clean_mirror():
    qc = remove_measurements(make_clean_mirror(n=3, depth=1))
    layers = greedy_layerize(qc)
    params = SpacetimeParams(
        trial_absorb_layers=2,
        trial_absorb_mode="per_side",
        trial_absorb_policy="greedy",
        run_trial_unswap=False,
        use_trial_rewire=False,
        max_bond=128,
        cutoff_window=1e-8,
    )

    result = trial_middle_mpo_score(qc, center_layer=len(layers) // 2, params=params)

    assert result.score.proxy_used is False
    assert result.score.cost < float("inf")
    assert result.score.max_bond_dim is not None
    assert result.consumed_left <= params.trial_absorb_layers
    assert result.consumed_right <= params.trial_absorb_layers


def test_trial_middle_mpo_score_invalid_center_returns_failure_score():
    qc = remove_measurements(make_dense_random(n=3, depth=1))
    params = SpacetimeParams()

    result = trial_middle_mpo_score(qc, center_layer=0, params=params)

    assert result.score.cost == float("inf")
    assert "invalid_center_layer" in result.score.risk_flags


def test_trial_result_to_dict_contains_stats_and_score():
    qc = remove_measurements(make_clean_mirror(n=3, depth=1))
    layers = greedy_layerize(qc)
    params = SpacetimeParams(trial_absorb_layers=1, max_bond=128)
    result = trial_middle_mpo_score(qc, center_layer=len(layers) // 2, params=params)

    data = trial_result_to_dict(result)

    assert "score" in data
    assert "stats" in data
    assert data["score"]["proxy_used"] is False


def test_validate_temporal_centers_returns_best_real_center():
    qc = remove_measurements(make_clean_mirror(n=3, depth=1))
    params = SpacetimeParams(
        trial_absorb_layers=1,
        max_bond=128,
        cutoff_window=1e-8,
    )

    plan = validate_temporal_centers(qc, params, top_k=2)

    assert plan.candidate_centers
    assert plan.real_center_trials
    assert plan.best_center == plan.real_center_trials[0].center_layer
    assert plan.best_score is plan.real_center_trials[0].score


def test_validated_temporal_plan_to_dict_serializes_trials():
    qc = remove_measurements(make_clean_mirror(n=3, depth=1))
    params = SpacetimeParams(trial_absorb_layers=1, max_bond=128)
    plan = validate_temporal_centers(qc, params, top_k=1)

    data = validated_temporal_plan_to_dict(plan, include_stats=False)

    assert data["best_center"] == plan.best_center
    assert data["real_center_trials"]
    assert "stats" not in data["real_center_trials"][0]


def test_trial_unswap_configuration_is_accepted_without_running_by_default():
    qc = remove_measurements(make_clean_mirror(n=3, depth=1))
    layers = greedy_layerize(qc)
    params = SpacetimeParams(
        trial_absorb_layers=1,
        run_trial_unswap=False,
        trial_unswap_trigger="threshold",
        trial_unswap_threshold_elems=1,
        max_bond=128,
    )

    result = trial_middle_mpo_score(qc, center_layer=len(layers) // 2, params=params)

    assert "unswap_not_run" in result.score.risk_flags


def test_run_unswap_override_does_not_mutate_params():
    qc = remove_measurements(make_clean_mirror(n=3, depth=1))
    layers = greedy_layerize(qc)
    params = SpacetimeParams(
        trial_absorb_layers=1,
        run_trial_unswap=False,
        trial_unswap_trigger="never",
        max_bond=128,
    )

    result = trial_middle_mpo_score(
        qc,
        center_layer=len(layers) // 2,
        params=params,
        run_unswap=True,
    )

    assert params.run_trial_unswap is False
    assert "unswap_not_run" in result.score.risk_flags


def test_trial_unswap_never_trigger_skips_even_when_enabled():
    qc = remove_measurements(make_clean_mirror(n=3, depth=1))
    layers = greedy_layerize(qc)
    params = SpacetimeParams(
        trial_absorb_layers=1,
        run_trial_unswap=True,
        trial_unswap_trigger="never",
        trial_unswap_threshold_elems=1,
        max_bond=128,
    )

    result = trial_middle_mpo_score(qc, center_layer=len(layers) // 2, params=params)

    assert "unswap_not_run" in result.score.risk_flags
    assert "trial_unswap_run" not in result.score.risk_flags
