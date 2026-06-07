"""Weighted two-qubit graph ordering for the MPS/MPO chain."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import networkx as nx
from qiskit import QuantumCircuit

from .compat import ensure_repo_paths

ensure_repo_paths()

from circuit_tools import remove_measurements


@dataclass
class GraphOrderingResult:
    """Optimized qubit chain order for reducing long weighted two-qubit edges."""
    natural_order: list[int]
    optimized_order: list[int]
    initial_cost: float
    optimized_cost: float
    cost_reduction_fraction: float
    edge_count: int
    weighted_edge_count: float
    method: str
    history: list[dict[str, Any]]
    risk_flags: list[str]


def _gate_weight(name: str, params) -> float:
    if name == "swap":
        return float(getattr(params, "swap_weight", 4.0))
    if name in {"cx", "cnot"}:
        return float(getattr(params, "cx_weight", 1.0))
    if name == "cz":
        return float(getattr(params, "cz_weight", 1.0))
    if name == "ecr":
        return float(getattr(params, "ecr_weight", 1.0))
    if name in {"iswap", "siswap"}:
        return float(getattr(params, "iswap_weight", 2.0))
    if name in {"rzz", "rzx", "rxx", "ryy", "cp", "crz", "cr", "unitary"}:
        return float(getattr(params, "other_two_qubit_weight", 0.5))
    return float(getattr(params, "other_two_qubit_weight", 0.5))


def _qubit_map(qc: QuantumCircuit) -> dict:
    return {q: i for i, q in enumerate(qc.qubits)}


def build_weighted_twoq_graph(qc_raw: QuantumCircuit, params) -> nx.Graph:
    """Build a weighted graph over qubits from all two-qubit gates."""
    qc = remove_measurements(qc_raw)
    q2i = _qubit_map(qc)
    G = nx.Graph()
    G.add_nodes_from(range(qc.num_qubits))
    for t, inst in enumerate(qc.data):
        op = inst.operation
        if len(inst.qubits) != 2:
            continue
        i, j = (q2i[q] for q in inst.qubits)
        w = _gate_weight(op.name, params)
        if G.has_edge(i, j):
            G[i][j]["weight"] += w
            G[i][j]["count"] += 1
            G[i][j]["times"].append(t)
            G[i][j]["gate_names"].append(op.name)
        else:
            G.add_edge(i, j, weight=w, count=1, times=[t], gate_names=[op.name])
    return G


def ordering_cost(G: nx.Graph, order: list[int], *, edge_power: float = 1.0) -> float:
    """
    Weighted MPS-chain edge-length objective.

    Minimizes sum_e w_e * |pos(u)-pos(v)|**edge_power. For ordinary nearest
    neighbor MPS/MPO contraction, edge_power=1 is the most transparent proxy.
    """
    pos = {q: i for i, q in enumerate(order)}
    return float(sum(
        d.get("weight", 1.0) * abs(pos[u] - pos[v]) ** edge_power
        for u, v, d in G.edges(data=True)
    ))


def _degree_order(G: nx.Graph) -> list[int]:
    return sorted(G.nodes(), key=lambda q: (-G.degree(q, weight="weight"), q))


def _spectral_order(G: nx.Graph) -> list[int]:
    if G.number_of_edges() == 0 or G.number_of_nodes() < 3:
        return list(G.nodes())
    import numpy as np

    nodes = list(G.nodes())
    L = nx.laplacian_matrix(G, nodelist=nodes, weight="weight").toarray().astype(float)
    eigvals, eigvecs = np.linalg.eigh(L)
    if len(eigvals) < 2:
        return nodes
    fiedler = eigvecs[:, 1]
    return [nodes[i] for i in np.argsort(fiedler)]


def _kl_partition_order(G: nx.Graph, seed: int | None) -> list[int]:
    nodes = list(G.nodes())
    if len(nodes) < 2:
        return nodes
    try:
        A, B = nx.community.kernighan_lin_bisection(G, weight="weight", seed=seed)
        A_order = _spectral_order(G.subgraph(A).copy())
        B_order = _spectral_order(G.subgraph(B).copy())
        return A_order + B_order
    except Exception:
        return _degree_order(G)


def _orient_best(G: nx.Graph, order: list[int], edge_power: float) -> list[int]:
    rev = list(reversed(order))
    return rev if ordering_cost(G, rev, edge_power=edge_power) < ordering_cost(G, order, edge_power=edge_power) else order


def improve_order_by_local_swaps(
    G: nx.Graph,
    order: list[int],
    *,
    max_passes: int = 25,
    edge_power: float = 1.0,
) -> tuple[list[int], list[dict[str, Any]]]:
    """Greedy adjacent-swap improvement of the weighted edge-length objective."""
    current = list(order)
    current_cost = ordering_cost(G, current, edge_power=edge_power)
    history: list[dict[str, Any]] = []

    for pass_idx in range(max_passes):
        improved = False
        for i in range(len(current) - 1):
            trial = list(current)
            trial[i], trial[i + 1] = trial[i + 1], trial[i]
            trial_cost = ordering_cost(G, trial, edge_power=edge_power)
            if trial_cost + 1e-12 < current_cost:
                history.append({
                    "pass": pass_idx,
                    "swap_positions": [i, i + 1],
                    "swap_qubits": [current[i], current[i + 1]],
                    "old_cost": current_cost,
                    "new_cost": trial_cost,
                })
                current = trial
                current_cost = trial_cost
                improved = True
        if not improved:
            break
    return current, history


def optimize_qubit_order(
    qc_raw: QuantumCircuit,
    params,
    *,
    method: str = "spectral_local",
    max_passes: int = 25,
    edge_power: float = 1.0,
) -> GraphOrderingResult:
    """Optimize the qubit chain order before temporal/spacetime contraction."""
    qc = remove_measurements(qc_raw)
    G = build_weighted_twoq_graph(qc, params)
    natural = list(range(qc.num_qubits))
    initial_cost = ordering_cost(G, natural, edge_power=edge_power)
    risk_flags = ["weighted_twoq_graph_ordering", "objective_weighted_edge_length"]

    candidates = [natural, _degree_order(G), _spectral_order(G), _kl_partition_order(G, getattr(params, "seed", 0))]
    candidates = [_orient_best(G, c, edge_power) for c in candidates if set(c) == set(natural)]
    if not candidates:
        candidates = [natural]
        risk_flags.append("ordering_candidate_generation_failed")

    best = min(candidates, key=lambda c: ordering_cost(G, c, edge_power=edge_power))
    if method.endswith("_local"):
        best, history = improve_order_by_local_swaps(
            G,
            best,
            max_passes=max_passes,
            edge_power=edge_power,
        )
    else:
        history = []

    opt_cost = ordering_cost(G, best, edge_power=edge_power)
    reduction = 0.0 if initial_cost == 0 else (initial_cost - opt_cost) / initial_cost
    if G.number_of_edges() == 0:
        risk_flags.append("no_two_qubit_edges")
    if opt_cost > initial_cost + 1e-12:
        risk_flags.append("optimized_order_worse_than_natural")

    return GraphOrderingResult(
        natural_order=natural,
        optimized_order=list(best),
        initial_cost=float(initial_cost),
        optimized_cost=float(opt_cost),
        cost_reduction_fraction=float(reduction),
        edge_count=G.number_of_edges(),
        weighted_edge_count=float(sum(d.get("weight", 1.0) for _, _, d in G.edges(data=True))),
        method=method,
        history=history,
        risk_flags=risk_flags,
    )


def graph_ordering_result_to_dict(result: GraphOrderingResult) -> dict[str, Any]:
    """JSON-friendly GraphOrderingResult."""
    return {
        "natural_order": result.natural_order,
        "optimized_order": result.optimized_order,
        "initial_cost": result.initial_cost,
        "optimized_cost": result.optimized_cost,
        "cost_reduction_fraction": result.cost_reduction_fraction,
        "edge_count": result.edge_count,
        "weighted_edge_count": result.weighted_edge_count,
        "method": result.method,
        "history": result.history,
        "risk_flags": result.risk_flags,
    }


def remap_circuit_to_order(qc_raw: QuantumCircuit, optimized_order: list[int]) -> QuantumCircuit:
    """
    Return a circuit whose qubit line `site` represents original qubit
    optimized_order[site].
    """
    qc = remove_measurements(qc_raw)
    if sorted(optimized_order) != list(range(qc.num_qubits)):
        raise ValueError("optimized_order must be a permutation of circuit qubits")
    original_to_site = {q: site for site, q in enumerate(optimized_order)}
    q2i = _qubit_map(qc)
    out = QuantumCircuit(qc.num_qubits)
    for inst in qc.data:
        op = inst.operation
        sites = [original_to_site[q2i[q]] for q in inst.qubits]
        out.append(op, sites)
    return out


def translate_ordered_bitstring_to_original(bitstring: str | None, optimized_order: list[int]) -> str | None:
    """
    Convert a Qiskit big-endian bitstring from optimized chain qubits back to
    original-circuit Qiskit big-endian order.
    """
    if bitstring is None:
        return None
    n = len(bitstring)
    if len(optimized_order) != n:
        return bitstring
    ordered_qubit_bits = list(reversed(bitstring))
    original_bits = ["0"] * n
    for site, original_q in enumerate(optimized_order):
        original_bits[original_q] = ordered_qubit_bits[site]
    return "".join(reversed(original_bits))

