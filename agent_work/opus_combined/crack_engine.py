"""Robust convergence-driven MPO compress-unswap driver.

Based on unswap_graph.mpo_compress_unswap_graph (Kremer-Dupuis + graph ordering)
but fixes the two ways the reference loop fails on hard obfuscated circuits:

  1. SPIN: when both sides exceed the soft element budget and neither local
     unswap nor graph reordering can reduce it, the reference loop rewires with
     an identity permutation, resets, and retries forever.  We add
     *force-absorb-on-stall*: after `stall_patience` unproductive unswap rounds
     we absorb the cheaper side anyway (bounded by max_bond), guaranteeing the
     layer count strictly decreases -> the loop always terminates with
     remaining_layers -> 0 (unless the time budget trips first).

  2. NO TIME GATE: we add a wall-clock `time_budget`; on expiry we stop and
     return the best-effort MPO plus whatever layers remain, flagged
     converged=False so the readout is treated as low-confidence.

Returns (mpo_core, layers_left, layers_right, stats, info) where info carries
converged / remaining / forced_absorptions / max_bond_seen.
"""
from __future__ import annotations
import logging, time
import numpy as np
from qiskit import QuantumCircuit
from qiskit_quimb import quimb_circuit
from quimb.tensor import Circuit

from circuit_mpo import apply_circuit, mpo_from_circuit
from unswap import count_quantum_ops, rewire_layers, unswap
from utils import elem_counts, get_tn_info, iter_layers, merge_gates, merge_layers
from graph_ordering import (build_interaction_graph, gate_aware_weight, rcm_ordering,
                            refine_ordering_by_adjacent_swaps, refine_ordering_by_insert_moves)

log = logging.getLogger("crack_engine")


def _safe_bandwidth(G, ordering):
    pos = {q: i for i, q in enumerate(ordering)}
    c = 0.0
    for i, j, data in G.edges(data=True):
        if i in pos and j in pos:
            c += data.get("weight", 1.0) * abs(pos[i] - pos[j])
    return c


def _graph_order(layers_left, layers_right, n):
    """Robust RCM-based ordering from remaining layers' interaction graph.

    Avoids the reference tree-DFS ordering, which crashes on disconnected
    interaction graphs (its DFS covers only one component).  Returns
    {ordering (perm of range(n)), method, improvement}.
    """
    ident = list(range(n))
    combined = list(layers_left) + list(layers_right)
    if not combined:
        return {"ordering": ident, "method": "identity", "improvement": 0.0}
    qc = merge_layers(combined) if len(combined) > 1 else combined[0]
    G = build_interaction_graph(qc, gate_weight_fn=gate_aware_weight)
    if G.number_of_edges() == 0:
        return {"ordering": ident, "method": "identity", "improvement": 0.0}
    for q in range(n):           # ensure all qubits present (incl. isolated)
        if q not in G:
            G.add_node(q)
    order = list(rcm_ordering(G))          # handles disconnected graphs
    order = refine_ordering_by_adjacent_swaps(G, order)
    order = refine_ordering_by_insert_moves(G, order)
    if sorted(order) != ident:             # safety: must be a full permutation
        return {"ordering": ident, "method": "identity", "improvement": 0.0}
    cost_id = _safe_bandwidth(G, ident)
    cost_new = _safe_bandwidth(G, order)
    improvement = (cost_id - cost_new) / (cost_id + 1e-12)
    return {"ordering": order, "method": "rcm", "improvement": improvement}


