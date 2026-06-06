"""
Circuit loading and GateInfo conversion utilities.
Independent of separator_mpo_attack/circuit_tools.py.
"""
from __future__ import annotations

from pathlib import Path

from qiskit import QuantumCircuit

from plan_types import GateInfo


_SKIP_OPS = frozenset({"measure", "barrier", "delay", "reset"})


def remove_measurements(qc: QuantumCircuit) -> QuantumCircuit:
    """Return a copy of qc with all measurements, barriers, and delays stripped."""
    clean = QuantumCircuit(*qc.qregs)
    for inst in qc.data:
        if inst.operation.name not in _SKIP_OPS:
            clean.append(inst)
    return clean


def load_circuit(path: str | Path) -> QuantumCircuit:
    """Load a QASM 2.0 circuit. Raises on unsupported formats."""
    from qiskit import qasm2
    return qasm2.load(
        str(Path(path).resolve()),
        custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS,
    )


def _qubit_map(qc: QuantumCircuit) -> dict:
    return {q: i for i, q in enumerate(qc.qubits)}


def iter_gate_infos(qc: QuantumCircuit):
    """
    Yield GateInfo objects for every non-skip instruction in qc,
    preserving original instruction index as `time`.
    `layer` is set to None here; use greedy_layerize to assign layers.
    """
    q2i = _qubit_map(qc)
    for t, inst in enumerate(qc.data):
        op = inst.operation
        if op.name in _SKIP_OPS:
            continue
        yield GateInfo(
            time=t,
            layer=None,
            name=op.name,
            qubits=tuple(q2i[q] for q in inst.qubits),
            params=tuple(float(p) for p in op.params),
            operation=op,
        )


def count_two_qubit_gates(qc: QuantumCircuit) -> int:
    """Return the total number of two-qubit gates (excluding measure/barrier)."""
    return sum(
        1 for inst in qc.data
        if inst.operation.name not in _SKIP_OPS and len(inst.qubits) == 2
    )


def gateinfo_to_dict(g: GateInfo) -> dict:
    """Convert a GateInfo to the plain-dict format used by separator_mpo_attack."""
    return {
        "time": g.time,
        "name": g.name,
        "qubits": g.qubits,
        "params": list(g.params),
        "operation": g.operation,
    }


def dict_to_gateinfo(d: dict, layer: int | None = None) -> GateInfo:
    """Convert a separator_mpo_attack gate dict to GateInfo."""
    return GateInfo(
        time=d["time"],
        layer=layer,
        name=d["name"],
        qubits=tuple(d["qubits"]),
        params=tuple(float(p) for p in d.get("params", [])),
        operation=d.get("operation"),
    )
