from __future__ import annotations

from qiskit import QuantumCircuit
from circuit_tools import get_qubit_index_map, iter_two_qubit_gates, gate_layers


def classify_gate_by_partition(gate_info: dict, A: set, B: set) -> str:
    """Return 'A', 'B', 'boundary', 'single_A', or 'single_B'."""
    qs = gate_info["qubits"]
    if len(qs) == 1:
        return "single_A" if qs[0] in A else "single_B"
    i, j = qs
    if i in A and j in A:
        return "A"
    if i in B and j in B:
        return "B"
    return "boundary"


def split_circuit_by_partition(qc: QuantumCircuit, A: set, B: set) -> dict:
    """
    Classify every gate by partition membership.
    Returns:
        {
          "A_gates":         list of gate_info dicts (both qubits in A),
          "B_gates":         list,
          "boundary_gates":  list (one qubit in A, one in B),
          "single_A_gates":  list (1-qubit gates on A qubits),
          "single_B_gates":  list,
        }
    All gate_info dicts include original time index.
    """
    q2i = get_qubit_index_map(qc)
    buckets: dict[str, list] = {
        "A_gates": [], "B_gates": [], "boundary_gates": [],
        "single_A_gates": [], "single_B_gates": [],
    }

    for t, inst in enumerate(qc.data):
        op = inst.operation
        if op.name in {"measure", "barrier", "delay"}:
            continue
        orig_idxs = tuple(q2i[q] for q in inst.qubits)
        g = {"time": t, "name": op.name, "qubits": orig_idxs,
             "params": list(op.params), "operation": op}
        cls = classify_gate_by_partition(g, A, B)
        buckets[f"{cls}_gates"].append(g)

    return buckets


def split_circuit_into_windows(
    qc: QuantumCircuit, A: set, B: set, num_windows: int = 20
) -> list[dict]:
    """
    Return windowed structure preserving time order:
    [{"window": w, "A_gates": [...], "B_gates": [...], "boundary_gates": [...]}, ...]
    """
    q2i = get_qubit_index_map(qc)
    all_gates = []
    for t, inst in enumerate(qc.data):
        op = inst.operation
        if op.name in {"measure", "barrier", "delay"}:
            continue
        orig_idxs = tuple(q2i[q] for q in inst.qubits)
        all_gates.append({"time": t, "name": op.name, "qubits": orig_idxs,
                           "params": list(op.params), "operation": op})

    T = max((g["time"] for g in all_gates), default=0) + 1
    windows = [{"window": w, "A_gates": [], "B_gates": [], "boundary_gates": []}
               for w in range(num_windows)]

    for g in all_gates:
        if len(g["qubits"]) != 2:
            continue
        cls = classify_gate_by_partition(g, A, B)
        w = min(int(g["time"] * num_windows / T), num_windows - 1)
        key = f"{cls}_gates"
        if key in windows[w]:
            windows[w][key].append(g)

    return windows


def build_remapped_subcircuit(gate_list: list[dict], qubit_subset: list[int]) -> QuantumCircuit:
    """
    Build a Qiskit circuit on len(qubit_subset) qubits from the given gate list.
    qubit_subset: sorted original qubit indices → remapped to 0..|subset|-1.
    Only includes gates whose qubits are entirely within qubit_subset.
    """
    remap = {orig: new for new, orig in enumerate(qubit_subset)}
    sub = QuantumCircuit(len(qubit_subset))
    for g in sorted(gate_list, key=lambda x: x["time"]):
        if not all(q in remap for q in g["qubits"]):
            continue
        new_qs = [remap[q] for q in g["qubits"]]
        sub.append(g["operation"], new_qs)
    return sub


def split_circuit_by_k_partition(qc: QuantumCircuit, partitions: list[set]) -> dict:
    """
    Generalised split for k partitions.
    Returns:
        {
          "partition_gates": [list_of_gate_infos_for_part_0, ..., for_part_{k-1}],
          "boundary_gates":  list of gate_infos crossing any partition boundary,
        }
    A gate is "in partition i" if BOTH its qubits belong to partition i.
    A gate is a "boundary gate" if its qubits span two different partitions.
    """
    node_to_part = {}
    for i, p in enumerate(partitions):
        for q in p:
            node_to_part[q] = i

    q2i = get_qubit_index_map(qc)
    partition_gates: list[list] = [[] for _ in partitions]
    boundary_gates: list = []

    for t, inst in enumerate(qc.data):
        op = inst.operation
        if op.name in {"measure", "barrier", "delay"}:
            continue
        orig_idxs = tuple(q2i[q] for q in inst.qubits)
        g = {"time": t, "name": op.name, "qubits": orig_idxs,
             "params": list(op.params), "operation": op}

        if len(orig_idxs) == 1:
            pi = node_to_part.get(orig_idxs[0])
            if pi is not None:
                partition_gates[pi].append(g)
        elif len(orig_idxs) == 2:
            p0 = node_to_part.get(orig_idxs[0])
            p1 = node_to_part.get(orig_idxs[1])
            if p0 is not None and p0 == p1:
                partition_gates[p0].append(g)
            else:
                boundary_gates.append(g)

    return {"partition_gates": partition_gates, "boundary_gates": boundary_gates}


def build_remapped_boundary_circuit(
    boundary_gates: list[dict],
    qubit_to_combined_site: dict[int, int],
    n_combined: int,
) -> QuantumCircuit:
    """
    Build an n_combined-qubit circuit for the boundary gates,
    remapping original qubit indices via qubit_to_combined_site.
    """
    circ = QuantumCircuit(n_combined)
    for g in sorted(boundary_gates, key=lambda x: x["time"]):
        new_qs = [qubit_to_combined_site[q] for q in g["qubits"]
                  if q in qubit_to_combined_site]
        if len(new_qs) != len(g["qubits"]):
            continue  # safety: skip if qubit not mapped
        circ.append(g["operation"], new_qs)
    return circ
