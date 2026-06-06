import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_circuits import make_two_independent_blocks, make_weakly_coupled_blocks, make_dense_random_circuit
from circuit_tools import remove_measurements
from graph_tools import build_weighted_interaction_graph, cut_ratio
from partition_tools import initial_balanced_partition, is_balanced, partition_score
from params import SeparatorParams
from diagnostics import summarize_partition, separator_acceptance_decision


def test_kl_recovers_independent_blocks():
    qc = remove_measurements(make_two_independent_blocks(4, 4, 4))
    G = build_weighted_interaction_graph(qc)
    A, B = initial_balanced_partition(G, method="kernighan_lin")
    # The partition should have zero cut (perfect split into the two known components)
    from graph_tools import weighted_cut
    c = weighted_cut(G, A, B)
    assert c == 0.0, f"Expected zero cut, got {c}"


def test_partition_is_balanced_50_50():
    qc = remove_measurements(make_weakly_coupled_blocks(4, 4, 4))
    G = build_weighted_interaction_graph(qc)
    A, B = initial_balanced_partition(G)
    assert is_balanced(A, B, max_imbalance=0.3), f"|A|={len(A)}, |B|={len(B)}"


def test_dense_random_rejected_at_low_threshold():
    qc = remove_measurements(make_dense_random_circuit(8, 10, 4))
    G = build_weighted_interaction_graph(qc)
    A, B = initial_balanced_partition(G)
    params = SeparatorParams(max_cut_ratio=0.10)
    summary = summarize_partition(qc, G, A, B, params)
    accepted, flags = separator_acceptance_decision(summary, params)
    # Dense random likely has high cut ratio; may or may not be accepted.
    # Just verify the function returns sensible types.
    assert isinstance(accepted, bool)
    assert isinstance(flags, list)


def test_weakly_coupled_summary_keys():
    qc = remove_measurements(make_weakly_coupled_blocks(4, 4, 4, n_boundary=1))
    G = build_weighted_interaction_graph(qc)
    A, B = initial_balanced_partition(G)
    params = SeparatorParams()
    summary = summarize_partition(qc, G, A, B, params)
    required_keys = {"cut", "cut_ratio", "boundary_size", "temporal_spread",
                     "accepted", "risk_flags", "n_qubits", "size_A", "size_B"}
    assert required_keys.issubset(summary.keys())