def compress_to_convergence(
    circuit: QuantumCircuit,
    max_bond: int = 8192,
    cutoff: float = 0.002,
    soft_elems: float = 1e6,
    center_ratio=0.5,
    max_its: int = 16,
    seed: int | None = 123,
    to_backend=None,
    sabre_trials: int = 1000,
    hows=("both", "left", "right"),
    time_budget: float | None = None,
    use_graph: bool = True,
    graph_min_improve: float = 0.02,
    graph_max_calls: int = 30,
    stall_patience: int = 2,
    force_batch: int = 8,
    equal: bool = False,
):
    q2c = lambda qc: quimb_circuit(qc.decompose("unitary"), Circuit, to_backend=to_backend)
    t0 = time.perf_counter()

    C = int(len(circuit) * center_ratio) if isinstance(center_ratio, float) else center_ratio
    circuit_left = merge_gates(circuit[:C], circuit.num_qubits).inverse()
    circuit_right = merge_gates(circuit[C:], circuit.num_qubits)
    for circ in (circuit_left, circuit_right):
        if "measure" not in circ.count_ops():
            circ.measure_all()

    layers_left = list(iter_layers(circuit_left))
    layers_right = list(iter_layers(circuit_right))
    n = circuit.num_qubits
    T_U = count_quantum_ops(circuit)
    log.info(f"[init] T_U={T_U} layers_left={len(layers_left)} layers_right={len(layers_right)}")

    # initial graph ordering
    if use_graph:
        init = _graph_order(layers_left, layers_right, n)
        perm0 = init["ordering"] if init["improvement"] >= graph_min_improve else list(range(n))
        log.info(f"[init graph] method={init['method']} improve={init['improvement']:.3f} "
                 f"{'ACCEPT' if perm0 != list(range(n)) else 'identity'}")
    else:
        perm0 = list(range(n))
    layers_left = rewire_layers(layers_left, perm0, seed=seed, sabre_trials=sabre_trials)
    layers_right = rewire_layers(layers_right, perm0, seed=seed, sabre_trials=sabre_trials)
    init_meas = layers_left[-2:]; layers_left = layers_left[:-2]
    final_meas = layers_right[-2:]; layers_right = layers_right[:-2]

    mpo_core = mpo_from_circuit(q2c(QuantumCircuit(n)))
    ii_left = ii_right = 0
    total_u = 0
    unswap_since_absorb = 0   # consecutive unswap cycles with NO absorption progress
    force_remaining = 0       # remaining layers in the current force-absorb batch
    forced = 0
    graph_calls = 0
    max_bond_seen = 1
    stats = []
    stopped_reason = "complete"

    while ii_left < len(layers_left) or ii_right < len(layers_right):
        if time_budget is not None and (time.perf_counter() - t0) > time_budget:
            stopped_reason = "time_budget"
            log.info(f"[stop] time budget {time_budget}s exceeded")
            break

        # try one layer from each side
        if ii_left < len(layers_left):
            try:
                mpo_left = apply_circuit(mpo_core, q2c(layers_left[ii_left].inverse()),
                                         side="right", max_bond=max_bond, cutoff=cutoff)
            except KeyboardInterrupt:
                stopped_reason = "interrupt"; break
            counts_left = elem_counts(mpo_left)
        else:
            mpo_left, counts_left = None, 1e20

        if ii_right < len(layers_right):
            try:
                mpo_right = apply_circuit(mpo_core, q2c(layers_right[ii_right]),
                                          side="left", max_bond=max_bond, cutoff=cutoff)
            except KeyboardInterrupt:
                stopped_reason = "interrupt"; break
            counts_right = elem_counts(mpo_right)
        else:
            mpo_right, counts_right = None, 1e20

        do_left = counts_left < counts_right
        chosen_count = counts_left if do_left else counts_right
        natural = chosen_count < soft_elems
        # When unswap fails to enable absorption for `stall_patience` cycles, enter a
        # force-absorb batch: absorb `force_batch` layers unconditionally (bounded by
        # max_bond) to push through the high-entanglement region instead of spinning.
        if (not natural) and unswap_since_absorb >= stall_patience and force_remaining == 0:
            force_remaining = force_batch
        force = (not natural) and force_remaining > 0

        if natural or force:
            # ---- absorb chosen side ----
            if do_left:
                mpo_core = mpo_left
                total_u += count_quantum_ops(layers_left[ii_left]); ii_left += 1; tag = "L"
            else:
                mpo_core = mpo_right
                total_u += count_quantum_ops(layers_right[ii_right]); ii_right += 1; tag = "R"
            mb = mpo_core.max_bond(); max_bond_seen = max(max_bond_seen, mb)
            if natural:
                force_remaining = 0
            else:
                forced += 1; force_remaining -= 1
                log.info(f"[FORCE-ABSORB {tag}] left={force_remaining} bond={mb} "
                         f"elems={chosen_count:.2e} t_u={total_u}/{T_U}")
            unswap_since_absorb = 0
            stats.append({"t": time.perf_counter() - t0, "stage": "absorb", "side": tag,
                          "il": ii_left, "ir": ii_right, "forced": force,
                          "t_u": total_u, **get_tn_info(mpo_core)})
        else:
            # ---- both too big: unswap, and graph-reorder if absorption is stalled ----
            try:
                mpo_core, (perm_l, perm_r), us_stats = unswap(
                    mpo_core, hows=hows, max_bond=max_bond, cutoff=cutoff,
                    max_its=max_its, equal=equal, to_backend=to_backend, t0=t0)
            except KeyboardInterrupt:
                stopped_reason = "interrupt"; break
            improvements = sum(s.get("new_swaps", 0) for s in us_stats)
            max_bond_seen = max(max_bond_seen, mpo_core.max_bond())
            rewire_l, rewire_r = perm_l, perm_r

            # Trigger graph reorder when absorption is stalled (not just when unswap
            # found nothing) -- the spin has improvements>0 but no absorb progress.
            if use_graph and unswap_since_absorb >= 1 and graph_calls < graph_max_calls:
                rem_l = layers_left[ii_left:] if ii_left < len(layers_left) else []
                rem_r = layers_right[ii_right:] if ii_right < len(layers_right) else []
                if rem_l or rem_r:
                    gr = _graph_order(rem_l, rem_r, n)
                    log.info(f"[graph] call={graph_calls} method={gr['method']} improve={gr['improvement']:.3f}")
                    if gr["improvement"] >= graph_min_improve:
                        rewire_l = rewire_r = gr["ordering"]
                        graph_calls += 1

            unswap_since_absorb += 1
            log.info(f"[unswap] improvements={improvements} no_absorb_cycles={unswap_since_absorb} "
                     f"bond={mpo_core.max_bond()}")

            # rewire remaining + reset
            if ii_left < len(layers_left):
                layers_left = rewire_layers(layers_left[ii_left:] + init_meas, rewire_l,
                                            seed=seed, sabre_trials=sabre_trials)
                init_meas = layers_left[-2:]; layers_left = layers_left[:-2]
            else:
                layers_left = []
            if ii_right < len(layers_right):
                layers_right = rewire_layers(layers_right[ii_right:] + final_meas, rewire_r,
                                             seed=seed, sabre_trials=sabre_trials)
                final_meas = layers_right[-2:]; layers_right = layers_right[:-2]
            else:
                layers_right = []
            ii_left = ii_right = 0

    layers_left = (layers_left[ii_left:] if ii_left < len(layers_left) else []) + init_meas
    layers_right = (layers_right[ii_right:] if ii_right < len(layers_right) else []) + final_meas
    rem = max(0, len(layers_left) - 2) + max(0, len(layers_right) - 2)
    info = {
        "converged": rem == 0 and stopped_reason == "complete",
        "stopped_reason": stopped_reason,
        "remaining_layers": rem,
        "forced_absorptions": forced,
        "graph_calls": graph_calls,
        "max_bond_seen": int(max_bond_seen),
        "final_max_bond": int(mpo_core.max_bond()),
        "compress_seconds": round(time.perf_counter() - t0, 1),
    }
    log.info(f"[done] {info}")
    return mpo_core, layers_left, layers_right, stats, info
