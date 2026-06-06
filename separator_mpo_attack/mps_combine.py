"""
Utilities for combining independent sub-MPSs into a single N-qubit MPS
and applying the boundary circuit to the result.

Perm convention (from mpo_to_mps):
    final_perm[site] = subcircuit qubit measured at that site.
    → combined site k holds original qubit partition_sorted[perm[k]].

qubit_to_combined_site: original qubit → combined site index.
reorder_bitstring: converts site-0-first extraction to Qiskit big-endian
    (qubit N-1 leftmost, qubit 0 rightmost) to match KNOWN answer strings.
"""
from __future__ import annotations

import logging

import quimb.tensor as qtn
from qiskit import QuantumCircuit

log = logging.getLogger(__name__)


def combined_site_map(
    A_sorted: list[int],
    B_sorted: list[int],
    perm_a: list[int],
    perm_b: list[int],
) -> dict[int, int]:
    """
    Build {original_qubit: combined_site} mapping.

    perm_a comes from mpo_to_mps's final_perm:
        final_perm[site] = subcircuit qubit measured at that site.
    So combined site k holds original qubit A_sorted[perm_a[k]].
    """
    n_a = len(A_sorted)
    qubit_to_site: dict[int, int] = {}
    for k in range(n_a):
        qubit_to_site[A_sorted[perm_a[k]]] = k
    for k in range(len(B_sorted)):
        qubit_to_site[B_sorted[perm_b[k]]] = n_a + k
    return qubit_to_site


def combine_mps_product(mps_a: qtn.MatrixProductState, mps_b: qtn.MatrixProductState) -> qtn.MatrixProductState:
    """
    Combine two open-boundary MPS into a product (no A-B entanglement) MPS.

    Open-boundary quimb MPS don't have explicit boundary bonds — the leftmost
    and rightmost tensors are 2D (bond, phys) rather than 3D. This means the
    two sub-MPS are disconnected after a naive merge. We fix it by adding a
    trivial (dim=1) bond index between the last tensor of mps_a and the first
    tensor of mps_b before casting as a unified MPS.
    """
    import numpy as np

    n_a = len(sorted(mps_a.sites))
    n_b = len(sorted(mps_b.sites))

    mps_a_copy = mps_a.copy()
    mps_b_copy = mps_b.copy()

    # Grab boundary tensors BEFORE renaming (site indexing still valid)
    t_right_a = mps_a_copy[n_a - 1]   # last site of A  (site index n_a-1)
    t_left_b  = mps_b_copy[0]          # first site of B (site index 0)

    # Add a dim-1 connecting bond between last-of-A and first-of-B
    new_bond = qtn.rand_uuid()

    # Append new bond at the END of the rightmost A tensor
    t_right_a.modify(
        data=t_right_a.data[..., np.newaxis],
        inds=list(t_right_a.inds) + [new_bond],
    )

    # Prepend new bond at the START of the leftmost B tensor
    t_left_b.modify(
        data=t_left_b.data[np.newaxis, ...],
        inds=[new_bond] + list(t_left_b.inds),
    )

    # Now relabel mps_b physical indices and site tags to start at n_a
    phys_reindex = {mps_b_copy.site_ind(i): f"k{n_a + i}" for i in range(n_b)}
    mps_b_copy.reindex_(phys_reindex)
    tag_retag = {mps_b_copy.site_tag(i): f"I{n_a + i}" for i in range(n_b)}
    mps_b_copy.retag_(tag_retag)

    # Merge tensor networks — now connected at sites n_a-1/n_a
    combined_tn = mps_a_copy | mps_b_copy

    combined_mps = combined_tn.view_as_(
        qtn.MatrixProductState,
        cyclic=False,
        L=n_a + n_b,
        site_ind_id="k{}",
        site_tag_id="I{}",
    )
    return combined_mps


def apply_boundary_to_combined_mps(
    combined_mps: qtn.MatrixProductState,
    boundary_circ: QuantumCircuit,
    max_bond: int,
    cutoff: float,
    to_backend=None,
) -> qtn.MatrixProductState:
    """
    Apply boundary circuit gates to the combined MPS one gate at a time.

    Boundary gates typically act between non-adjacent sites in the combined MPS
    ordering (partition-A sites first, then partition-B), so the MPO-layer
    approach produces malformed tensors.  Instead we apply each gate directly:
      - adjacent sites: gate_ with 'swap+split' contraction
      - non-adjacent sites: gate_with_auto_swap_ (inserts SWAP network internally)
    """
    import numpy as np
    from qiskit.quantum_info import Operator

    mps = combined_mps.copy()
    for inst in boundary_circ.data:
        op = inst.operation
        sites = tuple(boundary_circ.find_bit(q).index for q in inst.qubits)
        G = np.array(Operator(op).data, dtype=complex)

        if len(sites) == 1:
            mps.gate_(G.reshape(2, 2), sites[0], contract=True,
                      max_bond=max_bond, cutoff=cutoff)
        elif len(sites) == 2:
            G4 = G.reshape(2, 2, 2, 2)
            i, j = sites
            if abs(i - j) == 1:
                mps.gate_(G4, sites, contract='swap+split',
                          max_bond=max_bond, cutoff=cutoff)
            else:
                mps.gate_with_auto_swap_(G4, sites,
                                         max_bond=max_bond, cutoff=cutoff)
        log.info(f"[boundary gate] sites={sites} max_bond={mps.max_bond()}")

    return mps


