#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import importlib.metadata
import json
import math
import os
import re
import resource
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CHALLENGE_RE = re.compile(r"challenge-(\d+)_(\d+)\.qasm$")
SKIP_OPS = {"barrier", "measure"}
TWO_QUBIT_OPS = {
    "cx",
    "cz",
    "cy",
    "ch",
    "swap",
    "iswap",
    "ecr",
    "rxx",
    "ryy",
    "rzz",
    "rzx",
    "crx",
    "cry",
    "crz",
    "cp",
    "cu",
    "cu1",
    "cu3",
}

KNOWN_ANSWERS = {
    1: "10101101",
    2: "1010101011001000",
    3: "011110010000101010001000",
    4: "1111111000101010110110011111",
    11: "01001110",
    12: "1111000101101011",
    13: "111110011111001011010001",
    27: "11001001",
    28: "1101001111011100",
    29: "110100010111100001001001",
}


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(data), indent=2, sort_keys=True) + "\n")


def package_versions() -> dict[str, str]:
    out = {}
    for name in ["qiskit", "qiskit-aer", "quimb", "qiskit-quimb", "numpy", "scipy", "matplotlib"]:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = "not-installed"
    return out


def challenge_paths(root: Path) -> list[Path]:
    return sorted((root / "challenges").glob("*/*.qasm"), key=lambda p: (p.parent.name, p.name))


def resolve_challenge(root: Path, args: argparse.Namespace) -> Path:
    if args.qasm is not None:
        return (args.qasm if args.qasm.is_absolute() else root / args.qasm).resolve()
    if args.array_index is not None:
        paths = challenge_paths(root)
        if args.array_index < 0 or args.array_index >= len(paths):
            raise ValueError(f"array index {args.array_index} out of range for {len(paths)} files")
        return paths[args.array_index].resolve()
    if args.challenge_id is None:
        raise ValueError("provide --qasm, --challenge-id, or --array-index")
    hits = []
    for path in challenge_paths(root):
        match = CHALLENGE_RE.match(path.name)
        if match and int(match.group(2)) == args.challenge_id:
            hits.append(path)
    if len(hits) != 1:
        raise ValueError(f"expected one challenge id {args.challenge_id}, found {hits}")
    return hits[0].resolve()


def rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def instruction_parts(item: Any) -> tuple[Any, list[Any], list[Any]]:
    if hasattr(item, "operation"):
        return item.operation, list(item.qubits), list(item.clbits)
    op, qargs, cargs = item
    return op, list(qargs), list(cargs)


def bit_index(qc: Any, bit: Any) -> int:
    if hasattr(qc, "find_bit"):
        return int(qc.find_bit(bit).index)
    if hasattr(bit, "_index"):
        return int(bit._index)
    return int(bit.index)


def operation_copy(op: Any) -> Any:
    if hasattr(op, "copy"):
        return op.copy()
    return copy.copy(op)


def strip_to_unitary(qc: Any) -> Any:
    from qiskit import QuantumCircuit

    out = QuantumCircuit(qc.num_qubits)
    out.global_phase = getattr(qc, "global_phase", 0)
    for item in qc.data:
        op, qargs, cargs = instruction_parts(item)
        if op.name.lower() in SKIP_OPS or cargs:
            continue
        out.append(operation_copy(op), [bit_index(qc, q) for q in qargs], [])
    return out


def relabel_circuit(qc: Any, order: list[int]) -> Any:
    from qiskit import QuantumCircuit

    pos = {orig: new for new, orig in enumerate(order)}
    out = QuantumCircuit(qc.num_qubits)
    out.global_phase = getattr(qc, "global_phase", 0)
    for item in qc.data:
        op, qargs, cargs = instruction_parts(item)
        if op.name.lower() in SKIP_OPS or cargs:
            continue
        out.append(operation_copy(op), [pos[bit_index(qc, q)] for q in qargs], [])
    return out


