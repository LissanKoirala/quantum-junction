#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import heapq
import importlib.metadata
import inspect
import json
import os
import re
import resource
import sys
import textwrap
import time
import traceback
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CHALLENGE_RE = re.compile(r"challenge-(\d+)_(\d+)\.qasm$")
KNOWN = {
    "8_1": "10101101",
    "16_2": "1010101011001000",
    "24_3": "011110010000101010001000",
    "28_4": "1111111000101010110110011111",
    "8_11": "01001110",
    "16_12": "1111000101101011",
    "24_13": "111110011111001011010001",
    "8_27": "11001001",
    "16_28": "1101001111011100",
    "24_29": "110100010111100001001001",
}


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def json_safe(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [json_safe(v) for v in x]
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    return repr(x)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(data), indent=2, sort_keys=True) + "\n")


def versions() -> dict[str, str]:
    out = {}
    for name in ["qiskit", "qiskit-aer", "qiskit-quimb", "quimb", "torch", "numpy", "scipy"]:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = "not-installed"
    return out


def api_features() -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        import quimb.tensor as qtn

        out["quimb_has_CircuitMPS"] = hasattr(qtn, "CircuitMPS")
        out["quimb_has_CircuitPermMPS"] = hasattr(qtn, "CircuitPermMPS")
        out["quimb_tree_like_public_names"] = sorted(
            name for name in dir(qtn) if "tree" in name.lower() or "ttn" in name.lower()
        )
        out["CircuitMPS_signature"] = str(inspect.signature(qtn.CircuitMPS))
    except Exception as exc:  # noqa: BLE001
        out["quimb_error"] = repr(exc)
    try:
        import qiskit_quimb

        out["quimb_circuit_signature"] = str(inspect.signature(qiskit_quimb.quimb_circuit))
    except Exception as exc:  # noqa: BLE001
        out["qiskit_quimb_error"] = repr(exc)
    return out


def challenge_paths(root: Path) -> list[Path]:
    return sorted((root / "challenges").glob("*/*.qasm"), key=lambda p: (p.parent.name, p.name))


def resolve_challenge(root: Path, challenge_id: int | None, qasm: Path | None) -> Path:
    if qasm is not None:
        return (qasm if qasm.is_absolute() else root / qasm).resolve()
    if challenge_id is None:
        raise ValueError("provide --challenge-id or --qasm")
    hits = []
    for path in challenge_paths(root):
        match = CHALLENGE_RE.match(path.name)
        if match and int(match.group(2)) == challenge_id:
            hits.append(path)
    if len(hits) != 1:
        raise ValueError(f"expected one challenge for id {challenge_id}, found {hits}")
    return hits[0].resolve()


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def bit_index(circuit: Any, bit: Any) -> int:
    return int(circuit.find_bit(bit).index)


def strip_measure(circuit: Any) -> tuple[Any, bool]:
    if "measure" not in circuit.count_ops():
        return circuit, False
    return circuit.remove_final_measurements(inplace=False), True


def graph_from_circuit(circuit: Any, graph_ops: set[str], recency_alpha: float) -> dict[str, Any]:
    n = circuit.num_qubits
    weights = np.zeros((n, n), dtype=float)
    counts = np.zeros((n, n), dtype=int)
    rows = []
    data = list(circuit.data)
    denom = max(1, len(data) - 1)
    twoq = 0
    used = 0
    for idx, inst in enumerate(data):
        if len(inst.qubits) == 2:
            twoq += 1
        if inst.operation.name not in graph_ops or len(inst.qubits) != 2:
            continue
        q0, q1 = sorted(bit_index(circuit, bit) for bit in inst.qubits)
        inc = 1.0 + recency_alpha * idx / denom
        weights[q0, q1] += inc
        weights[q1, q0] += inc
        counts[q0, q1] += 1
        counts[q1, q0] += 1
        used += 1
    for u in range(n):
        for v in range(u + 1, n):
            if counts[u, v]:
                rows.append({"u": u, "v": v, "count": int(counts[u, v]), "weight": float(weights[u, v])})
    rows.sort(key=lambda r: (-r["weight"], r["u"], r["v"]))
    deg = weights.sum(axis=1)
    return {
        "weights": weights,
        "num_edges": len(rows),
        "two_qubit_ops_seen": twoq,
        "graph_ops_seen": used,
        "weighted_degree": deg,
        "top_edges": rows[:24],
    }


