"""Spawned MPO bridge contraction for chronological spacetime windows."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from .boundary_slicing import _is_boundary, build_boundary_sliced_events
from .compat import ensure_repo_paths
from .window_partitions import WindowPartitionPlan

ensure_repo_paths()

from circuit_tools import remove_measurements
from layer_tools import greedy_layerize
from plan_types import GateInfo
from temporal_global_executor import PeakExtractionResult, extract_peak_from_mps
from temporal_pipeline import exact_peak_bitstring


@dataclass
class BridgeBlockStats:
    """Telemetry for one spawned bridge MPO or boundary event."""
    kind: str
    window_index: int
    start_time: int | None
    end_time: int | None
    n_gates: int
    n_boundary_gates: int
    n_local_gates: int
    max_bond_before: int
    max_bond_after: int
    current_order: list[int]
    risk_flags: list[str]


@dataclass
class MigrationStats:
    """Telemetry for an explicit MPS site-order migration."""
    from_window: int
    to_window: int
    source_order: list[int]
    target_order: list[int]
    adjacent_swaps: list[tuple[int, int]]
    max_bond_before: int
    max_bond_after: int
    transition_cost: float
    risk_flags: list[str]


@dataclass
class SpawnedBridgeExecutionResult:
    """Result of chronological spawned bridge MPO contraction."""
    n_qubits: int
    n_layers: int
    n_gates: int
    final_site_to_qubit: list[int]
    final_max_bond: int
    peak_extraction: PeakExtractionResult | None
    bitstring_working_order: str | None
    exact_peak_bitstring: str | None
    exact_peak_probability: float | None
    exact_match: bool | None
    block_stats: list[BridgeBlockStats]
    migration_stats: list[MigrationStats]
    risk_flags: list[str]
    wall_seconds: float


def _empty_mps(n_qubits: int, *, to_backend=None):
    from qiskit_quimb import quimb_circuit
    from quimb.tensor import CircuitMPS

    return quimb_circuit(
        QuantumCircuit(n_qubits),
        quimb_circuit_class=CircuitMPS,
        to_backend=to_backend,
    ).psi


def _bridge_mpo_from_circuit(circ: QuantumCircuit, *, to_backend=None):
    from qiskit_quimb import quimb_circuit
    from quimb.tensor import Circuit
    from circuit_mpo import mpo_from_circuit

    q2c = lambda qc: quimb_circuit(qc.decompose("unitary"), Circuit, to_backend=to_backend)
    return mpo_from_circuit(q2c(circ))


def _gate_circuit_in_current_order(
    gates: list[GateInfo],
    n_qubits: int,
    current_order: list[int],
) -> QuantumCircuit:
    qubit_to_site = {q: i for i, q in enumerate(current_order)}
    circ = QuantumCircuit(n_qubits)
    for g in sorted(gates, key=lambda x: x.time):
        if not all(q in qubit_to_site for q in g.qubits):
            continue
        circ.append(g.operation, [qubit_to_site[q] for q in g.qubits])
    return circ


def _array_for_mps_backend(array: np.ndarray, mps):
    try:
        import torch
    except Exception:
        return array

    for tensor in mps:
        data = tensor.data
        if isinstance(data, torch.Tensor):
            return torch.as_tensor(array, dtype=data.dtype, device=data.device)
    return array


def _apply_gate_to_mps(mps, gate: GateInfo, current_order: list[int], *, max_bond: int, cutoff: float):
    qubit_to_site = {q: i for i, q in enumerate(current_order)}
    sites = tuple(qubit_to_site[q] for q in gate.qubits)
    G = _array_for_mps_backend(np.array(Operator(gate.operation).data, dtype=complex), mps)
    if len(sites) == 1:
        return mps.gate(
            G.reshape(2, 2),
            sites[0],
            contract=True,
            max_bond=max_bond,
            cutoff=cutoff,
        )
    if len(sites) == 2:
        G4 = G.reshape(2, 2, 2, 2)
        i, j = sites
        out = mps.copy()
        if abs(i - j) == 1:
            out.gate_(
                G4,
                sites,
                contract="swap+split",
                max_bond=max_bond,
                cutoff=cutoff,
            )
        else:
            out.gate_with_auto_swap_(
                G4,
                sites,
                max_bond=max_bond,
                cutoff=cutoff,
            )
        return out
    raise ValueError("only one- and two-qubit gates are supported in bridge executor")


def _migrate_mps_order(
    mps,
    current_order: list[int],
    target_order: list[int],
    *,
    max_bond: int,
    cutoff: float,
) -> tuple[Any, list[int], list[tuple[int, int]]]:
    """
    Change the MPS site ordering by adjacent site swaps.

    The state is migrated together with the site-to-qubit map. This is a
    representation/order transition for the executor, not an untracked circuit
    rewrite.
    """
    if sorted(current_order) != sorted(target_order):
        raise ValueError("target_order must contain the same qubits as current_order")
    out = mps.copy()
    order = list(current_order)
    swaps: list[tuple[int, int]] = []
    for target_site, q in enumerate(target_order):
        pos = order.index(q)
        while pos > target_site:
            out.swap_sites_with_compress_(
                pos - 1,
                pos,
                max_bond=max_bond,
                cutoff=cutoff,
            )
            order[pos - 1], order[pos] = order[pos], order[pos - 1]
            swaps.append((pos - 1, pos))
            pos -= 1
    return out, order, swaps


def _gates_for_window(layers: list[list[GateInfo]], layer_start: int, layer_end: int) -> list[GateInfo]:
    gates: list[GateInfo] = []
    for li in range(max(0, layer_start), min(len(layers), layer_end + 1)):
        gates.extend(layers[li])
    return sorted(gates, key=lambda g: g.time)


def _apply_spawned_bridge_block(
    mps,
    gates: list[GateInfo],
    current_order: list[int],
    *,
    n_qubits: int,
    max_bond: int,
    cutoff: float,
    to_backend=None,
):
    if not gates:
        return mps
    from circuit_mpo import stable_apply_operator

    circ = _gate_circuit_in_current_order(gates, n_qubits, current_order)
    mpo = _bridge_mpo_from_circuit(circ, to_backend=to_backend)
    return stable_apply_operator(
        mpo,
        mps,
        compress=True,
        max_bond=max_bond,
        cutoff=cutoff,
    )


def run_spawned_bridge_contraction(
    qc_raw,
    partition_plan: WindowPartitionPlan,
    params,
    *,
    max_bond: int | None = None,
    cutoff: float | None = None,
    peak_num_samples: int = 0,
    peak_sample_top_k: int = 32,
    refine_bitflips: bool = True,
    bitflip_rounds: int = 2,
    exact_validate: bool = False,
    max_exact_qubits: int = 8,
    to_backend=None,
) -> SpawnedBridgeExecutionResult:
    """
    Execute spacetime windows with spawned local bridge MPOs and chronological
    boundary events.

    For each window:
      1. migrate MPS chain to the window's qubit order,
      2. split the window into local blocks and boundary gates,
      3. apply local blocks as spawned MPOs,
      4. apply boundary gates immediately in their original time order.
    """
    t0 = time.perf_counter()
    qc = remove_measurements(qc_raw)
    layers = greedy_layerize(qc)
    mb = max_bond if max_bond is not None else params.max_bond
    co = cutoff if cutoff is not None else params.cutoff_final
    risk_flags = [
        "spawned_bridge_mpo_contraction",
        "chronological_boundary_sliced_execution",
        "window_dependent_partition_execution",
        "explicit_partition_migration",
    ]

    if not partition_plan.partitions:
        return SpawnedBridgeExecutionResult(
            n_qubits=qc.num_qubits,
            n_layers=len(layers),
            n_gates=qc.size(),
            final_site_to_qubit=list(range(qc.num_qubits)),
            final_max_bond=1,
            peak_extraction=None,
            bitstring_working_order=None,
            exact_peak_bitstring=None,
            exact_peak_probability=None,
            exact_match=None,
            block_stats=[],
            migration_stats=[],
            risk_flags=risk_flags + ["no_window_partitions"],
            wall_seconds=time.perf_counter() - t0,
        )

    mps = _empty_mps(qc.num_qubits, to_backend=to_backend)
    current_order = list(range(qc.num_qubits))
    block_stats: list[BridgeBlockStats] = []
    migration_stats: list[MigrationStats] = []

    for widx, part in enumerate(partition_plan.partitions):
        before_migration = int(mps.max_bond())
        mps, migrated_order, swaps = _migrate_mps_order(
            mps,
            current_order,
            part.qubit_order,
            max_bond=mb,
            cutoff=co,
        )
        if swaps or current_order != migrated_order:
            transition_cost = 0.0
            if widx > 0 and widx - 1 < len(partition_plan.migrations):
                transition_cost = partition_plan.migrations[widx - 1].transition_cost
            migration_stats.append(MigrationStats(
                from_window=max(0, widx - 1),
                to_window=widx,
                source_order=current_order,
                target_order=migrated_order,
                adjacent_swaps=swaps,
                max_bond_before=before_migration,
                max_bond_after=int(mps.max_bond()),
                transition_cost=float(transition_cost),
                risk_flags=["mps_site_order_migration"],
            ))
        current_order = migrated_order

        gates = _gates_for_window(layers, part.layer_start, part.layer_end)
        events = build_boundary_sliced_events(gates, set(part.A), set(part.B))
        for event in events:
            before = int(mps.max_bond())
            if event["kind"] == "local_block":
                local_gates = list(event["gates"])
                mps = _apply_spawned_bridge_block(
                    mps,
                    local_gates,
                    current_order,
                    n_qubits=qc.num_qubits,
                    max_bond=mb,
                    cutoff=co,
                    to_backend=to_backend,
                )
                block_stats.append(BridgeBlockStats(
                    kind="spawned_local_bridge_mpo",
                    window_index=part.window_index,
                    start_time=event["start_time"],
                    end_time=event["end_time"],
                    n_gates=len(local_gates),
                    n_boundary_gates=0,
                    n_local_gates=len(local_gates),
                    max_bond_before=before,
                    max_bond_after=int(mps.max_bond()),
                    current_order=list(current_order),
                    risk_flags=["spawned_mpo_bridge"],
                ))
            elif event["kind"] == "boundary_gate":
                gate = event["gate"]
                mps = _apply_gate_to_mps(
                    mps,
                    gate,
                    current_order,
                    max_bond=mb,
                    cutoff=co,
                )
                block_stats.append(BridgeBlockStats(
                    kind="chronological_boundary_gate",
                    window_index=part.window_index,
                    start_time=gate.time,
                    end_time=gate.time,
                    n_gates=1,
                    n_boundary_gates=1,
                    n_local_gates=0,
                    max_bond_before=before,
                    max_bond_after=int(mps.max_bond()),
                    current_order=list(current_order),
                    risk_flags=["boundary_applied_in_time_order"],
                ))
            else:
                raise ValueError(f"unknown boundary-sliced event kind: {event['kind']}")

    peak, _p0s = extract_peak_from_mps(
        mps,
        current_order,
        num_samples=peak_num_samples,
        sample_top_k=peak_sample_top_k,
        refine_bitflips=refine_bitflips,
        bitflip_rounds=bitflip_rounds,
    )
    exact_bits = None
    exact_prob = None
    exact_match = None
    if exact_validate:
        if qc.num_qubits <= max_exact_qubits:
            exact_bits, exact_prob = exact_peak_bitstring(qc)
            exact_match = peak.best_original_order == exact_bits
        else:
            risk_flags.append("exact_validation_qubit_limit_exceeded")

    return SpawnedBridgeExecutionResult(
        n_qubits=qc.num_qubits,
        n_layers=len(layers),
        n_gates=qc.size(),
        final_site_to_qubit=list(current_order),
        final_max_bond=int(mps.max_bond()),
        peak_extraction=peak,
        bitstring_working_order=peak.best_original_order,
        exact_peak_bitstring=exact_bits,
        exact_peak_probability=exact_prob,
        exact_match=exact_match,
        block_stats=block_stats,
        migration_stats=migration_stats,
        risk_flags=list(dict.fromkeys(risk_flags)),
        wall_seconds=time.perf_counter() - t0,
    )


def spawned_bridge_result_to_dict(result: SpawnedBridgeExecutionResult) -> dict[str, Any]:
    """JSON-friendly SpawnedBridgeExecutionResult."""
    return {
        "mode": "spawned_bridge_mpo_contraction",
        "n_qubits": result.n_qubits,
        "n_layers": result.n_layers,
        "n_gates": result.n_gates,
        "final_site_to_qubit": result.final_site_to_qubit,
        "final_max_bond": result.final_max_bond,
        "bitstring_working_order": result.bitstring_working_order,
        "exact_peak_bitstring": result.exact_peak_bitstring,
        "exact_peak_probability": result.exact_peak_probability,
        "exact_match": result.exact_match,
        "peak_extraction": None if result.peak_extraction is None else {
            "marginal_original_order": result.peak_extraction.marginal_original_order,
            "best_original_order": result.peak_extraction.best_original_order,
            "probability_estimate": result.peak_extraction.probability_estimate,
            "n_probability_evaluations": result.peak_extraction.n_probability_evaluations,
            "risk_flags": result.peak_extraction.risk_flags,
        },
        "block_stats": [
            {
                "kind": s.kind,
                "window_index": s.window_index,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "n_gates": s.n_gates,
                "n_boundary_gates": s.n_boundary_gates,
                "n_local_gates": s.n_local_gates,
                "max_bond_before": s.max_bond_before,
                "max_bond_after": s.max_bond_after,
                "current_order": s.current_order,
                "risk_flags": s.risk_flags,
            }
            for s in result.block_stats
        ],
        "migration_stats": [
            {
                "from_window": s.from_window,
                "to_window": s.to_window,
                "source_order": s.source_order,
                "target_order": s.target_order,
                "adjacent_swaps": [list(x) for x in s.adjacent_swaps],
                "max_bond_before": s.max_bond_before,
                "max_bond_after": s.max_bond_after,
                "transition_cost": s.transition_cost,
                "risk_flags": s.risk_flags,
            }
            for s in result.migration_stats
        ],
        "risk_flags": result.risk_flags,
        "wall_seconds": result.wall_seconds,
    }