def build_interaction_graph(qc: Any) -> dict[str, Any]:
    n = qc.num_qubits
    weights = np.zeros((n, n), dtype=float)
    pair_counts: Counter[tuple[int, int]] = Counter()
    op_counts: Counter[str] = Counter()
    for item in qc.data:
        op, qargs, _ = instruction_parts(item)
        name = op.name.lower()
        op_counts[name] += 1
        qinds = [bit_index(qc, q) for q in qargs]
        if len(qinds) != 2 or name not in TWO_QUBIT_OPS:
            continue
        i, j = sorted(qinds)
        weight = 2.0 if name == "swap" else 1.0
        weights[i, j] += weight
        weights[j, i] += weight
        pair_counts[(i, j)] += 1
    degree = np.count_nonzero(weights, axis=1)
    weighted_degree = weights.sum(axis=1)
    return {
        "weights": weights,
        "op_counts": dict(op_counts),
        "edge_count": int(len(pair_counts)),
        "density": 0.0 if n < 2 else len(pair_counts) / (n * (n - 1) / 2),
        "degree_min": int(degree.min()) if n else 0,
        "degree_mean": float(degree.mean()) if n else 0.0,
        "degree_max": int(degree.max()) if n else 0,
        "weighted_degree_min": float(weighted_degree.min()) if n else 0.0,
        "weighted_degree_mean": float(weighted_degree.mean()) if n else 0.0,
        "weighted_degree_max": float(weighted_degree.max()) if n else 0.0,
        "pair_counts": {f"{i}-{j}": int(c) for (i, j), c in pair_counts.items()},
        "top_pairs": [
            {"qubits": [i, j], "count": int(c), "weight": float(weights[i, j])}
            for (i, j), c in pair_counts.most_common(20)
        ],
    }


def dense_components(weights: np.ndarray) -> list[list[int]]:
    n = weights.shape[0]
    seen = [False] * n
    comps = []
    for start in range(n):
        if seen[start]:
            continue
        stack = [start]
        seen[start] = True
        comp = []
        while stack:
            node = stack.pop()
            comp.append(node)
            for nb in np.nonzero(weights[node] > 0)[0]:
                nb = int(nb)
                if not seen[nb]:
                    seen[nb] = True
                    stack.append(nb)
        comps.append(sorted(comp))
    return comps


def order_rcm(weights: np.ndarray) -> list[int]:
    try:
        from scipy.sparse import csr_matrix
        from scipy.sparse.csgraph import reverse_cuthill_mckee

        return [int(x) for x in reverse_cuthill_mckee(csr_matrix(weights > 0), symmetric_mode=True)]
    except Exception:
        return order_greedy(weights)


def order_greedy(weights: np.ndarray) -> list[int]:
    n = weights.shape[0]
    if n == 0:
        return []
    deg = weights.sum(axis=1)
    remaining = set(range(n))
    cur = int(np.argmax(deg))
    order = []
    while remaining:
        if cur not in remaining:
            cur = max(remaining, key=lambda x: (deg[x], -x))
        order.append(cur)
        remaining.remove(cur)
        if remaining:
            cur = max(remaining, key=lambda x: (weights[cur, x], deg[x], -x))
    return order


def fiedler_order(nodes: list[int], weights: np.ndarray) -> list[int]:
    if len(nodes) <= 2:
        return list(nodes)
    sub = weights[np.ix_(nodes, nodes)]
    if not np.any(sub):
        return list(nodes)
    deg = sub.sum(axis=1)
    lap = np.diag(deg) - sub
    try:
        vals, vecs = np.linalg.eigh(lap)
        coord = vecs[:, 1 if len(vals) > 1 else 0]
        return [nodes[i] for i in np.argsort(coord, kind="mergesort")]
    except Exception:
        return list(nodes)


def order_spectral(weights: np.ndarray) -> list[int]:
    deg = weights.sum(axis=1)
    comps = dense_components(weights)
    comps.sort(key=lambda comp: (-sum(float(deg[i]) for i in comp), min(comp)))
    out: list[int] = []
    for comp in comps:
        out.extend(fiedler_order(comp, weights))
    return out


