from __future__ import annotations

import math

import networkx as nx

from circuit_tools import iter_two_qubit_gates


# ── Weight functions ────────────────────────────────────────────────


def _weight_uniform(op, time: int, T: int) -> float:
    return 1.0


def _weight_gate_aware(op, time: int, T: int) -> float:
    if op.name == "swap":
        return 0.2
    if op.name in {"cx", "cz", "ecr", "iswap", "rzz", "rzx", "rxx", "ryy",
                   "xx_plus_yy", "unitary"}:
        return 1.0
    return 0.5


def _weight_time_decay(op, time: int, T: int) -> float:
    """Gates near the start get higher weight (mirror-structure: early gates matter more)."""
    if T == 0:
        return 1.0
    return 1.0 - 0.8 * (time / T)


def _weight_time_reverse_decay(op, time: int, T: int) -> float:
    if T == 0:
        return 1.0
    return 0.2 + 0.8 * (time / T)


_WEIGHT_FNS = {
    "uniform": _weight_uniform,
    "gate_aware": _weight_gate_aware,
    "time_decay": _weight_time_decay,
    "time_reverse_decay": _weight_time_reverse_decay,
}


def default_gate_weight(op, time: int, T: int, mode: str = "uniform") -> float:
    fn = _WEIGHT_FNS.get(mode, _weight_uniform)
    return fn(op, time, T)


# ── Graph construction ──────────────────────────────────────────────


def build_weighted_interaction_graph(
    qc,
    weight_mode: str = "uniform",
    weight_fn=None,
) -> nx.Graph:
    """
    Build a weighted undirected graph.
    Nodes: 0..N-1 (qubit indices).
    Edges: 2-qubit interactions with metadata {weight, count, gate_names, times}.
    """
    n = qc.num_qubits
    G = nx.Graph()
    G.add_nodes_from(range(n))

    T = qc.size()  # total instruction count for normalising time-based weights
    wfn = weight_fn or (lambda op, t: default_gate_weight(op, t, T, mode=weight_mode))

    for g in iter_two_qubit_gates(qc):
        i, j = g["qubits"]
        w = wfn(g["operation"], g["time"])
        if G.has_edge(i, j):
            G[i][j]["weight"] += w
            G[i][j]["count"] += 1
            G[i][j]["gate_names"].append(g["name"])
            G[i][j]["times"].append(g["time"])
        else:
            G.add_edge(i, j, weight=w, count=1, gate_names=[g["name"]], times=[g["time"]])
    return G


# ── Graph metrics ───────────────────────────────────────────────────


def total_edge_weight(G: nx.Graph) -> float:
    return sum(d.get("weight", 1.0) for _, _, d in G.edges(data=True))


def weighted_cut(G: nx.Graph, A: set, B: set) -> float:
    cut = 0.0
    for i, j, d in G.edges(data=True):
        if (i in A) != (j in A):   # exactly one endpoint in A
            cut += d.get("weight", 1.0)
    return cut


def cut_ratio(G: nx.Graph, A: set, B: set) -> float:
    total = total_edge_weight(G)
    return weighted_cut(G, A, B) / (total + 1e-12)


def boundary_vertices(G: nx.Graph, A: set, B: set) -> tuple[set, set]:
    """Return (boundary_A, boundary_B) where each vertex has a neighbour on the other side."""
    bA, bB = set(), set()
    for i, j in G.edges():
        if i in A and j in B:
            bA.add(i)
            bB.add(j)
        elif i in B and j in A:
            bB.add(i)
            bA.add(j)
    return bA, bB


def boundary_size(G: nx.Graph, A: set, B: set) -> int:
    bA, bB = boundary_vertices(G, A, B)
    return len(bA) + len(bB)