def _merge_two_mps(
    mps_a: qtn.MatrixProductState,
    mps_b: qtn.MatrixProductState,
) -> qtn.MatrixProductState:
    """
    Append mps_b (sites I0..I{n_b-1}) onto the right of mps_a (sites I0..I{n_a-1}).
    Returns a combined MPS with sites I0..I{n_a+n_b-1}.
    Connects them with a trivial dim-1 bond so the combined TN is fully connected.
    """
    import numpy as np

    n_a = len(sorted(mps_a.sites))
    n_b = len(sorted(mps_b.sites))

    mps_a_copy = mps_a.copy()
    mps_b_copy = mps_b.copy()

    # Grab boundary tensors before any renaming
    t_right_a = mps_a_copy[n_a - 1]
    t_left_b  = mps_b_copy[0]

    new_bond = qtn.rand_uuid()
    t_right_a.modify(
        data=t_right_a.data[..., np.newaxis],
        inds=list(t_right_a.inds) + [new_bond],
    )
    t_left_b.modify(
        data=t_left_b.data[np.newaxis, ...],
        inds=[new_bond] + list(t_left_b.inds),
    )

    # Relabel mps_b physical inds and site tags to follow immediately after mps_a
    phys_reindex = {mps_b_copy.site_ind(i): f"k{n_a + i}" for i in range(n_b)}
    mps_b_copy.reindex_(phys_reindex)
    tag_retag = {mps_b_copy.site_tag(i): f"I{n_a + i}" for i in range(n_b)}
    mps_b_copy.retag_(tag_retag)

    combined_tn = mps_a_copy | mps_b_copy
    N = n_a + n_b
    return combined_tn.view_as_(
        qtn.MatrixProductState,
        cyclic=False,
        L=N,
        site_ind_id="k{}",
        site_tag_id="I{}",
    )


def combine_mps_k_product(mps_list: list[qtn.MatrixProductState]) -> qtn.MatrixProductState:
    """
    Chain k MPS states into a single product MPS with trivial dim-1 bonds.
    Works for any k >= 1.
    """
    if len(mps_list) == 1:
        return mps_list[0].copy()
    result = mps_list[0].copy()
    for mps_next in mps_list[1:]:
        result = _merge_two_mps(result, mps_next)
    return result


def combined_site_map_k(
    partitions_sorted: list[list[int]],
    perms: list[list[int]],
) -> dict[int, int]:
    """
    Build {original_qubit: combined_site} for a k-way partition.

    partitions_sorted[i] = sorted list of original qubit indices in partition i.
    perms[i] = final_perm from mpo_to_mps for partition i:
        perms[i][site] = subcircuit qubit measured at that site.
    So combined site (offset_i + k) holds original qubit partitions_sorted[i][perms[i][k]].
    """
    qubit_to_site: dict[int, int] = {}
    offset = 0
    for part_sorted, perm in zip(partitions_sorted, perms):
        n = len(part_sorted)
        for k in range(n):
            qubit_to_site[part_sorted[perm[k]]] = offset + k
        offset += n
    return qubit_to_site


def reorder_bitstring(raw_bits: str, qubit_to_combined_site: dict[int, int]) -> str:
    """
    Convert bitstring indexed by combined_site to Qiskit's big-endian format.

    raw_bits[k] = bit at combined site k (site-0-first order from extract_bitstring).
    Returns a string in Qiskit's measurement convention: qubit N-1 is the leftmost
    character, qubit 0 is the rightmost.  This matches the KNOWN answer strings.
    """
    n = len(raw_bits)
    result = ["?"] * n
    site_to_qubit = {v: k for k, v in qubit_to_combined_site.items()}
    for site, bit in enumerate(raw_bits):
        orig_q = site_to_qubit.get(site)
        if orig_q is not None:
            result[orig_q] = bit
    # Reverse: qubit N-1 first (Qiskit big-endian), qubit 0 last
    return "".join(reversed(result))
