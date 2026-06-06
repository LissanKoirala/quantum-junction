"""Synthetic Qiskit circuits for testing the separator pipeline."""
from __future__ import annotations

import random

from qiskit import QuantumCircuit


def make_two_independent_blocks(nA: int = 4, nB: int = 4, depth: int = 4) -> QuantumCircuit:
    """Two completely disconnected subcircuits — cut should be zero."""
    n = nA + nB
    qc = QuantumCircuit(n)
    rng = random.Random(0)
    for _ in range(depth):
        for q in range(nA - 1):
            qc.cx(q, q + 1)
        for q in range(nA, n - 1):
            qc.cx(q, q + 1)
        for q in range(n):
            qc.rz(rng.uniform(0, 3.14), q)
    return qc


def make_weakly_coupled_blocks(
    nA: int = 4, nB: int = 4, depth: int = 4, n_boundary: int = 2
) -> QuantumCircuit:
    """Two blocks with a small number of cross-partition gates."""
    n = nA + nB
    qc = QuantumCircuit(n)
    rng = random.Random(1)
    # Internal gates
    for _ in range(depth):
        for q in range(nA - 1):
            qc.cx(q, q + 1)
        for q in range(nA, n - 1):
            qc.cx(q, q + 1)
        for q in range(n):
            qc.rz(rng.uniform(0, 3.14), q)
    # Boundary gates (cross-partition)
    for k in range(n_boundary):
        a = k % nA
        b = nA + (k % nB)
        qc.cx(a, b)
    return qc


def make_dense_random_circuit(n: int = 8, depth: int = 10, twoq_per_layer: int = 4) -> QuantumCircuit:
    """All-to-all random 2-qubit gates — no useful separator expected."""
    qc = QuantumCircuit(n)
    rng = random.Random(42)
    qubits = list(range(n))
    for _ in range(depth):
        pairs = random.sample([(i, j) for i in qubits for j in qubits if i < j], twoq_per_layer)
        for i, j in pairs:
            qc.cx(i, j)
        for q in qubits:
            qc.rz(rng.uniform(0, 3.14), q)
    return qc


def make_hidden_swapped_blocks(
    nA: int = 4, nB: int = 4, depth: int = 4, permutation: list[int] | None = None
) -> QuantumCircuit:
    """Two weakly coupled blocks with qubit labels scrambled by a permutation."""
    base = make_weakly_coupled_blocks(nA, nB, depth, n_boundary=1)
    n = nA + nB
    if permutation is None:
        perm = list(range(n))
        random.Random(7).shuffle(perm)
    else:
        perm = permutation
    # Apply permutation via qubit composition
    qc = QuantumCircuit(n)
    for inst in base.data:
        new_qs = [perm[q._index] for q in inst.qubits]
        qc.append(inst.operation, new_qs)
    return qc


def make_temporally_spread_boundary(
    nA: int = 4, nB: int = 4, depth: int = 20
) -> QuantumCircuit:
    """Few unique boundary edges but cross-partition gates repeated across many windows."""
    n = nA + nB
    qc = QuantumCircuit(n)
    rng = random.Random(3)
    for d in range(depth):
        # Internal gates
        for q in range(nA - 1):
            qc.cx(q, q + 1)
        for q in range(nA, n - 1):
            qc.cx(q, q + 1)
        # Boundary gate every layer (same edge, high temporal spread)
        qc.cx(nA - 1, nA)
        for q in range(n):
            qc.rz(rng.uniform(0, 3.14), q)
    return qc


def make_unbalanced_min_cut_case(n_big: int = 7) -> QuantumCircuit:
    """One leaf qubit weakly connected to a dense block — min-cut should be unbalanced."""
    n = n_big + 1
    qc = QuantumCircuit(n)
    rng = random.Random(5)
    # Dense block: all pairs in first n_big qubits
    for i in range(n_big - 1):
        qc.cx(i, i + 1)
    for i in range(0, n_big - 2, 2):
        qc.cx(i, i + 2)
    # Leaf: one gate connecting qubit n_big to qubit 0
    qc.cx(0, n_big)
    for q in range(n):
        qc.rz(rng.uniform(0, 3.14), q)
    return qc


def make_boundary_refinement_case() -> QuantumCircuit:
    """
    Two 4-qubit blocks deliberately split so initial KL partition is imperfect.
    Qubits 0,1,4,5 form block A and 2,3,6,7 form block B,
    but labelled as 0-7 so KL may not immediately find it.
    """
    qc = QuantumCircuit(8)
    # True block A: 0,1,4,5
    for _ in range(3):
        qc.cx(0, 1)
        qc.cx(4, 5)
        qc.cx(0, 4)
        qc.cx(1, 5)
    # True block B: 2,3,6,7
    for _ in range(3):
        qc.cx(2, 3)
        qc.cx(6, 7)
        qc.cx(2, 6)
        qc.cx(3, 7)
    # Weak cross coupling
    qc.cx(1, 2)
    return qc


def make_small_mirror_like_circuit(n: int = 6, depth: int = 3) -> QuantumCircuit:
    """Toy R U U† P circuit with a hidden permutation."""
    qc = QuantumCircuit(n)
    rng = random.Random(9)
    # R: random shallow
    for q in range(n - 1):
        qc.cx(q, q + 1)
    for q in range(n):
        qc.rz(rng.uniform(0, 3.14), q)
    # U block
    for _ in range(depth):
        for q in range(n - 1):
            qc.cx(q, q + 1)
        for q in range(n):
            qc.ry(rng.uniform(0, 3.14), q)
    # Swap obfuscation
    qc.swap(0, 1)
    qc.swap(2, 3)
    # U† block
    for _ in range(depth):
        for q in range(n - 1):
            qc.rz(-rng.uniform(0, 3.14), q)
        for q in range(n - 1, 0, -1):
            qc.cx(q - 1, q)
    # P: peaking layer (just Z rotations)
    for q in range(n):
        qc.rz(3.14 / 4, q)
    return qc