def connected_components(weights: np.ndarray) -> list[list[int]]:
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
            for nxt in np.flatnonzero(weights[node] > 0):
                nxt = int(nxt)
                if not seen[nxt]:
                    seen[nxt] = True
                    stack.append(nxt)
        comps.append(sorted(comp))
    return comps


def mst_edges(weights: np.ndarray) -> list[dict[str, Any]]:
    n = weights.shape[0]
    deg = weights.sum(axis=1)
    roots = sorted(range(n), key=lambda i: (-deg[i], i))
    seen = [False] * n
    edges = []
    for root in roots:
        if seen[root]:
            continue
        seen[root] = True
        heap: list[tuple[float, int, int]] = []
        for nxt in np.flatnonzero(weights[root] > 0):
            heapq.heappush(heap, (-float(weights[root, nxt]), root, int(nxt)))
        while heap:
            neg_w, u, v = heapq.heappop(heap)
            if seen[v]:
                continue
            seen[v] = True
            edges.append({"u": u, "v": v, "weight": -neg_w})
            for nxt in np.flatnonzero(weights[v] > 0):
                nxt = int(nxt)
                if not seen[nxt]:
                    heapq.heappush(heap, (-float(weights[v, nxt]), v, nxt))
    return edges


def order_spectral(weights: np.ndarray) -> list[int]:
    n = weights.shape[0]
    if n <= 2 or not np.any(weights > 0):
        return list(range(n))
    deg = weights.sum(axis=1)
    comps = connected_components(weights)
    comps.sort(key=lambda c: (-sum(float(deg[i]) for i in c), min(c)))
    order: list[int] = []
    for comp in comps:
        if len(comp) <= 2:
            order.extend(sorted(comp, key=lambda i: (-deg[i], i)))
            continue
        sub_w = weights[np.ix_(comp, comp)]
        sub_deg = sub_w.sum(axis=1)
        lap = np.diag(sub_deg) - sub_w
        vals, vecs = np.linalg.eigh(lap)
        fiedler = vecs[:, np.argsort(vals)[1]]
        order.extend([node for _x, _d, node in sorted(zip(fiedler, -sub_deg, comp))])
    return order


def order_mst_dfs(weights: np.ndarray) -> list[int]:
    n = weights.shape[0]
    deg = weights.sum(axis=1)
    adj = {i: [] for i in range(n)}
    for edge in mst_edges(weights):
        u, v, w = int(edge["u"]), int(edge["v"]), float(edge["weight"])
        adj[u].append((v, w))
        adj[v].append((u, w))
    seen = [False] * n
    order = []

    def dfs(node: int) -> None:
        seen[node] = True
        order.append(node)
        for child, _w in sorted(adj[node], key=lambda item: (-item[1], -deg[item[0]], item[0])):
            if not seen[child]:
                dfs(child)

    for root in sorted(range(n), key=lambda i: (-deg[i], i)):
        if not seen[root]:
            dfs(root)
    return order


def order_rcm(weights: np.ndarray) -> list[int]:
    try:
        from scipy.sparse import csr_matrix
        from scipy.sparse.csgraph import reverse_cuthill_mckee
    except Exception:
        return order_spectral(weights)
    if not np.any(weights > 0):
        return list(range(weights.shape[0]))
    adj = (weights > 0).astype(np.int8)
    return [int(i) for i in reverse_cuthill_mckee(csr_matrix(adj), symmetric_mode=True)]


def derive_order(weights: np.ndarray, method: str) -> list[int]:
    if method == "identity":
        return list(range(weights.shape[0]))
    if method == "degree":
        deg = weights.sum(axis=1)
        return sorted(range(weights.shape[0]), key=lambda i: (-deg[i], i))
    if method == "mst_dfs":
        return order_mst_dfs(weights)
    if method == "rcm":
        return order_rcm(weights)
    if method == "weighted_spectral":
        return order_spectral(weights)
    raise ValueError(f"unknown order method {method}")


