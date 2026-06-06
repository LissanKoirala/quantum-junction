"""
Synthetic test circuits for the spacetime unswapping diagnostics.

Each function returns a QuantumCircuit with a known structural property.
No measurements are included (measurement removal is handled by circuit_tools).
"""
from __future__ import annotations

import random

from qiskit import QuantumCircuit


def _random_layer(qc: QuantumCircuit, pairs: list[tuple[int, int]], rng: random.Random) -> None:
    """Apply a random set of CX gates on the given qubit pairs."""
    for i, j in rng.sample(pairs, min(len(pairs), len(pairs) // 2 + 1)):
        qc.cx(i, j)


def _random_unit(qc: QuantumCircuit, n: int, depth: int, rng: random.Random) -> None:
    """Apply `depth` random layers of CX and RZ gates to qc."""
    pairs = [(i, i + 1) for i in range(n - 1)]
    for _ in range(depth):
        for q in range(n):
            qc.rz(rng.uniform(-3.14, 3.14), q)
        _random_layer(qc, pairs, rng)


def make_clean_mirror(n: int = 6, depth: int = 4, seed: int = 0) -> QuantumCircuit:
    """
    C = U U†.
    Expected: perfect inverse at the midpoint (best center near depth).
    """
    rng = random.Random(seed)
    u = QuantumCircuit(n)
    _random_unit(u, n, depth, rng)
    qc = u.copy()
    qc = qc.compose(u.inverse())
    return qc


def make_shifted_mirror(n: int = 6, depth: int = 4, pad: int = 2, seed: int = 0) -> QuantumCircuit:
    """
    C = A U U† B where A and B are short random prefixes.
    Expected: best center differs from literal midpoint.
    """
    rng = random.Random(seed)
    pad_circ = QuantumCircuit(n)
    _random_unit(pad_circ, n, pad, rng)
    u = QuantumCircuit(n)
    _random_unit(u, n, depth, rng)

    qc = pad_circ.copy()
    qc = qc.compose(u)
    qc = qc.compose(u.inverse())
    qc = qc.compose(pad_circ)
    return qc


def make_swapped_mirror(n: int = 6, depth: int = 4, seed: int = 0) -> QuantumCircuit:
    """
    C = U P U† P^{-1} where P is a fixed qubit permutation (SWAP network).
    Expected: permutation-aware inverse score > identity inverse score.
    """
    rng = random.Random(seed)
    u = QuantumCircuit(n)
    _random_unit(u, n, depth, rng)

    # Build a SWAP-network permutation on even-indexed adjacent pairs
    perm = QuantumCircuit(n)
    for i in range(0, n - 1, 2):
        perm.swap(i, i + 1)

    qc = u.copy()
    qc = qc.compose(perm)
    qc = qc.compose(u.inverse())
    qc = qc.compose(perm.inverse())
    return qc


def make_modular_mirror(
    na: int = 4,
    nb: int = 4,
    depth: int = 4,
    n_cross: int = 2,
    seed: int = 0,
) -> QuantumCircuit:
    """
    C = (U_A ⊗ U_B)(U_A† ⊗ U_B†) with n_cross CX gates between A and B qubits.
    Expected: horizontal center AND vertical A|B partition are both useful.
    """
    rng = random.Random(seed)
    n = na + nb
    ua = QuantumCircuit(na)
    _random_unit(ua, na, depth, rng)
    ub = QuantumCircuit(nb)
    _random_unit(ub, nb, depth, rng)

    qc = QuantumCircuit(n)
    # Apply U_A on A qubits, U_B on B qubits
    qc = qc.compose(ua, qubits=list(range(na)))
    qc = qc.compose(ub, qubits=list(range(na, n)))

    # A few cross-partition CX gates
    for _ in range(n_cross):
        a_q = rng.randint(0, na - 1)
        b_q = rng.randint(na, n - 1)
        qc.cx(a_q, b_q)

    # Inverse
    qc = qc.compose(ub.inverse(), qubits=list(range(na, n)))
    qc = qc.compose(ua.inverse(), qubits=list(range(na)))
    return qc


def make_temporal_boundary_cluster(
    na: int = 4,
    nb: int = 4,
    depth: int = 8,
    n_cross: int = 6,
    cluster_fraction: float = 0.2,
    seed: int = 0,
) -> QuantumCircuit:
    """
    Internal gates spread over `depth` layers; cross-boundary gates concentrated
    in a short cluster_fraction of the total depth.
    Expected: boundary density concentrated in few windows.
    """
    rng = random.Random(seed)
    n = na + nb
    qc = QuantumCircuit(n)

    # Random internal gates throughout
    for _ in range(depth):
        for q in range(na):
            qc.rz(rng.uniform(-3.14, 3.14), q)
        for i in range(0, na - 1, 2):
            qc.cx(i, i + 1)
        for q in range(na, n):
            qc.rz(rng.uniform(-3.14, 3.14), q)
        for i in range(na, n - 1, 2):
            qc.cx(i, i + 1)

    # Boundary gates in one cluster near the middle
    cluster_depth = max(1, int(depth * cluster_fraction))
    for _ in range(n_cross):
        a_q = rng.randint(0, na - 1)
        b_q = rng.randint(na, n - 1)
        qc.cx(a_q, b_q)

    return qc


def make_temporally_spread_boundary(
    na: int = 4,
    nb: int = 4,
    depth: int = 8,
    seed: int = 0,
) -> QuantumCircuit:
    """
    Cross-partition CX gates interspersed throughout the whole circuit.
    Expected: high temporal spread risk flag.
    """
    rng = random.Random(seed)
    n = na + nb
    qc = QuantumCircuit(n)

    for _ in range(depth):
        for q in range(n):
            qc.rz(rng.uniform(-3.14, 3.14), q)
        # Internal A gates
        for i in range(0, na - 1, 2):
            qc.cx(i, i + 1)
        # Internal B gates
        for i in range(na, n - 1, 2):
            qc.cx(i, i + 1)
        # Cross-boundary gate in every layer
        a_q = rng.randint(0, na - 1)
        b_q = rng.randint(na, n - 1)
        qc.cx(a_q, b_q)

    return qc


def make_dense_random(n: int = 8, depth: int = 10, seed: int = 0) -> QuantumCircuit:
    """
    Dense random circuit with no discernible structure.
    Expected: fallback_recommended=True.
    """
    rng = random.Random(seed)
    qc = QuantumCircuit(n)
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]

    for _ in range(depth):
        for q in range(n):
            qc.rz(rng.uniform(-3.14, 3.14), q)
            qc.rx(rng.uniform(-3.14, 3.14), q)
        chosen = rng.sample(pairs, min(n // 2, len(pairs)))
        for i, j in chosen:
            qc.cx(i, j)

    return qc


def make_masked_toy_inverse(
    n: int = 6,
    depth: int = 4,
    mask_fraction: float = 0.3,
    seed: int = 0,
) -> QuantumCircuit:
    """
    Near-inverse circuit with some angles perturbed so symbolic matching partially fails.
    Expected: weak symbolic inverse score + risk flag requiring real MPO validation.
    """
    rng = random.Random(seed)
    u = QuantumCircuit(n)
    _random_unit(u, n, depth, rng)

    qc = u.copy()

    # Build a slightly perturbed inverse
    u_inv = u.inverse()
    perturbed = QuantumCircuit(n)
    for inst in u_inv.data:
        op = inst.operation.copy()
        if op.params and rng.random() < mask_fraction:
            # Randomly perturb this gate's angle
            op.params = [p + rng.uniform(-0.5, 0.5) for p in op.params]
        perturbed.append(op, [perturbed.qubits[u_inv.find_bit(q).index] for q in inst.qubits])

    qc = qc.compose(perturbed)
    return qc
