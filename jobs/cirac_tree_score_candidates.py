#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import csv
import itertools
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np


TWO_QUBIT_OPS = {"cx", "cz", "swap", "crx", "cry", "crz", "rxx", "ryy", "rzz", "rzx"}


def instruction_parts(item: Any) -> tuple[Any, list[Any], list[Any]]:
    if hasattr(item, "operation"):
        return item.operation, list(item.qubits), list(item.clbits)
    op, qargs, cargs = item
    return op, list(qargs), list(cargs)


def bit_index(circuit: Any, bit: Any) -> int:
    return int(circuit.find_bit(bit).index)


def strip_measurements(circuit: Any) -> Any:
    if "measure" in circuit.count_ops():
        return circuit.remove_final_measurements(inplace=False)
    return circuit


def interaction_graph(circuit: Any, recency_alpha: float) -> np.ndarray:
    n = circuit.num_qubits
    weights = np.zeros((n, n), dtype=float)
    data = list(circuit.data)
    denom = max(1, len(data) - 1)
    for idx, inst in enumerate(data):
        op, qargs, _ = instruction_parts(inst)
        name = op.name.lower()
        if name not in TWO_QUBIT_OPS or len(qargs) != 2:
            continue
        q0, q1 = sorted(bit_index(circuit, bit) for bit in qargs)
        inc = 1.0 + recency_alpha * idx / denom
        if name == "swap":
            inc *= 2.0
        weights[q0, q1] += inc
        weights[q1, q0] += inc
    return weights


def connected_components(weights: np.ndarray, nodes: list[int]) -> list[list[int]]:
    node_set = set(nodes)
    seen: set[int] = set()
    comps = []
    for start in nodes:
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        comp = []
        while stack:
            node = stack.pop()
            comp.append(node)
            for nxt in np.flatnonzero(weights[node] > 0):
                nxt = int(nxt)
                if nxt in node_set and nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        comps.append(sorted(comp))
    return comps


def spectral_split(nodes: list[int], weights: np.ndarray) -> tuple[list[int], list[int]]:
    if len(nodes) <= 1:
        return nodes, []
    if len(nodes) == 2:
        return [nodes[0]], [nodes[1]]
    sub = weights[np.ix_(nodes, nodes)]
    if not np.any(sub > 0):
        mid = len(nodes) // 2
        return nodes[:mid], nodes[mid:]
    deg = sub.sum(axis=1)
    lap = np.diag(deg) - sub
    vals, vecs = np.linalg.eigh(lap)
    fiedler = vecs[:, np.argsort(vals)[1]]
    ordered = [node for _, node in sorted(zip(fiedler, nodes), key=lambda x: (x[0], x[1]))]
    mid = len(ordered) // 2
    return ordered[:mid], ordered[mid:]


def recursive_tree(nodes: list[int], weights: np.ndarray) -> Any:
    if len(nodes) == 1:
        return nodes[0]
    comps = connected_components(weights, nodes)
    if len(comps) > 1:
        comps.sort(key=lambda comp: (-sum(float(weights[i].sum()) for i in comp), min(comp)))
        return [recursive_tree(comp, weights) for comp in comps]
    left, right = spectral_split(nodes, weights)
    return [recursive_tree(left, weights), recursive_tree(right, weights)]


def flatten_tree(tree: Any) -> list[int]:
    if isinstance(tree, int):
        return [tree]
    out: list[int] = []
    for child in tree:
        out.extend(flatten_tree(child))
    return out


def tree_depth(tree: Any) -> int:
    if isinstance(tree, int):
        return 0
    return 1 + max(tree_depth(child) for child in tree)


def tree_cut_stats(tree: Any, weights: np.ndarray) -> list[dict[str, Any]]:
    rows = []

    def walk(node: Any) -> set[int]:
        if isinstance(node, int):
            return {node}
        child_sets = [walk(child) for child in node]
        here = set().union(*child_sets)
        for child_set in child_sets:
            outside = here - child_set
            cut = 0.0
            for i in child_set:
                for j in outside:
                    cut += float(weights[i, j])
            rows.append({"child_size": len(child_set), "parent_size": len(here), "internal_tree_cut_weight": cut})
        return here

    walk(tree)
    rows.sort(key=lambda row: (-row["internal_tree_cut_weight"], -row["parent_size"], row["child_size"]))
    return rows


def remap_circuit(circuit: Any, logical_to_site: list[int]) -> Any:
    from qiskit import QuantumCircuit

    out = QuantumCircuit(circuit.num_qubits)
    out.global_phase = circuit.global_phase
    for inst in circuit.data:
        op, qargs, cargs = instruction_parts(inst)
        if cargs or op.name.lower() == "measure":
            continue
        out.append(op.copy(), [logical_to_site[bit_index(circuit, bit)] for bit in qargs], [])
    return out


def load_counts(path: Path) -> collections.Counter[str]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text())
        if isinstance(data, dict) and "counts" in data:
            data = data["counts"]
        if isinstance(data, dict):
            return collections.Counter({str(k): int(v) for k, v in data.items()})
    counts: collections.Counter[str] = collections.Counter()
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            bitstring = row.get("bitstring") or row.get("bits") or row.get("sample")
            count = row.get("count") or row.get("counts") or 1
            if bitstring:
                counts[str(bitstring)] += int(count)
    return counts


def load_candidates(paths: list[Path], limit: int) -> list[str]:
    counts: collections.Counter[str] = collections.Counter()
    for path in paths:
        counts.update(load_counts(path))
    return [bits for bits, _ in counts.most_common(limit)]