def order_stats(order: list[int], weights: np.ndarray) -> dict[str, Any]:
    pos = {q: i for i, q in enumerate(order)}
    total_w = 0.0
    weighted_len = 0.0
    max_len = 0
    for u in range(weights.shape[0]):
        for v in range(u + 1, weights.shape[0]):
            w = float(weights[u, v])
            if not w:
                continue
            dist = abs(pos[u] - pos[v])
            total_w += w
            weighted_len += w * dist
            max_len = max(max_len, dist)
    return {
        "weighted_edge_length_sum": weighted_len,
        "weighted_edge_length_mean": weighted_len / total_w if total_w else 0.0,
        "max_edge_length": max_len,
    }


def remap_circuit(circuit: Any, logical_to_site: list[int]) -> Any:
    from qiskit import QuantumCircuit

    mapped = QuantumCircuit(circuit.num_qubits)
    mapped.global_phase = circuit.global_phase
    for inst in circuit.data:
        if inst.operation.name == "measure":
            continue
        qargs = [logical_to_site[bit_index(circuit, bit)] for bit in inst.qubits]
        if inst.operation.name == "barrier":
            mapped.barrier(*qargs)
        else:
            mapped.append(inst.operation.copy(), qargs=qargs)
    return mapped


def choose_backend(name: str) -> tuple[Any, dict[str, Any]]:
    info = {"requested": name, "selected": "numpy", "cuda_available": False}
    if name == "numpy":
        return None, info
    try:
        import torch
    except Exception as exc:  # noqa: BLE001
        info["torch_error"] = repr(exc)
        if name == "cuda":
            raise
        return None, info
    info["cuda_available"] = bool(torch.cuda.is_available())
    info["torch_device_count"] = int(torch.cuda.device_count()) if info["cuda_available"] else 0
    if not info["cuda_available"]:
        if name == "cuda":
            raise RuntimeError("CUDA requested but unavailable")
        return None, info
    cap = torch.cuda.get_device_capability(0)
    arch = f"sm_{cap[0]}{cap[1]}"
    arch_list = list(torch.cuda.get_arch_list()) if hasattr(torch.cuda, "get_arch_list") else []
    info.update(
        {
            "cuda_device_name": torch.cuda.get_device_name(0),
            "cuda_device_capability": f"{cap[0]}.{cap[1]}",
            "torch_cuda_arch": arch,
            "torch_cuda_arch_list": arch_list,
        }
    )
    if arch_list and arch not in arch_list:
        info["fallback_reason"] = f"{arch} not in this PyTorch CUDA arch list"
        if name == "cuda":
            raise RuntimeError(info["fallback_reason"])
        return None, info

    def to_backend_cuda(array: Any) -> Any:
        if isinstance(array, torch.Tensor):
            return array.to("cuda")
        if isinstance(array, np.ndarray) and not array.flags.writeable:
            array = np.array(array, copy=True)
        return torch.as_tensor(array, device="cuda")

    info["selected"] = "cuda"
    return to_backend_cuda, info


def tn_info(tn: Any) -> dict[str, Any]:
    out = {}
    for name in ["num_tensors", "num_indices"]:
        attr = getattr(tn, name, None)
        try:
            out[name] = int(attr() if callable(attr) else attr)
        except Exception:
            pass
    try:
        out["max_bond"] = int(tn.max_bond())
    except Exception:
        pass
    try:
        out["total_tensor_elements"] = int(sum(t.size for t in tn))
    except Exception:
        pass
    return out


def projector_zero(tn: Any) -> Any:
    try:
        tensor = tn[0]
        backend = getattr(tensor, "backend", "")
        data = tensor.data
    except Exception:
        backend = ""
        data = None
    if backend == "torch" or "torch" in type(data).__module__:
        import torch

        dtype = getattr(data, "dtype", torch.complex128)
        device = getattr(data, "device", "cuda" if torch.cuda.is_available() else "cpu")
        return torch.tensor([[1.0, 0.0], [0.0, 0.0]], dtype=dtype, device=device)
    return np.array([[1.0, 0.0], [0.0, 0.0]], dtype=np.complex128)


def as_float(value: Any) -> float:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    return float(np.real(np.asarray(value)).item())


def p0s_from_mps(psi: Any, n: int) -> list[float]:
    pi0 = projector_zero(psi)
    p0s = []
    for site in range(n):
        try:
            val = psi.local_expectation_canonical(pi0, where=site, normalized=True)
        except AttributeError:
            try:
                val = psi.local_expectation(pi0, where=site, normalized=True)
            except TypeError:
                val = psi.local_expectation(pi0, where=[site], normalized=True)
        p0s.append(max(0.0, min(1.0, as_float(val))))
    return p0s


