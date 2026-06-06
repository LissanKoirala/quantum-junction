from __future__ import annotations

import random

import networkx as nx

from graph_tools import weighted_cut, total_edge_weight


def initial_balanced_partition(G: nx.Graph, method: str = "kernighan_lin") -> tuple[set, set]:
    """
    Return a balanced bipartition (A, B) of the qubit node set.
    Supported methods:
        "kernighan_lin"  — NetworkX Kernighan-Lin bisection (default)
        "spectral"       — Fiedler vector bisection
        "random_balanced"— random 50/50 split (for testing)
    Falls back to random_balanced if the preferred method fails.
    """
    nodes = list(G.nodes())
    n = len(nodes)
    if n < 2:
        return set(nodes), set()

    if method == "kernighan_lin":
        try:
            A, B = nx.community.kernighan_lin_bisection(G, weight="weight", seed=0)
            return set(A), set(B)
        except Exception:
            pass  # fall through

    if method == "spectral":
        try:
            return _spectral_bisection(G)
        except Exception:
            pass

    # fallback: random balanced
    shuffled = list(nodes)
    random.shuffle(shuffled)
    half = n // 2
    return set(shuffled[:half]), set(shuffled[half:])


def _spectral_bisection(G: nx.Graph) -> tuple[set, set]:
    import numpy as np

    L = nx.laplacian_matrix(G, weight="weight").toarray().astype(float)
    eigvals, eigvecs = np.linalg.eigh(L)
    fiedler = eigvecs[:, 1]  # second-smallest eigenvector
    nodes = list(G.nodes())
    A = {nodes[i] for i, v in enumerate(fiedler) if v >= 0}
    B = {nodes[i] for i, v in enumerate(fiedler) if v < 0}
    if not A or not B:
        raise ValueError("spectral bisection produced empty partition")
    return A, B


def partition_score(G: nx.Graph, A: set, B: set, lambda_balance: float = 1.0) -> float:
    """cut(A,B) + λ * ||A| - |B||"""
    return weighted_cut(G, A, B) + lambda_balance * abs(len(A) - len(B))


def make_ordering_from_partition(G: nx.Graph, A: set, B: set) -> list[int]:
    """
    Return a linear qubit ordering: A-qubits first (by degree desc), then B-qubits.
    Useful for informing MPO chain ordering.
    """
    def by_degree(qubits):
        return sorted(qubits, key=lambda q: -G.degree(q, weight="weight"))
    return by_degree(A) + by_degree(B)


def is_balanced(A: set, B: set, max_imbalance: float = 0.2) -> bool:
    n = len(A) + len(B)
    if n == 0:
        return True
    return abs(len(A) - len(B)) <= max_imbalance * n


# ── k-way partitioning ────────────────────────────────────────────────


def recursive_bisection(
    G: nx.Graph,
    k: int,
    method: str = "kernighan_lin",
    seed: int | None = None,
) -> list[set]:
    """
    Partition G into k roughly-equal groups using recursive KL bisection.
    Returns a list of k sets of node IDs.
    """
    if k <= 1 or G.number_of_nodes() <= 1:
        return [set(G.nodes())]

    if k == 2:
        A, B = initial_balanced_partition(G, method=method)
        return [A, B]

    # Split in half, recurse into each half
    A, B = initial_balanced_partition(G, method=method)
    k_a = k // 2
    k_b = k - k_a

    sub_a = G.subgraph(A).copy() if G.subgraph(A).number_of_nodes() > 1 else G.subgraph(A)
    sub_b = G.subgraph(B).copy() if G.subgraph(B).number_of_nodes() > 1 else G.subgraph(B)

    parts_a = recursive_bisection(sub_a, k_a, method, seed)
    parts_b = recursive_bisection(sub_b, k_b, method, seed)
    return parts_a + parts_b


def k_way_cut(G: nx.Graph, partitions: list[set]) -> float:
    """Total weight of edges that cross any partition boundary."""
    node_to_part = {}
    for i, p in enumerate(partitions):
        for q in p:
            node_to_part[q] = i
    total = 0.0
    for u, v, d in G.edges(data=True):
        if node_to_part.get(u) != node_to_part.get(v):
            total += d.get("weight", 1.0)
    return total


def k_way_cut_ratio(G: nx.Graph, partitions: list[set]) -> float:
    tw = total_edge_weight(G)
    return k_way_cut(G, partitions) / tw if tw > 0 else 0.0


def k_way_boundary_size(G: nx.Graph, partitions: list[set]) -> int:
    """Number of distinct qubits involved in any cross-partition edge."""
    node_to_part = {}
    for i, p in enumerate(partitions):
        for q in p:
            node_to_part[q] = i
    boundary = set()
    for u, v in G.edges():
        if node_to_part.get(u) != node_to_part.get(v):
            boundary.add(u)
            boundary.add(v)
    return len(boundary)


def find_best_k_partition(
    G: nx.Graph,
    max_k: int = 4,
    method: str = "kernighan_lin",
) -> tuple[int, list[set], float]:
    """
    Try k = 2, 3, ..., max_k and return (k, partitions, cut_ratio)
    for the k that minimises total cross-partition cut_ratio.
    """
    best_k = 2
    best_parts = list(initial_balanced_partition(G, method=method))
    best_ratio = k_way_cut_ratio(G, best_parts)

    for k in range(3, max_k + 1):
        parts = recursive_bisection(G, k, method=method)
        ratio = k_way_cut_ratio(G, parts)
        if ratio < best_ratio:
            best_ratio = ratio
            best_k = k
            best_parts = parts

    return best_k, best_parts, best_ratio
