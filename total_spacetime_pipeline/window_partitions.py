"""Per-window vertical partitions, orderings, and migration penalties."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx

from .compat import ensure_repo_paths
from .graph_ordering import build_weighted_twoq_graph, optimize_qubit_order, ordering_cost

ensure_repo_paths()

from circuit_tools import remove_measurements
from layer_tools import greedy_layerize
from params import SpacetimeParams
from plan_types import GateInfo
from window_tools import make_fixed_layer_windows


@dataclass
class WindowPartition:
    """A vertical partition and qubit chain order for one temporal window."""
    window_index: int
    layer_start: int
    layer_end: int
    A: set[int]
    B: set[int]
    qubit_order: list[int]
    cut_weight: float
    ordering_cost: float
    risk_flags: list[str]


@dataclass
class PartitionMigration:
    """Explicit migration between consecutive window partition/order choices."""
    from_window: int
    to_window: int
    side_changes: list[int]
    order_permutation_old_site_to_new_site: list[int]
    position_l1: int
    transition_cost: float
    risk_flags: list[str]


@dataclass
class WindowPartitionPlan:
    """Per-window partition plan with explicit transition costs."""
    partitions: list[WindowPartition]
    migrations: list[PartitionMigration]
    total_cut_weight: float
    total_ordering_cost: float
    total_transition_cost: float
    total_score: float
    risk_flags: list[str]


def _window_circuit(gates: list[GateInfo], n_qubits: int):
    from qiskit import QuantumCircuit

    circ = QuantumCircuit(n_qubits)
    for g in sorted(gates, key=lambda x: x.time):
        circ.append(g.operation, list(g.qubits))
    return circ


def _weighted_cut(G: nx.Graph, A: set[int], B: set[int]) -> float:
    return float(sum(
        d.get("weight", 1.0)
        for u, v, d in G.edges(data=True)
        if (u in A) != (v in A)
    ))


def _balanced_partition_from_order(order: list[int]) -> tuple[set[int], set[int]]:
    half = max(1, len(order) // 2)
    return set(order[:half]), set(order[half:])


def _partition_window_graph(G: nx.Graph, order: list[int], seed: int | None) -> tuple[set[int], set[int], list[str]]:
    flags = ["per_window_partition"]
    if G.number_of_edges() == 0 or G.number_of_nodes() < 2:
        A, B = _balanced_partition_from_order(order)
        flags.append("fallback_order_bisection_no_edges")
        return A, B, flags
    try:
        A, B = nx.community.kernighan_lin_bisection(G, weight="weight", seed=seed)
        return set(A), set(B), flags
    except Exception:
        A, B = _balanced_partition_from_order(order)
        flags.append("fallback_order_bisection")
        return A, B, flags


def _align_partition_labels(
    prev_A: set[int],
    prev_B: set[int],
    A: set[int],
    B: set[int],
) -> tuple[set[int], set[int]]:
    unchanged = len(prev_A & A) + len(prev_B & B)
    flipped = len(prev_A & B) + len(prev_B & A)
    return (B, A) if flipped > unchanged else (A, B)


def _migration(
    prev: WindowPartition,
    cur: WindowPartition,
    *,
    side_change_weight: float,
    position_change_weight: float,
) -> PartitionMigration:
    A, B = _align_partition_labels(prev.A, prev.B, cur.A, cur.B)
    cur.A = A
    cur.B = B

    side_changes = sorted(q for q in prev.A | prev.B if (q in prev.A) != (q in cur.A))
    cur_pos = {q: i for i, q in enumerate(cur.qubit_order)}
    perm = [cur_pos[q] for q in prev.qubit_order]
    position_l1 = sum(abs(i - new_i) for i, new_i in enumerate(perm))
    cost = side_change_weight * len(side_changes) + position_change_weight * position_l1
    flags = ["explicit_partition_migration"]
    if side_changes:
        flags.append("qubits_change_partition_side")
    if position_l1:
        flags.append("qubit_chain_order_changes")
    return PartitionMigration(
        from_window=prev.window_index,
        to_window=cur.window_index,
        side_changes=side_changes,
        order_permutation_old_site_to_new_site=perm,
        position_l1=int(position_l1),
        transition_cost=float(cost),
        risk_flags=flags,
    )


def build_window_partition_plan(
    qc_raw,
    params: SpacetimeParams,
    *,
    window_size: int | None = None,
    side_change_weight: float = 4.0,
    position_change_weight: float = 0.1,
) -> WindowPartitionPlan:
    """
    Build per-window partitions and explicit migration penalties.

    The migrations are a physical warning/plan: applying changing partitions in
    an executor requires explicit permutation or tensor reindexing between
    windows, never silent relabeling.
    """
    qc = remove_measurements(qc_raw)
    layers = greedy_layerize(qc)
    ws = window_size or params.window_sizes[0]
    windows = make_fixed_layer_windows(layers, ws)
    partitions: list[WindowPartition] = []

    for w in windows:
        wc = _window_circuit(w.gates, qc.num_qubits)
        order_result = optimize_qubit_order(wc, params)
        G = build_weighted_twoq_graph(wc, params)
        A, B, flags = _partition_window_graph(G, order_result.optimized_order, params.seed)
        cut = _weighted_cut(G, A, B)
        partitions.append(WindowPartition(
            window_index=w.index,
            layer_start=w.layer_start,
            layer_end=w.layer_end,
            A=A,
            B=B,
            qubit_order=order_result.optimized_order,
            cut_weight=cut,
            ordering_cost=ordering_cost(G, order_result.optimized_order),
            risk_flags=flags + order_result.risk_flags,
        ))

    migrations = [
        _migration(
            partitions[i],
            partitions[i + 1],
            side_change_weight=side_change_weight,
            position_change_weight=position_change_weight,
        )
        for i in range(len(partitions) - 1)
    ]
    cut_total = sum(p.cut_weight for p in partitions)
    order_total = sum(p.ordering_cost for p in partitions)
    transition_total = sum(m.transition_cost for m in migrations)
    risk_flags = ["per_window_partition_plan", "transition_penalty_included"]
    if any(m.side_changes for m in migrations):
        risk_flags.append("partition_membership_changes_over_time")
    if any(m.position_l1 for m in migrations):
        risk_flags.append("window_dependent_qubit_order")

    return WindowPartitionPlan(
        partitions=partitions,
        migrations=migrations,
        total_cut_weight=float(cut_total),
        total_ordering_cost=float(order_total),
        total_transition_cost=float(transition_total),
        total_score=float(cut_total + order_total + transition_total),
        risk_flags=risk_flags,
    )


def window_partition_plan_to_dict(plan: WindowPartitionPlan) -> dict[str, Any]:
    """JSON-friendly WindowPartitionPlan."""
    return {
        "partitions": [
            {
                "window_index": p.window_index,
                "layer_start": p.layer_start,
                "layer_end": p.layer_end,
                "A": sorted(p.A),
                "B": sorted(p.B),
                "qubit_order": p.qubit_order,
                "cut_weight": p.cut_weight,
                "ordering_cost": p.ordering_cost,
                "risk_flags": p.risk_flags,
            }
            for p in plan.partitions
        ],
        "migrations": [
            {
                "from_window": m.from_window,
                "to_window": m.to_window,
                "side_changes": m.side_changes,
                "order_permutation_old_site_to_new_site": m.order_permutation_old_site_to_new_site,
                "position_l1": m.position_l1,
                "transition_cost": m.transition_cost,
                "risk_flags": m.risk_flags,
            }
            for m in plan.migrations
        ],
        "total_cut_weight": plan.total_cut_weight,
        "total_ordering_cost": plan.total_ordering_cost,
        "total_transition_cost": plan.total_transition_cost,
        "total_score": plan.total_score,
        "risk_flags": plan.risk_flags,
    }

