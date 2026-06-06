"""
Vertical unswapping: qubit-space partition diagnostics and greedy refinement.

Uses independent gate weights from SpacetimeParams (swap_weight=4.0).
Does NOT modify separator_mpo_attack/graph_tools.py.

Risk flag emitted when SWAP gates cross the proposed partition:
    cross_partition_swap_detected
"""
from __future__ import annotations

import math

import networkx as nx

from plan_types import GateInfo, TemporalWindow


# ── Gate-weight graph ─────────────────────────────────────────────────────────

def _gate_weight(name: str, params) -> float:
    """Return the interaction weight for a 2-qubit gate according to SpacetimeParams."""
    if name == "swap":
        return params.swap_weight
    if name in {"cx", "cnot"}:
        return params.cx_weight
    if name in {"cz"}:
        return params.cz_weight
    if name in {"ecr"}:
        return params.ecr_weight
    if name in {"iswap", "siswap"}:
        return params.iswap_weight
    if name in {"rzz", "rzx", "rxx", "ryy", "cp", "crz", "cr", "xx_plus_yy", "unitary"}:
        return params.other_two_qubit_weight
    return params.other_two_qubit_weight


def build_spacetime_interaction_graph(
    gates: list[GateInfo],
    n_qubits: int,
    params,
) -> nx.Graph:
    """
    Build a weighted qubit interaction graph using SpacetimeParams gate weights.
    SWAP gets swap_weight=4.0 (not 0.2 as in separator_mpo_attack).
    """
    G = nx.Graph()
    G.add_nodes_from(range(n_qubits))

    for g in gates:
        if len(g.qubits) != 2:
            continue
        i, j = g.qubits
        w = _gate_weight(g.name, params)
        if G.has_edge(i, j):
            G[i][j]["weight"] += w
            G[i][j]["count"] += 1
            G[i][j]["gate_names"].append(g.name)
        else:
            G.add_edge(i, j, weight=w, count=1, gate_names=[g.name])

    return G


# ── Graph utilities ───────────────────────────────────────────────────────────

def _total_weight(G: nx.Graph) -> float:
    return sum(d.get("weight", 1.0) for _, _, d in G.edges(data=True))


def _weighted_cut(G: nx.Graph, A: set, B: set) -> float:
    return sum(
        d.get("weight", 1.0)
        for u, v, d in G.edges(data=True)
        if (u in A) != (v in A)
    )


def _cut_ratio(G: nx.Graph, A: set, B: set) -> float:
    tw = _total_weight(G)
    return _weighted_cut(G, A, B) / tw if tw > 0 else 0.0


def _boundary_vertices(G: nx.Graph, A: set, B: set) -> tuple[set, set]:
    bA, bB = set(), set()
    for u, v in G.edges():
        if u in A and v in B:
            bA.add(u); bB.add(v)
        elif u in B and v in A:
            bB.add(u); bA.add(v)
    return bA, bB


def _boundary_size(G: nx.Graph, A: set, B: set) -> int:
    bA, bB = _boundary_vertices(G, A, B)
    return len(bA) + len(bB)


# ── Initial partition ─────────────────────────────────────────────────────────

def find_initial_partition(G: nx.Graph, seed: int | None = 0) -> tuple[set, set]:
    """
    Use Kernighan-Lin bisection to find a balanced bipartition.
    Falls back to a simple degree-based 50/50 split on failure.
    """
    nodes = list(G.nodes())
    n = len(nodes)
    if n < 2:
        return set(nodes), set()

    try:
        A, B = nx.community.kernighan_lin_bisection(G, weight="weight", seed=seed)
        return set(A), set(B)
    except Exception:
        pass

    # Fallback: split by degree rank
    by_degree = sorted(nodes, key=lambda q: G.degree(q, weight="weight"), reverse=True)
    half = n // 2
    return set(by_degree[:half]), set(by_degree[half:])


# ── Per-window boundary diagnostics ──────────────────────────────────────────

def compute_boundary_density_per_window(
    windows: list[TemporalWindow],
    A: set,
    B: set,
) -> dict[int, int]:
    """Count 2-qubit gates that cross the A|B boundary in each window."""
    return {
        w.index: sum(
            1 for g in w.gates
            if len(g.qubits) == 2 and (g.qubits[0] in A) != (g.qubits[1] in A)
        )
        for w in windows
    }


