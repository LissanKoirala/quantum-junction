import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_circuits import (
    make_boundary_refinement_case,
    make_temporally_spread_boundary,
    make_weakly_coupled_blocks,
)
from circuit_tools import remove_measurements
from graph_tools import build_weighted_interaction_graph
from partition_tools import initial_balanced_partition
from boundary_scoring import score_boundary, temporal_boundary_density, temporal_spread
from boundary_refinement import refine_partition_by_boundary_swaps
from params import SeparatorParams


def test_refinement_does_not_increase_score():
    qc = remove_measurements(make_boundary_refinement_case())
    G = build_weighted_interaction_graph(qc)
    A, B = initial_balanced_partition(G)
    params = SeparatorParams(max_refinement_iter=20)
    old_score = score_boundary(qc, G, A, B, params).total
    A2, B2, history = refine_partition_by_boundary_swaps(qc, G, A, B, params)
    new_score = score_boundary(qc, G, A2, B2, params).total
    assert new_score <= old_score + 1e-9, f"Score increased: {old_score:.4f} → {new_score:.4f}"


def test_refinement_history_format():
    qc = remove_measurements(make_weakly_coupled_blocks(4, 4, 4, n_boundary=2))
    G = build_weighted_interaction_graph(qc)
    A, B = initial_balanced_partition(G)
    params = SeparatorParams(max_refinement_iter=5)
    _, _, history = refine_partition_by_boundary_swaps(qc, G, A, B, params)
    for entry in history:
        assert "iteration" in entry
        assert "accepted_move" in entry
        assert "old_score" in entry
        assert "new_score" in entry


def test_temporal_spread_detected():
    qc = remove_measurements(make_temporally_spread_boundary(4, 4, 20))
    G = build_weighted_interaction_graph(qc)
    A = set(range(4))
    B = set(range(4, 8))
    density = temporal_boundary_density(qc, A, B, num_windows=10)
    sp = temporal_spread(density)
    assert sp > 5, f"Expected high temporal spread, got {sp}"


def test_scorer_fn_override():
    """scorer_fn should replace the proxy, not add to it."""
    qc = remove_measurements(make_weakly_coupled_blocks(4, 4, 4))
    G = build_weighted_interaction_graph(qc)
    A, B = initial_balanced_partition(G)

    def fixed_scorer(qc, G, A, B, params):
        return 42.0

    params = SeparatorParams(scorer_fn=fixed_scorer)
    score = score_boundary(qc, G, A, B, params)
    assert score.mpo_proxy == 42.0
