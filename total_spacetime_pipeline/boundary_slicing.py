"""Chronological boundary-sliced diagnostics for spacetime blocking."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qiskit import QuantumCircuit

from .compat import ensure_repo_paths

ensure_repo_paths()

from circuit_tools import remove_measurements
from layer_tools import greedy_layerize, layers_to_gate_list
from plan_types import GateInfo
from temporal_pipeline import build_circuit_from_gates, normalized_unitary_error


@dataclass
class BoundaryOrderingViolation:
    """A boundary gate that cannot safely be deferred to the end."""
    boundary_time: int
    boundary_qubits: tuple[int, ...]
    later_time: int
    later_name: str
    later_qubits: tuple[int, ...]
    reason: str


@dataclass
class BoundaryOrderingAudit:
    """Static and exact baby-case audit for final-boundary deferral."""
    n_boundary_gates: int
    n_local_gates: int
    n_violations: int
    violations: list[BoundaryOrderingViolation]
    deferred_boundary_unitary_error: float | None
    boundary_event_count: int
    local_block_count: int
    risk_flags: list[str]


def _is_boundary(g: GateInfo, A: set[int], B: set[int]) -> bool:
    if len(g.qubits) < 2:
        return False
    sides = [q in A for q in g.qubits]
    return any(s != sides[0] for s in sides)


def _is_local(g: GateInfo, A: set[int], B: set[int]) -> bool:
    if len(g.qubits) == 0:
        return True
    in_A = [q in A for q in g.qubits]
    in_B = [q in B for q in g.qubits]
    return all(in_A) or all(in_B)


def build_boundary_sliced_events(gates: list[GateInfo], A: set[int], B: set[int]) -> list[dict[str, Any]]:
    """
    Split a gate stream into chronological local blocks and boundary events.

    Every gate appears exactly once. This is the safe representation for future
    boundary-sliced tensor execution.
    """
    events: list[dict[str, Any]] = []
    local_buffer: list[GateInfo] = []
    for g in sorted(gates, key=lambda x: x.time):
        if _is_boundary(g, A, B):
            if local_buffer:
                events.append({
                    "kind": "local_block",
                    "start_time": local_buffer[0].time,
                    "end_time": local_buffer[-1].time,
                    "gates": list(local_buffer),
                })
                local_buffer = []
            events.append({
                "kind": "boundary_gate",
                "time": g.time,
                "gate": g,
            })
        else:
            local_buffer.append(g)
    if local_buffer:
        events.append({
            "kind": "local_block",
            "start_time": local_buffer[0].time,
            "end_time": local_buffer[-1].time,
            "gates": list(local_buffer),
        })
    return events


def _deferred_boundary_circuit(gates: list[GateInfo], n_qubits: int, A: set[int], B: set[int]) -> QuantumCircuit:
    local = [g for g in gates if not _is_boundary(g, A, B)]
    boundary = [g for g in gates if _is_boundary(g, A, B)]
    return build_circuit_from_gates(
        sorted(local, key=lambda g: g.time) + sorted(boundary, key=lambda g: g.time),
        n_qubits,
        sort_by_time=False,
    )


def run_boundary_ordering_audit(
    qc_raw,
    A: set[int],
    B: set[int],
    *,
    max_exact_qubits: int = 8,
) -> BoundaryOrderingAudit:
    """
    Detect when final-boundary deferral is definitely unsafe.

    Violation criterion: a boundary gate is followed by a later local gate that
    touches either boundary qubit. This does not prove every unflagged case is
    safe, but flagged cases are exactly the ones the old approximation mishandles.
    """
    qc = remove_measurements(qc_raw)
    layers = greedy_layerize(qc)
    gates = layers_to_gate_list(layers)
    boundary_gates = [g for g in gates if _is_boundary(g, A, B)]
    local_gates = [g for g in gates if _is_local(g, A, B) and not _is_boundary(g, A, B)]
    violations: list[BoundaryOrderingViolation] = []

    for bg in boundary_gates:
        bq = set(bg.qubits)
        for later in local_gates:
            if later.time <= bg.time:
                continue
            if bq & set(later.qubits):
                violations.append(BoundaryOrderingViolation(
                    boundary_time=bg.time,
                    boundary_qubits=bg.qubits,
                    later_time=later.time,
                    later_name=later.name,
                    later_qubits=later.qubits,
                    reason="later_local_gate_overlaps_boundary_qubit",
                ))

    events = build_boundary_sliced_events(gates, A, B)
    unitary_error = None
    risk_flags = ["chronological_boundary_slicing_audit"]
    if violations:
        risk_flags.append("final_boundary_deferral_invalid")
    if qc.num_qubits <= max_exact_qubits:
        true_circ = build_circuit_from_gates(gates, qc.num_qubits)
        deferred = _deferred_boundary_circuit(gates, qc.num_qubits, A, B)
        unitary_error = normalized_unitary_error(true_circ, deferred)
    else:
        risk_flags.append("exact_deferred_boundary_check_skipped_qubit_limit")

    return BoundaryOrderingAudit(
        n_boundary_gates=len(boundary_gates),
        n_local_gates=len(local_gates),
        n_violations=len(violations),
        violations=violations,
        deferred_boundary_unitary_error=unitary_error,
        boundary_event_count=sum(1 for e in events if e["kind"] == "boundary_gate"),
        local_block_count=sum(1 for e in events if e["kind"] == "local_block"),
        risk_flags=risk_flags,
    )


def boundary_ordering_audit_to_dict(audit: BoundaryOrderingAudit) -> dict[str, Any]:
    """JSON-friendly BoundaryOrderingAudit."""
    return {
        "n_boundary_gates": audit.n_boundary_gates,
        "n_local_gates": audit.n_local_gates,
        "n_violations": audit.n_violations,
        "violations": [
            {
                "boundary_time": v.boundary_time,
                "boundary_qubits": list(v.boundary_qubits),
                "later_time": v.later_time,
                "later_name": v.later_name,
                "later_qubits": list(v.later_qubits),
                "reason": v.reason,
            }
            for v in audit.violations
        ],
        "deferred_boundary_unitary_error": audit.deferred_boundary_unitary_error,
        "boundary_event_count": audit.boundary_event_count,
        "local_block_count": audit.local_block_count,
        "risk_flags": audit.risk_flags,
    }

