"""
Greedy layerization of quantum circuits.

Returns list[list[GateInfo]] with each gate carrying its assigned layer index.
Gates in the same layer have disjoint qubit support and respect causal order.
"""
from __future__ import annotations

from qiskit import QuantumCircuit

from plan_types import GateInfo
from circuit_tools import _SKIP_OPS, _qubit_map


def greedy_layerize(qc: QuantumCircuit) -> list[list[GateInfo]]:
    """
    Assign every non-skip gate to the earliest possible causal layer.

    Rule: a gate on qubits Q goes into layer max(last_layer[q] for q in Q) + 1,
    where last_layer[q] = -1 if qubit q has not yet appeared.

    Returns a list of layers, where layers[k] contains all GateInfo objects
    with layer == k. Both `time` (original instruction index) and `layer`
    are set on each GateInfo.
    """
    q2i = _qubit_map(qc)
    last_layer: dict[int, int] = {}  # qubit -> latest layer index
    all_gates: list[GateInfo] = []

    for t, inst in enumerate(qc.data):
        op = inst.operation
        if op.name in _SKIP_OPS:
            continue

        qubits = tuple(q2i[q] for q in inst.qubits)

        if qubits:
            layer_idx = max(last_layer.get(q, -1) for q in qubits) + 1
        else:
            layer_idx = 0  # 0-qubit global phase gates

        gate = GateInfo(
            time=t,
            layer=layer_idx,
            name=op.name,
            qubits=qubits,
            params=tuple(float(p) for p in op.params),
            operation=op,
        )
        for q in qubits:
            last_layer[q] = layer_idx

        all_gates.append(gate)

    if not all_gates:
        return []

    n_layers = max(g.layer for g in all_gates) + 1
    layers: list[list[GateInfo]] = [[] for _ in range(n_layers)]
    for g in all_gates:
        layers[g.layer].append(g)

    return layers


def layer_support(layer: list[GateInfo]) -> set[int]:
    """Return the set of qubits touched by any gate in this layer."""
    return {q for g in layer for q in g.qubits}


def layer_twoq_count(layer: list[GateInfo]) -> int:
    """Return the number of two-qubit gates in this layer."""
    return sum(1 for g in layer if len(g.qubits) == 2)


def layers_to_gate_list(layers: list[list[GateInfo]]) -> list[GateInfo]:
    """Flatten layers to a single list in layer-then-time order."""
    return [g for layer in layers for g in sorted(layer, key=lambda g: g.time)]
