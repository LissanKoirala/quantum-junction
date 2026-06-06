from __future__ import annotations

from qiskit import QuantumCircuit
from qiskit.converters import circuit_to_dag, dag_to_circuit


def remove_measurements(qc: QuantumCircuit) -> QuantumCircuit:
    """Return a copy of qc with all measurements and barriers removed."""
    out = qc.copy()
    out.remove_final_measurements(inplace=True)
    # Also strip any mid-circuit barriers
    out = out.remove_final_measurements(inplace=False)
    # Belt-and-suspenders: filter out remaining measure/barrier instructions
    clean = QuantumCircuit(*out.qregs)
    for inst in out.data:
        if inst.operation.name not in {"measure", "barrier", "delay"}:
            clean.append(inst)
    return clean


def get_qubit_index_map(qc: QuantumCircuit) -> dict:
    """Return {qubit_object: integer_index}."""
    return {q: i for i, q in enumerate(qc.qubits)}


def iter_two_qubit_gates(qc: QuantumCircuit):
    """
    Yield dicts for every 2-qubit gate in qc:
        {"time": int, "name": str, "qubits": (int, int),
         "params": list, "operation": op}
    Time is the instruction index (0-based) in qc.data.
    """
    q2i = get_qubit_index_map(qc)
    for t, inst in enumerate(qc.data):
        op = inst.operation
        qargs = inst.qubits
        if len(qargs) != 2:
            continue
        i, j = q2i[qargs[0]], q2i[qargs[1]]
        if i == j:
            continue
        yield {
            "time": t,
            "name": op.name,
            "qubits": (i, j),
            "params": list(op.params),
            "operation": op,
        }


def gate_layers(qc: QuantumCircuit) -> list[QuantumCircuit]:
    """Return list of non-overlapping gate layers (DAG-based layering)."""
    dag = circuit_to_dag(qc)
    layers = []
    for layer in dag.layers():
        layers.append(dag_to_circuit(layer["graph"]))
    return layers


def build_subcircuit(qc: QuantumCircuit, qubit_subset: list[int]) -> QuantumCircuit:
    """
    Extract gates whose qubits are ALL in qubit_subset, remapping to 0..|subset|-1.
    qubit_subset: sorted list of original qubit indices.
    Returns a new QuantumCircuit on len(qubit_subset) qubits.
    """
    remap = {orig: new for new, orig in enumerate(qubit_subset)}
    q2i = get_qubit_index_map(qc)
    sub = QuantumCircuit(len(qubit_subset))
    for inst in qc.data:
        op = inst.operation
        if op.name in {"measure", "barrier", "delay"}:
            continue
        orig_idxs = [q2i[q] for q in inst.qubits]
        if not all(idx in remap for idx in orig_idxs):
            continue
        new_idxs = [remap[idx] for idx in orig_idxs]
        sub.append(op, new_idxs)
    return sub


def build_boundary_circuit(
    qc: QuantumCircuit,
    boundary_gates: list[dict],
    qubit_to_combined_site: dict[int, int],
    n_combined: int,
) -> QuantumCircuit:
    """
    Build an N-qubit circuit containing only the boundary gates,
    remapped so that original qubit q → combined site qubit_to_combined_site[q].
    """
    circ = QuantumCircuit(n_combined)
    for g in boundary_gates:
        op = g["operation"]
        new_qubits = [qubit_to_combined_site[q] for q in g["qubits"]]
        circ.append(op, new_qubits)
    # Add single-qubit gates from boundary side too (classified by caller as needed)
    return circ