def compute_window_cut_ratios(
    windows: list[TemporalWindow],
    G: nx.Graph,
    A: set,
    B: set,
) -> dict[int, float]:
    """
    For each window, compute a per-window cut ratio using only gates in that window.
    Uses unweighted edge counts (1 per gate) since we don't reweight per window.
    """
    ratios = {}
    for w in windows:
        total = 0
        boundary = 0
        for g in w.gates:
            if len(g.qubits) != 2:
                continue
            total += 1
            if (g.qubits[0] in A) != (g.qubits[1] in A):
                boundary += 1
        ratios[w.index] = boundary / total if total > 0 else 0.0
    return ratios


def compute_window_boundary_sizes(
    windows: list[TemporalWindow],
    G: nx.Graph,
    A: set,
    B: set,
) -> dict[int, int]:
    """Count unique qubits involved in cross-partition gates per window."""
    sizes = {}
    for w in windows:
        boundary_qubits: set[int] = set()
        for g in w.gates:
            if len(g.qubits) == 2 and (g.qubits[0] in A) != (g.qubits[1] in A):
                boundary_qubits.update(g.qubits)
        sizes[w.index] = len(boundary_qubits)
    return sizes


# ── Vertical partition score ──────────────────────────────────────────────────

def compute_vertical_score(
    G: nx.Graph,
    A: set,
    B: set,
    windows: list[TemporalWindow],
    params,
) -> float:
    """
    Compute the vertical partition objective J_vert:
        alpha_q_cut * cut(A,B)
        + gamma_boundary_size * |boundary_vertices|
        + lambda_temporal_spread * spread
        + lambda_temporal_entropy * H
        + lambda_balance * ||A| - |B||
    """
    cut = _weighted_cut(G, A, B)
    bsz = _boundary_size(G, A, B)

    density = compute_boundary_density_per_window(windows, A, B)
    density_vals = list(density.values())
    spread = sum(1 for d in density_vals if d > 0)
    total = sum(density_vals)

    H = 0.0
    if total > 0:
        for d in density_vals:
            if d > 0:
                p = d / total
                H -= p * math.log(p)

    imbalance = abs(len(A) - len(B))

    return (
        params.alpha_q_cut * cut
        + params.gamma_boundary_size * bsz
        + params.lambda_temporal_spread * spread
        + params.lambda_temporal_entropy * H
        + params.lambda_balance * imbalance
    )


# ── Greedy membership-swap refinement ─────────────────────────────────────────

def refine_partition(
    gates: list[GateInfo],
    G: nx.Graph,
    A: set,
    B: set,
    windows: list[TemporalWindow],
    params,
) -> tuple[set, set, list[dict]]:
    """
    Greedy boundary membership-swap refinement.

    At each step, evaluate all (a ∈ A, b ∈ B) boundary swaps and accept
    the one that most reduces compute_vertical_score.
    Stops when no move improves by more than vertical_acceptance_margin
    or max_vertical_refinement_iter is reached.

    Returns (A_refined, B_refined, history).
    """
    current_score = compute_vertical_score(G, A, B, windows, params)
    history: list[dict] = []

    for iteration in range(params.max_vertical_refinement_iter):
        bA, bB = _boundary_vertices(G, A, B)
        cands_A = bA if bA else A
        cands_B = bB if bB else B

        best_move = None
        best_score = current_score

        for a in cands_A:
            for b in cands_B:
                A2 = (A - {a}) | {b}
                B2 = (B - {b}) | {a}
                if not A2 or not B2:
                    continue
                if abs(len(A2) - len(B2)) > params.max_size_imbalance:
                    continue
                s = compute_vertical_score(G, A2, B2, windows, params)
                if s < best_score - params.vertical_acceptance_margin:
                    best_score = s
                    best_move = (a, b)

        if best_move is None:
            break

        a, b = best_move
        history.append({
            "iteration": iteration,
            "move": (a, b),
            "old_score": current_score,
            "new_score": best_score,
        })
        A = (A - {a}) | {b}
        B = (B - {b}) | {a}
        current_score = best_score

    return A, B, history


# ── SWAP risk detection ───────────────────────────────────────────────────────

def detect_cross_partition_swaps(
    gates: list[GateInfo],
    A: set,
    B: set,
) -> list[GateInfo]:
    """
    Return SWAP gates that cross the A|B partition boundary.
    Each such gate exchanges logical quantum states between sides, which can
    invalidate a fixed qubit-membership decomposition.
    Emits risk flag: cross_partition_swap_detected (handled by caller).
    """
    return [
        g for g in gates
        if g.name == "swap"
        and len(g.qubits) == 2
        and (g.qubits[0] in A) != (g.qubits[1] in A)
    ]