def site_bits_to_logical(site_bits: str, site_to_logical: list[int]) -> str:
    logical = ["0"] * len(site_bits)
    for site, bit in enumerate(site_bits):
        logical[site_to_logical[site]] = bit
    return "".join(logical)


def sample_counts(circ: Any, samples: int, seed: int, site_to_logical: list[int], top_k: int) -> dict[str, Any]:
    if samples <= 0:
        return {"status": "skipped", "requested_samples": samples}
    counts: collections.Counter[str] = collections.Counter()
    try:
        for sample in circ.sample(samples, seed=seed):
            site_bits = sample if isinstance(sample, str) else "".join(str(int(bit)) for bit in sample)
            qiskit_bits = site_bits_to_logical(site_bits, site_to_logical)[::-1]
            counts[qiskit_bits] += 1
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error_type": type(exc).__name__, "error": str(exc)}
    top = counts.most_common(top_k)
    return {
        "status": "ok",
        "observed_samples": sum(counts.values()),
        "top_qiskit_order": [{"bitstring": b, "count": c} for b, c in top],
        "top_bitstring_qiskit_order": top[0][0] if top else None,
        "top_count": top[0][1] if top else None,
        "top_fraction": top[0][1] / sum(counts.values()) if top else None,
    }


def save_figure(result: dict[str, Any], path: Path) -> None:
    p1s = result.get("p1s_logical_order") or []
    fig = plt.figure(figsize=(15.5, 10.5))
    gs = fig.add_gridspec(nrows=2, ncols=1, height_ratios=[3.0, 2.4])
    ax = fig.add_subplot(gs[0])
    txt = fig.add_subplot(gs[1])
    if result.get("status") == "ok" and p1s:
        x = np.arange(len(p1s))
        colors = ["#287271" if p >= 0.5 else "#b14d34" for p in p1s]
        ax.bar(x, p1s, width=0.85, color=colors)
        ax.axhline(0.5, color="#222", linestyle="--", linewidth=1.0)
        ax.set_ylim(-0.02, 1.02)
        ax.set_ylabel("P(original qubit = 1)")
        ax.set_xlabel("original qubit index")
        step = 1 if len(p1s) <= 40 else max(1, len(p1s) // 28)
        ax.set_xticks(x[::step])
        ax.set_title(
            f"Quimb graph/tree-ordered CircuitMPS: {result.get('challenge_label')} "
            f"({result.get('difficulty')}, {result.get('num_qubits')} qubits)"
        )
    else:
        ax.axis("off")
        ax.text(0.01, 0.95, result.get("error", "no probability data"), va="top", ha="left")

    params = result.get("parameters", {})
    sampling = result.get("sampling", {})
    validation = result.get("validation", {})
    backend = result.get("backend", {})
    env = result.get("env", {})
    lines = [
        f"QASM: {result.get('qasm')}",
        "Method: graph/tree-aware tensor network via graph-derived qubit order + Quimb CircuitMPS.",
        "True TTN/tree contraction status: no public Quimb TTN circuit-state API found; this is an explicitly labeled graph-ordered MPS fallback.",
        f"Graph/tree: order_method={params.get('order_method')}, tree_method=maximum_spanning_tree, graph_ops={params.get('graph_ops')}, recency_alpha={params.get('recency_alpha')}",
        f"Parameters: backend={params.get('backend_requested')}->{backend.get('selected')}, gate_contract={params.get('gate_contract')}, max_bond={params.get('max_bond')}, cutoff={params.get('cutoff')}, samples={params.get('samples')}, seed={params.get('seed')}",
        f"Raw site-order candidate: {result.get('candidate_site_order')}",
        f"Logical q0..qN candidate: {result.get('candidate_logical_order')}",
        f"Qiskit/counts-order marginal candidate: {result.get('candidate_qiskit_order')}",
        f"Qiskit/counts-order sample top: {sampling.get('top_bitstring_qiskit_order')}",
        f"Final selected Qiskit/counts-order candidate: {result.get('final_candidate_qiskit_order')}",
        f"Validation: {validation.get('status')} known={validation.get('known_answer_qiskit_order')} details={validation.get('candidate_results')}",
        f"Runtime/resource: total={result.get('total_seconds'):.3f}s max_rss={result.get('max_rss_mb'):.1f}MB slurm={env.get('SLURM_ARRAY_JOB_ID') or env.get('SLURM_JOB_ID')} mps={result.get('mps_info')}",
    ]
    if params.get("figure_note"):
        lines.append(f"Note: {params.get('figure_note')}")
    txt.axis("off")
    txt.text(
        0.01,
        0.98,
        "\n".join(sum((textwrap.wrap(line, width=150) for line in lines), [])),
        va="top",
        ha="left",
        family="monospace",
        fontsize=8.1,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def validate(label: str, **candidates: str | None) -> dict[str, Any]:
    known = KNOWN.get(label)
    out = {"known_answer_qiskit_order": known}
    if known is None:
        out["status"] = "unknown"
        return out
    results = {name: (bitstring == known) for name, bitstring in candidates.items() if bitstring is not None}
    out["candidate_results"] = results
    out["status"] = "correct" if any(results.values()) else "incorrect"
    return out


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    out_dir = (args.out_dir if args.out_dir.is_absolute() else root / args.out_dir).resolve()
    for sub in ["json", "images", "stats"]:
        (out_dir / sub).mkdir(parents=True, exist_ok=True)
    qasm = resolve_challenge(root, args.challenge_id, args.qasm)
    match = CHALLENGE_RE.match(qasm.name)
    if not match:
        raise ValueError(f"unexpected challenge name {qasm.name}")
    label = f"{match.group(1)}_{match.group(2)}"
    base = f"challenge-{label}.quimb_tree_graph_mps"
    json_path = out_dir / "json" / f"{base}.json"
    image_path = out_dir / "images" / f"{base}.png"
    stats_path = out_dir / "stats" / f"{base}.stats.jsonl"
    params = {
        "backend_requested": args.backend,
        "max_bond": args.max_bond,
        "cutoff": args.cutoff,
        "gate_contract": args.gate_contract,
        "order_method": args.order_method,
        "graph_ops": args.graph_ops,
        "recency_alpha": args.recency_alpha,
        "samples": args.samples,
        "sample_top_k": args.sample_top_k,
        "seed": args.seed,
        "dtype": args.dtype,
        "figure_note": args.figure_note,
    }
    result: dict[str, Any] = {
        "method": "quimb_graph_tree_ordered_circuit_mps",
        "method_classification": "graph_ordered_mps_fallback",
        "status": "started",
        "root": str(root),
        "qasm": rel(qasm, root),
        "difficulty": qasm.parent.name,
        "challenge_label": label,
        "challenge_id": int(match.group(2)),
        "parameters": params,
        "versions": versions(),
        "api_features": api_features(),
        "output_json": rel(json_path, root),
        "output_image": rel(image_path, root),
        "output_stats_jsonl": rel(stats_path, root),
        "env": {
            key: os.environ.get(key)
            for key in [
                "SLURM_ARRAY_JOB_ID",
                "SLURM_ARRAY_TASK_ID",
                "SLURM_JOB_ID",
                "SLURM_JOB_PARTITION",
                "SLURM_CPUS_PER_TASK",
                "CUDA_VISIBLE_DEVICES",
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
            ]
        },
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_json(json_path, result)
    stats = []

    def mark(stage: str, start: float, **extra: Any) -> None:
        row = {"stage": stage, "seconds": time.perf_counter() - start, "rss_mb": rss_mb()}
        row.update(extra)
        stats.append(row)

    t0 = time.perf_counter()
    try:
        from qiskit import QuantumCircuit
        from qiskit_quimb import quimb_circuit
        import quimb.tensor as qtn

        b0 = time.perf_counter()
        to_backend, backend_info = choose_backend(args.backend)
        result["backend"] = backend_info
        mark("backend", b0, backend=backend_info)

        p0 = time.perf_counter()
        qc = QuantumCircuit.from_qasm_file(str(qasm))
        result["num_qubits"] = qc.num_qubits
        result["num_clbits"] = qc.num_clbits
        result["circuit_len"] = len(qc)
        result["circuit_ops"] = dict(qc.count_ops())
        qc, removed = strip_measure(qc)
        result["removed_final_measurements"] = removed
        result["unitary_circuit_len"] = len(qc)
        result["unitary_circuit_ops"] = dict(qc.count_ops())
        mark("parse_qasm", p0)

        g0 = time.perf_counter()
        graph = graph_from_circuit(qc, set(args.graph_ops), args.recency_alpha)
        weights = graph["weights"]
        order = derive_order(weights, args.order_method)
        if sorted(order) != list(range(qc.num_qubits)):
            raise ValueError(f"invalid order {order}")
        logical_to_site = [0] * len(order)
        for site, logical in enumerate(order):
            logical_to_site[logical] = site
        result["graph"] = {
            "num_edges": graph["num_edges"],
            "two_qubit_ops_seen": graph["two_qubit_ops_seen"],
            "graph_ops_seen": graph["graph_ops_seen"],
            "weighted_degree": graph["weighted_degree"].tolist(),
            "top_edges": graph["top_edges"],
        }
        result["tree"] = {"method": "maximum_spanning_tree", "edges": mst_edges(weights)}
        result["ordering"] = {
            "site_to_logical_qubit": order,
            "logical_qubit_to_site": logical_to_site,
            "linear_order_stats": order_stats(order, weights),
            "identity_linear_order_stats": order_stats(list(range(qc.num_qubits)), weights),
        }
        mark("graph_order", g0, num_edges=graph["num_edges"])

        r0 = time.perf_counter()
        mapped = remap_circuit(qc, logical_to_site)
        result["mapped_circuit_len"] = len(mapped)
        result["mapped_circuit_ops"] = dict(mapped.count_ops())
        mark("remap", r0)

        m0 = time.perf_counter()
        circ = quimb_circuit(
            mapped,
            quimb_circuit_class=qtn.CircuitMPS,
            max_bond=args.max_bond,
            cutoff=args.cutoff,
            gate_contract=args.gate_contract,
            dtype=args.dtype,
            to_backend=to_backend,
        )
        result["mps_seconds"] = time.perf_counter() - m0
        try:
            result["fidelity_estimate"] = float(circ.fidelity_estimate())
            result["error_estimate"] = float(circ.error_estimate())
        except Exception as exc:  # noqa: BLE001
            result["fidelity_error"] = repr(exc)
        psi = circ.psi
        result["mps_info"] = tn_info(psi)
        mark("simulate_quimb_circuit_mps", m0, mps_info=result["mps_info"])

        e0 = time.perf_counter()
        site_p0s = p0s_from_mps(psi, qc.num_qubits)
        site_candidate = "".join("1" if p0 < 0.5 else "0" for p0 in site_p0s)
        logical_candidate = site_bits_to_logical(site_candidate, order)
        qiskit_candidate = logical_candidate[::-1]
        p1_site = [1.0 - p0 for p0 in site_p0s]
        p1_logical = [0.0] * len(p1_site)
        for site, value in enumerate(p1_site):
            p1_logical[order[site]] = value
        margins = [abs(value - 0.5) for value in p1_logical]
        result.update(
            {
                "candidate_site_order": site_candidate,
                "candidate_logical_order": logical_candidate,
                "candidate_qiskit_order": qiskit_candidate,
                "p0s_site_order": site_p0s,
                "p1s_site_order": p1_site,
                "p1s_logical_order": p1_logical,
                "p1_margin_min": min(margins) if margins else None,
                "p1_margin_mean": float(np.mean(margins)) if margins else None,
                "p1_margin_max": max(margins) if margins else None,
            }
        )
        mark("extract_marginals", e0, p1_margin_min=result["p1_margin_min"])

        s0 = time.perf_counter()
        sampling = sample_counts(circ, args.samples, args.seed, order, args.sample_top_k)
        result["sampling"] = sampling
        mark("sample_mps", s0, sampling_status=sampling.get("status"))

        final = sampling.get("top_bitstring_qiskit_order") or qiskit_candidate
        result["final_candidate_qiskit_order"] = final
        result["candidate_strategy"] = (
            "sample_top_qiskit_order" if sampling.get("top_bitstring_qiskit_order") else "marginal_qiskit_order"
        )
        result["validation"] = validate(
            label,
            marginal_qiskit_order=qiskit_candidate,
            sample_top_qiskit_order=sampling.get("top_bitstring_qiskit_order"),
            final_qiskit_order=final,
        )
        result["status"] = "ok"
    except Exception as exc:  # noqa: BLE001
        result.update(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
    finally:
        result["total_seconds"] = time.perf_counter() - t0
        result["max_rss_mb"] = rss_mb()
        result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        with stats_path.open("w") as f:
            for row in stats:
                f.write(json.dumps(json_safe(row), sort_keys=True) + "\n")
        save_figure(result, image_path)
        write_json(json_path, result)
        print(json.dumps(json_safe(result), sort_keys=True), flush=True)
    return result


def summarize(out_dir: Path, summary_path: Path, title: str) -> None:
    rows = []
    jobs = set()
    for path in sorted((out_dir / "json").glob("*.quimb_tree_graph_mps.json")):
        result = json.loads(path.read_text())
        env = result.get("env", {})
        job = env.get("SLURM_ARRAY_JOB_ID") or env.get("SLURM_JOB_ID")
        if job:
            jobs.add(str(job))
        rows.append(result)
    known = [r for r in rows if r.get("validation", {}).get("known_answer_qiskit_order")]
    correct = [r for r in known if r.get("validation", {}).get("status") == "correct"]
    lines = [
        f"# {title}",
        "",
        f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
        f"Output directory: `{out_dir}`",
        f"Slurm job IDs: `{', '.join(sorted(jobs)) if jobs else 'none'}`",
        "",
        f"Results: {len(rows)} JSON files, known-answer validations correct {len(correct)}/{len(known)}.",
        "",
        "| challenge | difficulty | q | status | backend | order | marginal | sample top | final | known | validation | sec | rss MB | max bond |",
        "| --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for r in rows:
        params = r.get("parameters", {})
        sampling = r.get("sampling", {})
        validation = r.get("validation", {})
        lines.append(
            "| "
            + " | ".join(
                [
                    str(r.get("challenge_label")),
                    str(r.get("difficulty")),
                    str(r.get("num_qubits")),
                    str(r.get("status")),
                    str(r.get("backend", {}).get("selected")),
                    str(params.get("order_method")),
                    f"`{r.get('candidate_qiskit_order')}`" if r.get("candidate_qiskit_order") else "",
                    f"`{sampling.get('top_bitstring_qiskit_order')}`"
                    if sampling.get("top_bitstring_qiskit_order")
                    else "",
                    f"`{r.get('final_candidate_qiskit_order')}`" if r.get("final_candidate_qiskit_order") else "",
                    f"`{validation.get('known_answer_qiskit_order')}`"
                    if validation.get("known_answer_qiskit_order")
                    else "",
                    str(validation.get("status")),
                    f"{float(r.get('total_seconds', 0.0)):.2f}",
                    f"{float(r.get('max_rss_mb', 0.0)):.1f}",
                    str(r.get("mps_info", {}).get("max_bond", "")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Outputs:",
            f"- JSON: `{out_dir / 'json'}`",
            f"- Images: `{out_dir / 'images'}`",
            f"- Stats JSONL: `{out_dir / 'stats'}`",
            f"- Logs: `{out_dir / 'logs'}`",
        ]
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--challenge-id", type=int)
    parser.add_argument("--qasm", type=Path)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs" / "tree_tensor_sim" / "quimb_pilot")
    parser.add_argument("--backend", choices=["auto", "cuda", "numpy"], default="auto")
    parser.add_argument("--max-bond", type=int, default=512)
    parser.add_argument("--cutoff", type=float, default=1e-7)
    parser.add_argument("--gate-contract", choices=["auto-mps", "swap+split", "nonlocal"], default="swap+split")
    parser.add_argument(
        "--order-method",
        choices=["weighted_spectral", "mst_dfs", "rcm", "degree", "identity"],
        default="weighted_spectral",
    )
    parser.add_argument("--graph-ops", nargs="+", default=["cx", "swap"])
    parser.add_argument("--recency-alpha", type=float, default=0.15)
    parser.add_argument("--samples", type=int, default=2048)
    parser.add_argument("--sample-top-k", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20260605)
    parser.add_argument("--dtype", default="complex128")
    parser.add_argument("--figure-note", default="")
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--summary-path", type=Path)
    parser.add_argument("--summary-title", default="Quimb graph/tree tensor pilot")
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = (args.out_dir if args.out_dir.is_absolute() else root / args.out_dir).resolve()
    if args.summarize:
        summary_path = args.summary_path or out_dir / "SUMMARY.md"
        if not summary_path.is_absolute():
            summary_path = root / summary_path
        summarize(out_dir, summary_path, args.summary_title)
        return 0
    result = run(args)
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
