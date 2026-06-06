"""
MPO compress-and-unswap with graph-ordering and tree-TNS diagnostics.

Drop-in replacement for mpo_compress_unswap in unswap.py.
Uses an *external layout map* strategy: the MPO tensor sites are never
physically permuted.  Instead, whenever local unswapping stalls, a new
qubit ordering is derived from the remaining interaction graph, and the
remaining circuit layers are re-transpiled (via rewire_layers + SABRE)
to the new target ordering.  The MPO sees gate qubits that already
correspond to its physical sites, so no MPO site permutation is needed.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np
from qiskit import QuantumCircuit
from qiskit_quimb import quimb_circuit
from quimb.tensor import Circuit

from circuit_mpo import apply_circuit, mpo_from_circuit
from graph_ordering import (
    build_interaction_graph,
    gate_aware_weight,
    rcm_ordering,
    refine_ordering_by_adjacent_swaps,
    refine_ordering_by_insert_moves,
    tree_tns_diagnostic,
    weighted_bandwidth_cost,
)
from unswap import (
    count_quantum_ops,
    rewire_layers,
    unswap,
)
from utils import elem_counts, get_tn_info, iter_layers, merge_gates, merge_layers

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    level=logging.INFO,
)


# ── Internal helpers ─────────────────────────────────────────────────

# rewire_layers(ls, perm) expects perm[pos] = qubit, i.e. the same "ordering"
# format that compute_graph_ordering returns.  It internally calls
# np.argsort(perm) to build the qubit relabelling map, so no inversion is needed
# here — just pass the ordering list directly.


def _graph_ordering_from_layers(
    layers_left: list,
    layers_right: list,
    n_qubits: int,
) -> dict[str, Any]:
    """
    Build interaction graph from remaining layers, compute best ordering
    (RCM vs tree DFS), and return a dict with the results.
    """
    combined = list(layers_left) + list(layers_right)
    ident = list(range(n_qubits))
    if not combined:
        return {"ordering": ident, "method": "identity", "cost_before": 0.0, "cost_after": 0.0, "improvement": 0.0, "blocks": []}

    qc_rem = merge_layers(combined) if len(combined) > 1 else combined[0]

    # Build graph once; nodes 0..N-1 correspond to current MPO chain positions
    G = build_interaction_graph(qc_rem, gate_weight_fn=gate_aware_weight)
    cost_before = weighted_bandwidth_cost(G, ident)

    if G.number_of_edges() == 0:
        return {"ordering": ident, "method": "identity", "cost_before": 0.0, "cost_after": 0.0, "improvement": 0.0, "blocks": []}

    # RCM ordering: ordering[pos] = chain_pos_that_should_be_at_pos
    rcm_order = rcm_ordering(G)
    rcm_order = refine_ordering_by_adjacent_swaps(G, rcm_order)
    rcm_order = refine_ordering_by_insert_moves(G, rcm_order)
    rcm_cost = weighted_bandwidth_cost(G, rcm_order)

    # Tree ordering
    tree_diag = tree_tns_diagnostic(G, b_max=4, eta=3.0)
    tree_order = tree_diag["tree_ordering"]
    tree_cost = tree_diag["tree_cost"]

    if rcm_cost <= tree_cost:
        best_order, best_cost, method = rcm_order, rcm_cost, "rcm"
    else:
        best_order, best_cost, method = tree_order, tree_cost, "tree"

    improvement = (cost_before - best_cost) / (cost_before + 1e-12)

    # Return the ordering directly — rewire_layers expects perm[pos]=qubit,
    # which is exactly the format compute_graph_ordering produces.
    return {
        "ordering": best_order,
        "method": method,
        "cost_before": cost_before,
        "cost_after": best_cost,
        "improvement": improvement,
        "blocks": [list(b) for b in tree_diag["blocks"]],
    }


# ── Main algorithm ───────────────────────────────────────────────────


def mpo_compress_unswap_graph(
    circuit: QuantumCircuit,
    max_bond: int = 8192,
    cutoff: float = 0.001,
    unswap_threshold: float = 1e6,
    early_stopping_gates: int = 100,
    center_ratio: float | int = 0.5,
    equal: bool = False,
    flip_freq: int | None = None,
    max_its: int = 20,
    to_backend=None,
    seed: int | None = None,
    hows: tuple = ("both", "left", "right"),
    mpo_core=None,
    sabre_trials: int = 10000,
    # Graph-ordering knobs
    graph_ordering_min_improvement: float = 0.02,
    graph_ordering_max_calls: int = 10,
):
    """
    Identical contract to mpo_compress_unswap(unswap.py) but adds:

    1. Initial graph ordering — computes a good MPO chain ordering from the
       full interaction graph before contraction starts.
    2. Stall-triggered dynamic graph reordering — when local unswapping
       produces zero improvements, rebuilds the interaction graph from
       remaining layers and proposes a new ordering.  The ordering is
       accepted only when it reduces the weighted bandwidth cost by at
       least graph_ordering_min_improvement (relative).
    3. Tree TNS diagnostic — at each reorder call, also computes a tree
       ordering (MST DFS) and picks whichever (RCM vs tree) is cheaper.
       Candidate qubit blocks are logged for future use.
    """
    q2c = lambda qc: quimb_circuit(qc.decompose("unitary"), Circuit, to_backend=to_backend)
    t0 = time.perf_counter()

    # ── Split circuit ─────────────────────────────────────────────────
    C = int(len(circuit) * center_ratio) if isinstance(center_ratio, float) else center_ratio
    circuit_left = merge_gates(circuit[:C], circuit.num_qubits).inverse()
    circuit_right = merge_gates(circuit[C:], circuit.num_qubits)
    for circ in (circuit_left, circuit_right):
        if "measure" not in circ.count_ops():
            circ.measure_all()

    layers_left = list(iter_layers(circuit_left))
    layers_right = list(iter_layers(circuit_right))

    T_U = count_quantum_ops(circuit)
    T_UL = count_quantum_ops(circuit_left)
    T_UR = count_quantum_ops(circuit_right)
    n_qubits = circuit.num_qubits
    logging.info(f"Total quantum ops: {T_U} = {T_UL} (left) + {T_UR} (right)")

    # ── Initial graph ordering ────────────────────────────────────────
    logging.info("[graph_ordering] Computing initial ordering from full circuit...")
    init_result = _graph_ordering_from_layers(layers_left, layers_right, n_qubits)
    logging.info(
        f"[graph_ordering] initial method={init_result['method']} "
        f"cost: {init_result['cost_before']:.2f} → {init_result['cost_after']:.2f} "
        f"(improvement: {init_result['improvement']:.3f})"
    )
    logging.info(f"[tree_diagnostic] initial candidate blocks: {init_result['blocks']}")

    use_init_perm = (
        init_result["ordering"]
        if init_result["improvement"] >= graph_ordering_min_improvement
        else list(range(n_qubits))
    )
    if init_result["improvement"] >= graph_ordering_min_improvement:
        logging.info(f"[graph_ordering] initial ordering accepted (method={init_result['method']})")
    else:
        logging.info("[graph_ordering] initial ordering skipped (insufficient improvement), using identity")
    init_graph_ordering_event = {
        "time": time.perf_counter() - t0,
        "stage": "graph_ordering",
        "phase": "initial",
        "call_num": -1,
        "method": init_result["method"],
        "bandwidth_cost_before": init_result["cost_before"],
        "bandwidth_cost_after": init_result["cost_after"],
        "improvement_ratio": init_result["improvement"],
        "accepted": init_result["improvement"] >= graph_ordering_min_improvement,
        "candidate_blocks": init_result["blocks"],
    }

    layers_left = rewire_layers(layers_left, use_init_perm, seed=seed, sabre_trials=sabre_trials)
    layers_right = rewire_layers(layers_right, use_init_perm, seed=seed, sabre_trials=sabre_trials)

    init_meas = layers_left[-2:]
    layers_left = layers_left[:-2]
    final_meas = layers_right[-2:]
    layers_right = layers_right[:-2]

    # ── Initialise MPO ────────────────────────────────────────────────
    ii_left = ii_right = 0
    do_left = False
    if mpo_core is None:
        mpo_core = mpo_from_circuit(q2c(QuantumCircuit(n_qubits)))
    logging.info("[start compressing] -> " + str(get_tn_info(mpo_core)))

    total_u = total_u_left = total_u_right = current_u = 0
    graph_ordering_calls = 0
    stats_data: list[dict] = [init_graph_ordering_event]

    # ── Main absorption loop ──────────────────────────────────────────
    while ii_left < len(layers_left) or ii_right < len(layers_right):

        # Try absorbing one layer from each side
        if ii_left < len(layers_left):
            try:
                mpo_left = apply_circuit(
                    mpo_core, q2c(layers_left[ii_left].inverse()),
                    side="right", max_bond=max_bond, cutoff=cutoff,
                )
            except KeyboardInterrupt:
                break
            counts_left = elem_counts(mpo_left)
        else:
            mpo_left = None
            counts_left = 1e20

        if ii_right < len(layers_right):
            try:
                mpo_right = apply_circuit(
                    mpo_core, q2c(layers_right[ii_right]),
                    side="left", max_bond=max_bond, cutoff=cutoff,
                )
            except KeyboardInterrupt:
                break
            counts_right = elem_counts(mpo_right)
        else:
            mpo_right = None
            counts_right = 1e20

        # Decide which side to absorb
        if flip_freq is None:
            do_left = counts_left < counts_right
        else:
            if mpo_left is None:
                do_left = False
            elif mpo_right is None:
                do_left = True
            elif (ii_left + ii_right) % flip_freq == 0:
                do_left = not do_left

        chosen_count = counts_left if do_left else counts_right

        if chosen_count < unswap_threshold:
            # ── Accept absorption ─────────────────────────────────────
            if do_left:
                mpo_core = mpo_left
                new_us = count_quantum_ops(layers_left[ii_left])
                new_swaps = layers_left[ii_left].count_ops().get("swap", 0)
                total_u += new_us; current_u += new_us; total_u_left += new_us
                side_tag = "L"; ii_left += 1
            else:
                mpo_core = mpo_right
                new_us = count_quantum_ops(layers_right[ii_right])
                new_swaps = layers_right[ii_right].count_ops().get("swap", 0)
                total_u += new_us; current_u += new_us; total_u_right += new_us
                side_tag = "R"; ii_right += 1

            tag = f"[{ii_right}R/{len(layers_right)}]" if side_tag == "R" else f"[{ii_left}L/{len(layers_left)}]"
            logging.info(
                tag + f"(swap:{new_swaps} u:{new_us} | t_u:{total_u}/{T_U}) -> "
                + str(get_tn_info(mpo_core))
            )
            stats_data.append({
                "time": time.perf_counter() - t0,
                "stage": "absorbing",
                "absorb_side": side_tag,
                "it_left": ii_left, "it_right": ii_right,
                "layers_left": len(layers_left), "layers_right": len(layers_right),
                "u_consumed_total_left": total_u_left,
                "u_consumed_total_right": total_u_right,
                "u_consumed_total": total_u,
                "swap_consumed": new_swaps, "u_consumed": new_us,
                **get_tn_info(mpo_core),
            })

        else:
            # ── Both sides too large: local unswap first ──────────────
            try:
                mpo_core, (perm_l, perm_r), unswap_stats = unswap(
                    mpo_core, hows=hows, max_bond=max_bond, cutoff=cutoff,
                    max_its=max_its, equal=equal, to_backend=to_backend, t0=t0,
                )
                stats_data += unswap_stats
            except KeyboardInterrupt:
                break

            unswap_improvements = sum(s.get("new_swaps", 0) for s in unswap_stats)
            logging.info(f"[unswap] improvements={unswap_improvements}")

            # Use unswap permutation by default; override with graph perm if stalled
            rewire_perm_l, rewire_perm_r = perm_l, perm_r

            if unswap_improvements == 0 and graph_ordering_calls < graph_ordering_max_calls:
                rem_l = layers_left[ii_left:] if ii_left < len(layers_left) else []
                rem_r = layers_right[ii_right:] if ii_right < len(layers_right) else []

                if rem_l or rem_r:
                    logging.info(
                        f"[graph_ordering] Local unswap stalled. "
                        f"Computing graph ordering (call {graph_ordering_calls})..."
                    )
                    gr = _graph_ordering_from_layers(rem_l, rem_r, n_qubits)
                    logging.info(
                        f"[graph_ordering] call={graph_ordering_calls} "
                        f"method={gr['method']} "
                        f"cost: {gr['cost_before']:.2f} → {gr['cost_after']:.2f} "
                        f"(improvement: {gr['improvement']:.3f})"
                    )
                    logging.info(f"[tree_diagnostic] candidate blocks: {gr['blocks']}")

                    accepted = gr["improvement"] >= graph_ordering_min_improvement
                    stats_data.append({
                        "time": time.perf_counter() - t0,
                        "stage": "graph_ordering",
                        "call_num": graph_ordering_calls,
                        "method": gr["method"],
                        "bandwidth_cost_before": gr["cost_before"],
                        "bandwidth_cost_after": gr["cost_after"],
                        "improvement_ratio": gr["improvement"],
                        "accepted": accepted,
                        "candidate_blocks": gr["blocks"],
                        **get_tn_info(mpo_core),
                    })

                    if accepted:
                        rewire_perm_l = gr["ordering"]
                        rewire_perm_r = gr["ordering"]
                        graph_ordering_calls += 1
                        logging.info(
                            f"[graph_ordering] Accepted (method={gr['method']}). "
                            f"Rewiring remaining layers."
                        )
                    else:
                        logging.info("[graph_ordering] Rejected (insufficient improvement).")

            # ── Rewire remaining layers with chosen permutation ───────
            if ii_left < len(layers_left):
                layers_left = rewire_layers(
                    layers_left[ii_left:] + init_meas,
                    rewire_perm_l, seed=seed, sabre_trials=sabre_trials,
                )
                init_meas = layers_left[-2:]
                layers_left = layers_left[:-2]
            else:
                layers_left = []

            if ii_right < len(layers_right):
                layers_right = rewire_layers(
                    layers_right[ii_right:] + final_meas,
                    rewire_perm_r, seed=seed, sabre_trials=sabre_trials,
                )
                final_meas = layers_right[-2:]
                layers_right = layers_right[:-2]
            else:
                layers_right = []

            ii_left = ii_right = 0
            current_u = 0

            if (T_U - total_u) <= early_stopping_gates:
                break

    # ── Collect leftover layers ───────────────────────────────────────
    layers_left = (layers_left[ii_left:] if ii_left < len(layers_left) else []) + init_meas
    layers_right = (layers_right[ii_right:] if ii_right < len(layers_right) else []) + final_meas

    logging.info(
        f"[end compressing](left:{len(layers_left)}, right:{len(layers_right)}) -> "
        + str(get_tn_info(mpo_core))
    )
    logging.info(f"[graph_ordering] total accepted calls: {graph_ordering_calls}")

    return mpo_core, layers_left, layers_right, stats_data
