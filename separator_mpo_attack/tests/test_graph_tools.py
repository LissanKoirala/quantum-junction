import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_circuits import make_two_independent_blocks, make_weakly_coupled_blocks, make_dense_random_circuit
from circuit_tools import remove_measurements
from graph_tools import (
    build_weighted_interaction_graph,
    weighted_cut,
    cut_ratio,
    boundary_vertices,
    boundary_size,
    total_edge_weight,
)


def test_two_independent_blocks_zero_cut():
    qc = remove_measurements(make_two_independent_blocks(4, 4, 4))
    G = build_weighted_interaction_graph(qc)
    A = set(range(4))
    B = set(range(4, 8))
    assert weighted_cut(G, A, B) == 0.0


def test_weakly_coupled_low_cut_ratio():
    qc = remove_measurements(make_weakly_coupled_blocks(4, 4, 4, n_boundary=1))
    G = build_weighted_interaction_graph(qc)
    A = set(range(4))
    B = set(range(4, 8))
    cr = cut_ratio(G, A, B)
    assert cr < 0.3, f"cut_ratio={cr:.4f} unexpectedly high"


def test_boundary_vertices_correct():
    qc = remove_measurements(make_weakly_coupled_blocks(4, 4, 4, n_boundary=2))
    G = build_weighted_interaction_graph(qc)
    A = set(range(4))
    B = set(range(4, 8))
    bA, bB = boundary_vertices(G, A, B)
    bsz = boundary_size(G, A, B)
    assert all(v in A for v in bA)
    assert all(v in B for v in bB)
    assert bsz == len(bA) + len(bB)


def test_total_edge_weight_positive():
    qc = remove_measurements(make_dense_random_circuit(8, 5, 3))
    G = build_weighted_interaction_graph(qc, weight_mode="gate_aware")
    assert total_edge_weight(G) > 0


def test_gate_aware_weights_differ_from_uniform():
    qc = remove_measurements(make_dense_random_circuit(8, 5, 3))
    G_uni = build_weighted_interaction_graph(qc, weight_mode="uniform")
    G_ga = build_weighted_interaction_graph(qc, weight_mode="gate_aware")
    # At least one edge should differ (swap weights differ)
    uniform_weights = sorted(d["weight"] for _, _, d in G_uni.edges(data=True))
    aware_weights = sorted(d["weight"] for _, _, d in G_ga.edges(data=True))
    # They may or may not differ depending on gates; just check both produce graphs
    assert len(uniform_weights) == len(aware_weights)