def recursive_mincut_tree(nodes: list[int], weights: np.ndarray) -> Any:
    if len(nodes) <= 2:
        return list(nodes)
    ordered = fiedler_order(nodes, weights)
    split = max(1, len(ordered) // 2)
    return [recursive_mincut_tree(ordered[:split], weights), recursive_mincut_tree(ordered[split:], weights)]


def flatten_tree(tree: Any) -> list[int]:
    if isinstance(tree, int):
        return [tree]
    out: list[int] = []
    for item in tree:
        out.extend(flatten_tree(item) if isinstance(item, list) else [int(item)])
    return out


def tree_depth(tree: Any) -> int:
    if isinstance(tree, int) or not isinstance(tree, list) or not tree:
        return 0
    if all(isinstance(x, int) for x in tree):
        return 1
    return 1 + max(tree_depth(x) for x in tree)


def order_mincut(weights: np.ndarray) -> tuple[list[int], Any]:
    deg = weights.sum(axis=1)
    comps = dense_components(weights)
    comps.sort(key=lambda comp: (-sum(float(deg[i]) for i in comp), min(comp)))
    forest = [recursive_mincut_tree(comp, weights) for comp in comps]
    tree: Any = forest[0] if len(forest) == 1 else forest
    return flatten_tree(tree), tree


def edge_span_stats(weights: np.ndarray, order: list[int]) -> dict[str, float | int]:
    pos = {node: idx for idx, node in enumerate(order)}
    spans = []
    weighted = []
    for i in range(weights.shape[0]):
        for j in range(i + 1, weights.shape[1]):
            w = float(weights[i, j])
            if w <= 0:
                continue
            s = abs(pos[i] - pos[j])
            spans.append(s)
            weighted.append((s, w))
    if not spans:
        return {"edge_span_max": 0, "edge_span_mean": 0.0, "weighted_edge_span_mean": 0.0}
    total_w = sum(w for _, w in weighted)
    return {
        "edge_span_max": int(max(spans)),
        "edge_span_mean": float(np.mean(spans)),
        "weighted_edge_span_mean": float(sum(s * w for s, w in weighted) / total_w),
    }


def make_orders(weights: np.ndarray, methods: list[str]) -> list[dict[str, Any]]:
    n = weights.shape[0]
    rows = []
    seen: dict[tuple[int, ...], str] = {}
    for method in methods:
        tree = None
        if method == "native":
            order = list(range(n))
        elif method == "rcm":
            order = order_rcm(weights)
        elif method == "spectral":
            order = order_spectral(weights)
        elif method == "mincut":
            order, tree = order_mincut(weights)
        elif method == "greedy":
            order = order_greedy(weights)
        else:
            raise ValueError(f"unknown order method {method}")
        if sorted(order) != list(range(n)):
            order = list(range(n))
        key = tuple(order)
        row = {
            "method": method,
            "order": order,
            "duplicate_of": seen.get(key),
            "span_stats": edge_span_stats(weights, order),
        }
        if tree is not None:
            row["tree"] = tree
            row["tree_depth"] = tree_depth(tree)
        rows.append(row)
        seen.setdefault(key, method)
    return rows


def new_qiskit_to_original_qiskit(bitstring: str, order: list[int]) -> str:
    clean = bitstring.replace(" ", "")
    new_bits = list(reversed(clean))
    original_bits = ["0"] * len(order)
    for new_i, original_i in enumerate(order):
        original_bits[original_i] = new_bits[new_i]
    return "".join(reversed(original_bits))


def counts_to_original(counts: dict[str, int], order: list[int]) -> Counter[str]:
    out: Counter[str] = Counter()
    for bits, count in counts.items():
        out[new_qiskit_to_original_qiskit(bits, order)] += int(count)
    return out


def marginals_from_counts(counts: Counter[str], n: int) -> list[float]:
    total = sum(counts.values())
    if total == 0:
        return [math.nan] * n
    return [sum(c for bits, c in counts.items() if bits[n - 1 - q] == "1") / total for q in range(n)]


def majority_bitstring_qiskit_order(p1s: list[float]) -> str:
    return "".join(reversed(["1" if p >= 0.5 else "0" for p in p1s]))


def run_mps_trial(
    unitary_qc: Any,
    order_row: dict[str, Any],
    bond_dim: int,
    shots: int,
    seed: int,
    truncation_threshold: float,
    max_parallel_threads: int,
) -> dict[str, Any]:
    from qiskit_aer import AerSimulator

    order = order_row["order"]
    measured = relabel_circuit(unitary_qc, order)
    measured.measure_all()
    result = {
        "order_method": order_row["method"],
        "duplicate_order_of": order_row.get("duplicate_of"),
        "order": order,
        "span_stats": order_row["span_stats"],
        "bond_dim": bond_dim,
        "shots": shots,
        "seed": seed,
        "truncation_threshold": truncation_threshold,
        "max_parallel_threads": max_parallel_threads,
        "ansatz_status": "graph_ordered_mps_fallback",
    }
    if "tree_depth" in order_row:
        result["tree_depth"] = order_row["tree_depth"]
        result["tree"] = order_row.get("tree")
    sim = AerSimulator(
        method="matrix_product_state",
        matrix_product_state_max_bond_dimension=bond_dim,
        matrix_product_state_truncation_threshold=truncation_threshold,
        seed_simulator=seed,
        max_parallel_threads=max_parallel_threads,
    )
    t0 = time.perf_counter()
    aer_result = sim.run(measured, shots=shots).result()
    counts = counts_to_original(aer_result.get_counts(), order)
    total = sum(counts.values())
    top_bitstring, top_count = counts.most_common(1)[0]
    p1s = marginals_from_counts(counts, unitary_qc.num_qubits)
    margins = [abs(p - 0.5) for p in p1s if not math.isnan(p)]
    result.update(
        {
            "status": "ok",
            "seconds": time.perf_counter() - t0,
            "top_bitstring_qiskit_order": top_bitstring,
            "top_count": int(top_count),
            "top_probability": float(top_count / total) if total else 0.0,
            "majority_bitstring_qiskit_order": majority_bitstring_qiskit_order(p1s),
            "unique_samples": int(len(counts)),
            "top_counts_qiskit_order": dict(counts.most_common(20)),
            "p1_by_original_qubit": p1s,
            "p1_margin_min": float(min(margins)) if margins else None,
            "p1_margin_mean": float(np.mean(margins)) if margins else None,
            "p1_margin_max": float(max(margins)) if margins else None,
        }
    )
    return result


def exact_peak(unitary_qc: Any, max_qubits: int, top_k: int) -> dict[str, Any]:
    n = unitary_qc.num_qubits
    out: dict[str, Any] = {"enabled": n <= max_qubits, "max_qubits": max_qubits, "num_qubits": n}
    if n > max_qubits:
        out["status"] = "skipped"
        out["reason"] = f"{n} qubits exceeds exact-max-qubits={max_qubits}"
        return out
    from qiskit.quantum_info import Statevector

    t0 = time.perf_counter()
    sv = Statevector.from_instruction(unitary_qc)
    probs = np.abs(np.asarray(sv.data)) ** 2
    peak_i = int(np.argmax(probs))
    k = min(top_k, probs.size)
    top_i = np.argpartition(probs, -k)[-k:] if k else np.array([], dtype=int)
    top_i = top_i[np.argsort(probs[top_i])[::-1]]
    out.update(
        {
            "status": "ok",
            "seconds": time.perf_counter() - t0,
            "peak_bitstring_qiskit_order": format(peak_i, f"0{n}b"),
            "peak_probability": float(probs[peak_i]),
            "top_probabilities": {format(int(i), f"0{n}b"): float(probs[int(i)]) for i in top_i},
        }
    )
    return out


def select_final_candidate(trials: list[dict[str, Any]], exact: dict[str, Any] | None) -> dict[str, Any]:
    if exact and exact.get("status") == "ok":
        return {
            "candidate_qiskit_order": exact["peak_bitstring_qiskit_order"],
            "source": "statevector_exact",
            "score": exact["peak_probability"],
        }
    votes: Counter[str] = Counter()
    evidence: defaultdict[str, float] = defaultdict(float)
    for trial in trials:
        if trial.get("status") != "ok":
            continue
        top = trial["top_bitstring_qiskit_order"]
        majority = trial["majority_bitstring_qiskit_order"]
        mean_margin = float(trial.get("p1_margin_mean") or 0.0)
        top_prob = float(trial.get("top_probability") or 0.0)
        votes[top] += 2
        evidence[top] += 2.0 + top_prob + mean_margin
        votes[majority] += 1
        evidence[majority] += 1.0 + mean_margin
    if not votes:
        return {"candidate_qiskit_order": None, "source": "none", "score": 0.0}
    candidate = max(votes, key=lambda bits: (votes[bits], evidence[bits], bits))
    return {
        "candidate_qiskit_order": candidate,
        "source": "mps_order_consensus",
        "vote_count": int(votes[candidate]),
        "score": float(evidence[candidate]),
        "all_votes": dict(votes),
        "all_evidence": dict(evidence),
    }


def format_float(value: Any, spec: str) -> str:
    if value is None:
        return ""
    try:
        return format(float(value), spec)
    except Exception:
        return str(value)


def save_figure(result: dict[str, Any], image_path: Path) -> None:
    trials = [t for t in result.get("trials", []) if t.get("status") == "ok"]
    best = max(
        trials,
        key=lambda t: (float(t.get("top_probability") or 0.0), float(t.get("p1_margin_mean") or 0.0)),
        default=None,
    )
    fig = plt.figure(figsize=(15.5, 9.5))
    gs = fig.add_gridspec(nrows=2, ncols=1, height_ratios=[3.0, 2.4])
    ax = fig.add_subplot(gs[0])
    txt = fig.add_subplot(gs[1])
    if best is not None:
        p1s = best["p1_by_original_qubit"]
        x = np.arange(len(p1s))
        ax.bar(x, p1s, color=["#2c6fbb" if p >= 0.5 else "#b64f3a" for p in p1s], width=0.86)
        ax.axhline(0.5, color="#222", linestyle="--", linewidth=1.0)
        ax.set_ylim(-0.02, 1.02)
        ax.set_xlabel("original qubit index")
        ax.set_ylabel("P(q = 1) from samples")
        step = 1 if len(p1s) <= 32 else max(1, len(p1s) // 24)
        ax.set_xticks(x[::step])
        ax.set_title(f"Graph/tree-aware MPS fallback: {result.get('challenge_label')}")
    else:
        ax.axis("off")
        ax.text(0.01, 0.95, f"Status: {result.get('status')} {result.get('error', '')}", va="top")
    final = result.get("final_candidate", {})
    validation = result.get("validation", {})
    params = result.get("parameters", {})
    graph = result.get("graph", {})
    lines = [
        f"QASM: {result.get('qasm')}",
        "Method: graph/mincut-derived qubit orderings with Aer matrix_product_state sampling.",
        "Status: geometry-aware MPS fallback; not a full TensorNetworkQuantumSimulator.jl boundary-MPS TNS implementation.",
        f"Parameters: order_methods={params.get('order_methods')}, bond_dims={params.get('bond_dims')}, shots={params.get('shots')}, trunc={params.get('mps_truncation_threshold')}",
        f"Graph: edges={graph.get('edge_count')}, density={format_float(graph.get('density'), '.4g')}, max_degree={graph.get('degree_max')}",
        f"Final candidate: {final.get('candidate_qiskit_order')} source={final.get('source')}",
        f"Known answer: {validation.get('known_answer')} match={validation.get('final_matches_known')}",
    ]
    if best is not None:
        lines.append(
            f"Best trial: order={best.get('order_method')}, bond={best.get('bond_dim')}, top={best.get('top_bitstring_qiskit_order')}, p={format_float(best.get('top_probability'), '.6g')}"
        )
    txt.axis("off")
    import textwrap

    txt.text(
        0.01,
        0.98,
        "\n".join(sum((textwrap.wrap(line, width=150) for line in lines), [])),
        va="top",
        ha="left",
        family="monospace",
        fontsize=8.4,
    )
    image_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(image_path, dpi=170)
    plt.close(fig)


def run(args: argparse.Namespace) -> dict[str, Any]:
    from qiskit import QuantumCircuit

    root = args.root.resolve()
    out_dir = (args.out_dir if args.out_dir.is_absolute() else root / args.out_dir).resolve()
    for sub in ["json", "images", "stats"]:
        (out_dir / sub).mkdir(parents=True, exist_ok=True)
    qasm_path = resolve_challenge(root, args)
    match = CHALLENGE_RE.match(qasm_path.name)
    if not match:
        raise ValueError(f"unexpected challenge file name: {qasm_path.name}")
    num_from_name, challenge_id = int(match.group(1)), int(match.group(2))
    label = f"{num_from_name}_{challenge_id}"
    base = f"challenge-{label}"
    json_path = out_dir / "json" / f"{base}.tree_tensor_mps.json"
    image_path = out_dir / "images" / f"{base}.tree_tensor_mps.png"
    stats_path = out_dir / "stats" / f"{base}.order_stats.json"
    params = {
        "order_methods": args.order_methods,
        "bond_dims": args.bond_dims,
        "shots": args.shots,
        "seed": args.seed,
        "mps_truncation_threshold": args.mps_truncation_threshold,
        "exact_max_qubits": args.exact_max_qubits,
        "top_k": args.top_k,
        "max_parallel_threads": args.max_parallel_threads,
    }
    result: dict[str, Any] = {
        "method": "tree_graph_ordered_mps_fallback",
        "ansatz_status": "fallback_not_true_boundary_mps_tns",
        "status": "started",
        "root": str(root),
        "qasm": rel_path(qasm_path, root),
        "difficulty": qasm_path.parent.name,
        "challenge_id": challenge_id,
        "challenge_label": label,
        "num_from_name": num_from_name,
        "output_json": rel_path(json_path, root),
        "output_stats_json": rel_path(stats_path, root),
        "output_image": rel_path(image_path, root),
        "parameters": params,
        "versions": package_versions(),
        "env": {
            key: os.environ.get(key)
            for key in [
                "SLURM_ARRAY_JOB_ID",
                "SLURM_ARRAY_TASK_ID",
                "SLURM_JOB_ID",
                "SLURM_JOB_PARTITION",
                "SLURM_CPUS_PER_TASK",
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
            ]
        },
        "figure_note": args.figure_note,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_json(json_path, result)
    t0 = time.perf_counter()
    try:
        qc = QuantumCircuit.from_qasm_file(str(qasm_path))
        unitary_qc = strip_to_unitary(qc)
        result.update(
            {
                "num_qubits": unitary_qc.num_qubits,
                "num_clbits": qc.num_clbits,
                "circuit_len": len(qc),
                "unitary_circuit_len": len(unitary_qc),
                "circuit_ops": dict(qc.count_ops()),
                "unitary_circuit_ops": dict(unitary_qc.count_ops()),
            }
        )
        graph = build_interaction_graph(unitary_qc)
        weights = graph.pop("weights")
        orders = make_orders(weights, args.order_methods)
        graph["order_summaries"] = [
            {
                "method": row["method"],
                "duplicate_of": row.get("duplicate_of"),
                "span_stats": row["span_stats"],
                "tree_depth": row.get("tree_depth"),
                "order_prefix": row["order"][:20],
            }
            for row in orders
        ]
        result["graph"] = graph
        write_json(stats_path, {"graph": graph, "orders": orders})
        exact = exact_peak(unitary_qc, args.exact_max_qubits, args.top_k)
        result["exact"] = exact
        write_json(json_path, result)
        trials = []
        for order_row in orders:
            if order_row.get("duplicate_of") and not args.run_duplicate_orders:
                continue
            for bond_dim in args.bond_dims:
                trial = run_mps_trial(
                    unitary_qc,
                    order_row,
                    bond_dim,
                    args.shots,
                    args.seed + len(trials),
                    args.mps_truncation_threshold,
                    args.max_parallel_threads,
                )
                trials.append(trial)
                result["trials"] = trials
                write_json(json_path, result)
        final = select_final_candidate(trials, exact)
        known = KNOWN_ANSWERS.get(challenge_id)
        result.update(
            {
                "status": "ok" if trials or exact.get("status") == "ok" else "no_trials",
                "trials": trials,
                "final_candidate": final,
                "validation": {
                    "known_answer": known,
                    "final_matches_known": (final.get("candidate_qiskit_order") == known) if known else None,
                    "known_answers_are_qiskit_counts_order": True,
                    "bit_order_note": "Right-most bit is qubit 0.",
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        result.update({"status": "error", "error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()})
    finally:
        result["total_seconds"] = time.perf_counter() - t0
        result["max_rss_mb"] = rss_mb()
        result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        save_figure(result, image_path)
        write_json(json_path, result)
        print(json.dumps(json_safe(result), sort_keys=True), flush=True)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--qasm", type=Path, default=None)
    parser.add_argument("--challenge-id", type=int, default=None)
    parser.add_argument("--array-index", type=int, default=None)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs" / "tree_tensor_sim" / "pilot")
    parser.add_argument("--order-methods", nargs="+", default=["native", "rcm", "spectral", "mincut", "greedy"])
    parser.add_argument("--bond-dims", nargs="+", type=int, default=[64])
    parser.add_argument("--shots", type=int, default=4096)
    parser.add_argument("--seed", type=int, default=20260605)
    parser.add_argument("--mps-truncation-threshold", type=float, default=1e-10)
    parser.add_argument("--exact-max-qubits", type=int, default=24)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--max-parallel-threads", type=int, default=int(os.environ.get("SLURM_CPUS_PER_TASK", "1")))
    parser.add_argument("--run-duplicate-orders", action="store_true")
    parser.add_argument("--figure-note", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run(args)
    return 0 if result.get("status") in {"ok", "no_trials"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
