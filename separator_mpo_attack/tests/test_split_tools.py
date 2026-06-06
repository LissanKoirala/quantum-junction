import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_circuits import make_two_independent_blocks, make_weakly_coupled_blocks
from circuit_tools import remove_measurements
from split_tools import (
    split_circuit_by_partition,
    build_remapped_subcircuit,
    split_circuit_into_windows,
    build_remapped_boundary_circuit,
)


def test_independent_blocks_no_boundary_gates():
    qc = remove_measurements(make_two_independent_blocks(4, 4, 4))
    A = set(range(4))
    B = set(range(4, 8))
    buckets = split_circuit_by_partition(qc, A, B)
    assert len(buckets["boundary_gates"]) == 0
    assert len(buckets["A_gates"]) > 0
    assert len(buckets["B_gates"]) > 0


def test_weakly_coupled_has_boundary_gates():
    qc = remove_measurements(make_weakly_coupled_blocks(4, 4, 4, n_boundary=2))
    A = set(range(4))
    B = set(range(4, 8))
    buckets = split_circuit_by_partition(qc, A, B)
    assert len(buckets["boundary_gates"]) > 0


def test_remapped_subcircuit_correct_size():
    qc = remove_measurements(make_two_independent_blocks(4, 4, 4))
    A = set(range(4))
    A_sorted = sorted(A)
    buckets = split_circuit_by_partition(qc, A, set(range(4, 8)))
    sub = build_remapped_subcircuit(buckets["A_gates"], A_sorted)
    assert sub.num_qubits == len(A_sorted)
    # All gate qubit indices should be in 0..|A|-1
    from circuit_tools import get_qubit_index_map
    q2i = get_qubit_index_map(sub)
    for inst in sub.data:
        for q in inst.qubits:
            assert q2i[q] < len(A_sorted)


def test_windowed_split_preserves_all_2q_gates():
    qc = remove_measurements(make_weakly_coupled_blocks(4, 4, 4, n_boundary=2))
    A = set(range(4))
    B = set(range(4, 8))
    windows = split_circuit_into_windows(qc, A, B, num_windows=5)
    total_boundary = sum(len(w["boundary_gates"]) for w in windows)
    total_A = sum(len(w["A_gates"]) for w in windows)
    total_B = sum(len(w["B_gates"]) for w in windows)
    # All 2-qubit gates should be accounted for
    from circuit_tools import iter_two_qubit_gates
    n_2q = sum(1 for _ in iter_two_qubit_gates(qc))
    assert total_boundary + total_A + total_B == n_2q


def test_boundary_circuit_remapping():
    qc = remove_measurements(make_weakly_coupled_blocks(4, 4, 4, n_boundary=2))
    A = set(range(4))
    B = set(range(4, 8))
    A_sorted = sorted(A)
    B_sorted = sorted(B)
    qubit_to_site = {}
    for i, a in enumerate(A_sorted):
        qubit_to_site[a] = i
    for j, b in enumerate(B_sorted):
        qubit_to_site[b] = len(A_sorted) + j
    buckets = split_circuit_by_partition(qc, A, B)
    boundary_circ = build_remapped_boundary_circuit(
        buckets["boundary_gates"], qubit_to_site, len(A_sorted) + len(B_sorted)
    )
    assert boundary_circ.num_qubits == len(A_sorted) + len(B_sorted)
