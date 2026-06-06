"""
Window feature extraction: gate histograms, interaction graphs, inverse scores.

All scores are proxy-only. They do not validate MPO compressibility.
Risk flag: proxy_mpo_score_no_tensor_validation
"""
from __future__ import annotations

import math
from collections import Counter

import networkx as nx
import numpy as np

from plan_types import GateInfo, TemporalWindow


# ── Self-inverse and angle-negation gate sets ─────────────────────────────────

_SELF_INVERSE = frozenset({
    "cx", "cnot", "cz", "swap", "h", "x", "y", "z",
    "ccx", "ecr", "dcx", "iswap", "ch", "cy",
})

_ANGLE_INVERSE = frozenset({
    "rx", "ry", "rz", "p", "u1", "rzz", "rzx", "rxx", "ryy",
    "cp", "crz", "r",
})

_DEFAULT_TWOQ_WEIGHT = 0.5  # fallback for unrecognized 2-qubit gates


# ── Basic window features ─────────────────────────────────────────────────────

def window_gate_histogram(window: TemporalWindow) -> dict[str, int]:
    """Return gate-name counts for all gates in the window."""
    return dict(Counter(g.name for g in window.gates))


def window_support(window: TemporalWindow) -> set[int]:
    """Return the set of qubits touched by any gate in the window."""
    return {q for g in window.gates for q in g.qubits}


def window_interaction_graph(window: TemporalWindow) -> nx.Graph:
    """
    Build a weighted undirected qubit graph for 2-qubit gates in the window.
    Edge weight = total gate count between qubit pair.
    """
    G = nx.Graph()
    for g in window.gates:
        if len(g.qubits) != 2:
            continue
        i, j = g.qubits
        if G.has_edge(i, j):
            G[i][j]["weight"] += 1
            G[i][j]["gate_names"].append(g.name)
        else:
            G.add_edge(i, j, weight=1, gate_names=[g.name])
    return G


def angle_signature(window: TemporalWindow, rounding: int = 6) -> dict:
    """
    Coarse gate-angle signature: maps (gate_name, n_qubits) -> list of rounded param tuples.
    Useful for spotting repeated or negated angles.
    """
    sig: dict[tuple, list] = {}
    for g in window.gates:
        if g.params:
            key = (g.name, len(g.qubits))
            rounded = tuple(round(p, rounding) for p in g.params)
            sig.setdefault(key, []).append(rounded)
    return {f"{k[0]}_{k[1]}q": v for k, v in sig.items()}


def proxy_window_mpo_cost(window: TemporalWindow) -> float:
    """
    Rough proxy for MPO complexity of a window.
    Higher means more expensive to represent as an MPO.
    """
    n_twoq = sum(1 for g in window.gates if len(g.qubits) == 2)
    support_size = len(window_support(window))
    if n_twoq == 0:
        return 0.0
    cap = min(support_size, 20)
    return cap * math.log(2) + math.sqrt(n_twoq)


# ── Inverse scoring ───────────────────────────────────────────────────────────

def _gate_inverse_match(
    ga: GateInfo,
    gb: GateInfo,
    permutation: dict[int, int] | None = None,
) -> float:
    """
    Score how well gb looks like the inverse of ga. Returns value in [0.0, 1.0].
    A score of 1.0 means perfect inverse match under the given permutation.
    """
    qa = ga.qubits
    # Apply permutation to ga's qubit indices
    if permutation:
        qa = tuple(permutation.get(q, q) for q in qa)

    # Qubit sets must match (order-insensitive for 2q gates; exact for 1q)
    if len(qa) != len(gb.qubits):
        return 0.0
    if len(qa) == 1:
        if qa[0] != gb.qubits[0]:
            return 0.0
    else:
        if frozenset(qa) != frozenset(gb.qubits):
            return 0.0

    if ga.name != gb.name:
        return 0.0

    if ga.name in _SELF_INVERSE:
        return 1.0

    if ga.name in _ANGLE_INVERSE and len(ga.params) == len(gb.params) and ga.params:
        # Perfect inverse: all angles negated
        if all(abs(pa + pb) < 1e-6 for pa, pb in zip(ga.params, gb.params)):
            return 1.0
        # Partial credit: some angles negated
        negated = sum(1 for pa, pb in zip(ga.params, gb.params) if abs(pa + pb) < 1e-6)
        return 0.5 * negated / len(ga.params)

    # Unknown gate type — can't determine inverse symbolically
    return 0.1


def inverse_symbolic_score(
    window_a: TemporalWindow,
    window_b: TemporalWindow,
) -> float:
    """
    Score whether window_b looks like inverse(window_a) in gate order.
    Returns value in [0.0, 1.0]. 1.0 = perfect symbolic inverse.

    Method: pair reversed(window_a.gates) with window_b.gates.
    Normalize by max(len_a, len_b) to penalize length mismatches.
    """
    gates_a = [g for g in window_a.gates]
    gates_b = [g for g in window_b.gates]
    if not gates_a or not gates_b:
        return 0.0

    rev_a = list(reversed(gates_a))
    n_pairs = max(len(rev_a), len(gates_b))

    total = 0.0
    for ga, gb in zip(rev_a, gates_b):
        total += _gate_inverse_match(ga, gb)

    return total / n_pairs


def permuted_inverse_symbolic_score(
    window_a: TemporalWindow,
    window_b: TemporalWindow,
    permutation: dict[int, int],
) -> float:
    """
    Apply qubit relabeling to window_a's gates, then compute inverse score.
    permutation maps original qubit indices in window_a -> target qubit indices.
    """
    gates_a = [g for g in window_a.gates]
    gates_b = [g for g in window_b.gates]
    if not gates_a or not gates_b:
        return 0.0

    rev_a = list(reversed(gates_a))
    n_pairs = max(len(rev_a), len(gates_b))

    total = 0.0
    for ga, gb in zip(rev_a, gates_b):
        total += _gate_inverse_match(ga, gb, permutation)

    return total / n_pairs


# ── Interaction graph similarity ──────────────────────────────────────────────

def interaction_graph_similarity(
    window_a: TemporalWindow,
    window_b: TemporalWindow,
    permutation: dict[int, int] | None = None,
) -> float:
    """
    Cosine similarity between the edge-weight vectors of the two windows' graphs.
    Returns value in [0.0, 1.0]. 1.0 = identical edge structure (after permutation).

    permutation (optional): maps qubit indices of window_a -> new indices,
    applied before comparison so that graph_a's nodes match graph_b's.
    """
    ga = window_interaction_graph(window_a)
    gb = window_interaction_graph(window_b)

    if permutation:
        ga = nx.relabel_nodes(ga, permutation)

    all_edges = set()
    for u, v in ga.edges():
        all_edges.add((min(u, v), max(u, v)))
    for u, v in gb.edges():
        all_edges.add((min(u, v), max(u, v)))

    if not all_edges:
        return 1.0  # both graphs empty → trivially similar

    edges_sorted = sorted(all_edges)

    def _w(G, u, v):
        if G.has_edge(u, v):
            return G[u][v].get("weight", 1.0)
        return 0.0

    wa = np.array([_w(ga, u, v) for u, v in edges_sorted], dtype=float)
    wb = np.array([_w(gb, u, v) for u, v in edges_sorted], dtype=float)

    na = np.linalg.norm(wa)
    nb = np.linalg.norm(wb)

    if na == 0.0 and nb == 0.0:
        return 1.0
    if na == 0.0 or nb == 0.0:
        return 0.0

    return float(np.dot(wa / na, wb / nb))