def qiskit_to_site_bits(qiskit_bits: str, site_to_logical: list[int]) -> str:
    logical_bits = list(reversed(qiskit_bits.strip().replace(" ", "")))
    return "".join(logical_bits[logical] for logical in site_to_logical)


def hamming_neighbors(bits: str, radius: int, max_neighbors: int) -> list[str]:
    out = [bits]
    n = len(bits)
    for r in range(1, radius + 1):
        for idxs in itertools.combinations(range(n), r):
            arr = list(bits)
            for i in idxs:
                arr[i] = "1" if arr[i] == "0" else "0"
            out.append("".join(arr))
            if len(out) >= max_neighbors:
                return out
    return out


def make_optimizer(kind: str, max_repeats: int, tree: Any, order: list[int]) -> Any:
    if kind == "auto-hq":
        return "auto-hq"
    try:
        import cotengra as ctg
    except Exception:
        return "auto-hq"
    if kind == "tree-greedy":
        return ctg.HyperOptimizer(
            methods=["greedy", "kahypar", "labels"],
            max_repeats=max_repeats,
            minimize="combo",
            progbar=False,
        )
    if kind == "nested-dissection":
        return ctg.HyperOptimizer(
            methods=["kahypar", "greedy"],
            max_repeats=max_repeats,
            minimize="flops",
            progbar=False,
        )
    return "auto-hq"


def score_amplitude(circuit: Any, site_bits: str, optimize: Any) -> complex:
    if hasattr(circuit, "amplitude"):
        return complex(circuit.amplitude(site_bits, optimize=optimize))
    psi = circuit.psi
    if hasattr(psi, "amplitude"):
        return complex(psi.amplitude(site_bits, optimize=optimize))
    raise AttributeError("Quimb circuit/state does not expose amplitude().")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qasm", type=Path, required=True)
    parser.add_argument("--candidate-counts", type=Path, action="append", default=[])
    parser.add_argument("--candidate", action="append", default=[])
    parser.add_argument("--candidate-limit", type=int, default=64)
    parser.add_argument("--hamming-radius", type=int, default=1)
    parser.add_argument("--max-neighbors-per-candidate", type=int, default=256)
    parser.add_argument("--recency-alpha", type=float, default=0.15)
    parser.add_argument("--optimizer", choices=["auto-hq", "tree-greedy", "nested-dissection"], default="tree-greedy")
    parser.add_argument("--optimizer-repeats", type=int, default=64)
    parser.add_argument("--backend", choices=["numpy", "cuda"], default="numpy")
    parser.add_argument("--out", type=Path, default=Path("outputs/tree_tensor_sim/cirac_tree_score/challenge-80_46.json"))
    args = parser.parse_args()

    from qiskit import QuantumCircuit
    from qiskit_quimb import quimb_circuit
    import quimb.tensor as qtn

    t0 = time.perf_counter()
    qc = strip_measurements(QuantumCircuit.from_qasm_file(str(args.qasm)))
    weights = interaction_graph(qc, args.recency_alpha)
    tree = recursive_tree(list(range(qc.num_qubits)), weights)
    order = flatten_tree(tree)
    logical_to_site = [0] * len(order)
    for site, logical in enumerate(order):
        logical_to_site[logical] = site
    mapped = remap_circuit(qc, logical_to_site)

    to_backend = None
    if args.backend == "cuda":
        import torch

        to_backend = lambda x: torch.tensor(x, dtype=torch.complex128, device="cuda:0")

    circ = quimb_circuit(mapped, quimb_circuit_class=qtn.Circuit, to_backend=to_backend)
    optimize = make_optimizer(args.optimizer, args.optimizer_repeats, tree, order)

    candidates = list(dict.fromkeys(args.candidate + load_candidates(args.candidate_counts, args.candidate_limit)))
    rows = []
    for candidate in candidates:
        if len(candidate) != qc.num_qubits:
            continue
        total_prob = 0.0
        exact_prob = None
        scored = 0
        for nb in hamming_neighbors(candidate, args.hamming_radius, args.max_neighbors_per_candidate):
            site_bits = qiskit_to_site_bits(nb, order)
            amp = score_amplitude(circ, site_bits, optimize)
            prob = float(abs(amp) ** 2)
            if nb == candidate:
                exact_prob = prob
            total_prob += prob
            scored += 1
        rows.append(
            {
                "candidate_qiskit_order": candidate,
                "exact_probability": exact_prob,
                "hamming_neighborhood_probability": total_prob,
                "neighborhood_strings_scored": scored,
            }
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"status": "running", "rows": rows}, indent=2, sort_keys=True))

    rows.sort(key=lambda row: (-(row["hamming_neighborhood_probability"] or 0.0), -(row["exact_probability"] or 0.0)))
    result = {
        "status": "ok",
        "method": "cirac_tree_hierarchical_candidate_scoring",
        "qasm": str(args.qasm),
        "num_qubits": qc.num_qubits,
        "tree": tree,
        "tree_depth": tree_depth(tree),
        "site_to_logical_qubit": order,
        "top_tree_cuts": tree_cut_stats(tree, weights)[:32],
        "optimizer": args.optimizer,
        "optimizer_repeats": args.optimizer_repeats,
        "hamming_radius": args.hamming_radius,
        "rows": rows,
        "seconds": time.perf_counter() - t0,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps({"status": "ok", "top": rows[:5]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
