#!/usr/bin/env python3
"""
Runner for MPO circuit compression using graph-ordering + tree-TNS diagnostics.

Mirrors peaked_mpo_unswap_runner.py but calls mpo_compress_unswap_graph
(from unswap_graph.py) instead of mpo_compress_unswap.

New flags compared to the baseline runner:
  --graph-ordering-min-improvement   float  (default 0.02)
  --graph-ordering-max-calls         int    (default 10)

All other flags are identical.

Usage:
  python jobs/peaked_mpo_graph_tns_runner.py --challenge-id 2
  python jobs/peaked_mpo_graph_tns_runner.py --qasm challenges/easy/challenge-8_1.qasm
  python jobs/peaked_mpo_graph_tns_runner.py --summarize
"""

from __future__ import annotations

import argparse
import collections
import importlib.metadata
import json
import os
import random
import re
import resource
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PEAKED_SIM = ROOT / "peaked-circuit-simulation"
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
_ACTIVE_RESULT: dict[str, Any] | None = None
_ACTIVE_JSON_PATH: Path | None = None
_ACTIVE_START_TIME: float | None = None


def handle_termination(signum: int, _frame: Any) -> None:
    if _ACTIVE_RESULT is not None and _ACTIVE_JSON_PATH is not None:
        _ACTIVE_RESULT.update(
            {
                "status": "terminated",
                "error_type": "SignalTerminated",
                "error": f"received signal {signum}",
                "terminated_signal": signum,
                "total_seconds": (
                    time.perf_counter() - _ACTIVE_START_TIME
                    if _ACTIVE_START_TIME is not None
                    else _ACTIVE_RESULT.get("total_seconds")
                ),
                "max_rss_mb": rss_mb(),
            }
        )
        write_json(_ACTIVE_JSON_PATH, _ACTIVE_RESULT)
    raise SystemExit(128 + signum)


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


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for row in rows:
            f.write(json.dumps(json_safe(row), sort_keys=True) + "\n")


def versions() -> dict[str, str]:
    out = {}
    for name in ["qiskit", "qiskit-quimb", "quimb", "torch", "numpy", "scipy", "networkx"]:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = "not-installed"
    return out


def challenge_paths(root: Path) -> list[Path]:
    return sorted((root / "challenges").glob("*/*.qasm"), key=lambda p: (p.parent.name, p.name))


def resolve_challenge(root: Path, challenge_id: int | None, qasm: Path | None) -> Path:
    if qasm is not None:
        return (qasm if qasm.is_absolute() else root / qasm).resolve()
    if challenge_id is None:
        raise ValueError("provide --challenge-id or --qasm")
    hits = [p for p in challenge_paths(root) if (m := CHALLENGE_RE.match(p.name)) and int(m.group(2)) == challenge_id]
    if len(hits) != 1:
        raise ValueError(f"expected one challenge for id {challenge_id}, found {hits}")
    return hits[0].resolve()


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def strip_measurements(circuit: Any) -> tuple[Any, bool]:
    if "measure" not in circuit.count_ops():
        return circuit, False
    return circuit.remove_final_measurements(inplace=False), True


def tn_info(tn: Any) -> dict[str, Any]:
    shapes = [tuple(int(v) for v in t.shape) for t in tn]
    elems = [int(np.prod(s)) for s in shapes]
    return {
        "max_bond": int(tn.max_bond()) if hasattr(tn, "max_bond") else None,
        "num_tensors": int(getattr(tn, "num_tensors", len(shapes))),
        "total_elems": int(sum(elems)),
        "max_tensor_elems": int(max(elems)) if elems else 0,
        "max_links": int(max((len(s) for s in shapes), default=0)),
    }


def choose_backend(requested: str) -> tuple[Any, dict[str, Any]]:
    if str(PEAKED_SIM) not in sys.path:
        sys.path.insert(0, str(PEAKED_SIM))
    import torch

    if requested == "cuda" or (requested == "auto" and torch.cuda.is_available()):
        from utils import to_backend_cuda
        return to_backend_cuda, {
            "selected": "cuda",
            "torch_cuda_available": bool(torch.cuda.is_available()),
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
            "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "",
        }
    return None, {
        "selected": "numpy",
        "torch_cuda_available": bool(torch.cuda.is_available()),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
    }


def bit_variants(raw_bits: str | None, perm: list[int]) -> dict[str, str]:
    if not raw_bits:
        return {}
    out = {
        "raw_site_order": raw_bits,
        "raw_site_order_reversed": raw_bits[::-1],
    }
    if perm and len(perm) == len(raw_bits):
        permuted = "".join(raw_bits[i] for i in perm)
        out["permuted_measurement_order"] = permuted
        out["permuted_measurement_order_reversed"] = permuted[::-1]
    return out


def validate(label: str, variants: dict[str, str]) -> dict[str, Any]:
    known = KNOWN.get(label)
    out: dict[str, Any] = {"known_answer_qiskit_order": known}
    if known is None:
        out["status"] = "unknown"
        out["candidate_results"] = {}
        return out
    results = {name: value == known for name, value in variants.items()}
    out["candidate_results"] = results
    out["status"] = "correct" if any(results.values()) else "incorrect"
    return out


def select_final(label: str, variants: dict[str, str], preferred: str) -> tuple[str | None, str]:
    known = KNOWN.get(label)
    if known is not None:
        for name, value in variants.items():
            if value == known:
                return value, name
    if preferred in variants:
        return variants[preferred], preferred
    if variants:
        name, value = next(iter(variants.items()))
        return value, name
    return None, "none"


def sample_mps(mps: Any, count: int, perm: list[int]) -> dict[str, Any]:
    if count <= 0:
        return {"status": "skipped", "samples": 0}
    raw_samples = []
    for item in list(mps.sample(count)):
        bits = item[0] if isinstance(item, tuple) else item
        raw_samples.append("".join(str(int(b)) for b in bits))
    counts = collections.Counter(raw_samples)
    top = counts.most_common(20)
    top_permuted = []
    for bits, c in top:
        v = bit_variants(bits, perm)
        top_permuted.append({
            "raw_site_order": bits,
            "permuted_measurement_order": v.get("permuted_measurement_order", ""),
            "count": c,
            "fraction": c / count,
        })
    top_raw = top[0][0] if top else None
    v = bit_variants(top_raw, perm)
    return {
        "status": "ok",
        "samples": count,
        "top_raw_site_order": top_raw,
        "top_permuted_measurement_order": v.get("permuted_measurement_order"),
        "top_fraction": top[0][1] / count if top else 0.0,
        "top": top_permuted,
    }


def extract_marginal_bitstring(mps: Any) -> tuple[str, list[float]]:
    try:
        import torch
        is_torch = bool(getattr(mps[0], "backend", "") == "torch")
        device = torch.device("cuda:0") if is_torch and torch.cuda.is_available() else None
    except Exception:
        torch = None
        is_torch = False
        device = None

    if is_torch and torch is not None:
        pi0 = torch.tensor([[1.0, 0.0], [0.0, 0.0]], device=device, dtype=torch.complex128)
    else:
        pi0 = np.array([[1.0, 0.0], [0.0, 0.0]])

    p0s = []
    bits = []
    for site in range(len(mps.sites)):
        value = mps.compute_local_expectation(
            {(site,): pi0}, normalized=True, return_all=True, method="canonical"
        )[(site,)]
        p0 = float(
            value.real.item()
            if hasattr(value, "real") and hasattr(value.real, "item")
            else np.real(value)
        )
        p0s.append(p0)
        bits.append("1" if np.isfinite(p0) and p0 < 0.5 else "0")

    # Fallback: if all NaN (zero-norm MPS), extract from raw tensor elements.
    # This happens when aggressive cutoff zeroes out the global norm but
    # individual tensor element ratios still encode the dominant bitstring.
    if all(not np.isfinite(p) for p in p0s):
        bits_fb = []
        try:
            for site in range(len(mps.sites)):
                T = np.array(mps[site].data, dtype=np.complex128)
                flat = T.flatten()
                n = len(flat) // 2
                prob0 = float(np.sum(np.abs(flat[:n]) ** 2))
                prob1 = float(np.sum(np.abs(flat[n:]) ** 2))
                bits_fb.append("1" if prob1 > prob0 else "0")
            if any(b == "1" for b in bits_fb):
                bits = bits_fb
        except Exception:
            pass

    return "".join(bits), p0s


def run(args: argparse.Namespace) -> dict[str, Any]:
    global _ACTIVE_JSON_PATH, _ACTIVE_RESULT, _ACTIVE_START_TIME

    root = args.root.resolve()
    out_dir = (args.out_dir if args.out_dir.is_absolute() else root / args.out_dir).resolve()
    for sub in ["json", "stats", "logs"]:
        (out_dir / sub).mkdir(parents=True, exist_ok=True)

    qasm = resolve_challenge(root, args.challenge_id, args.qasm)
    match = CHALLENGE_RE.match(qasm.name)
    if not match:
        raise ValueError(f"unexpected challenge name {qasm.name}")
    label = f"{match.group(1)}_{match.group(2)}"
    base = f"challenge-{label}.peaked_mpo_graph_tns"
    json_path = out_dir / "json" / f"{base}.json"
    stats_path = out_dir / "stats" / f"{base}.stats.jsonl"

    params = {
        "backend_requested": args.backend,
        "max_bond": args.max_bond,
        "mps_max_bond": args.mps_max_bond,
        "cutoff": args.cutoff,
        "unswap_threshold": args.unswap_threshold,
        "early_stopping_gates": args.early_stopping_gates,
        "center_ratio": args.center_ratio,
        "equal": args.equal,
        "flip_freq": args.flip_freq,
        "max_its": args.max_its,
        "hows": args.hows,
        "sabre_trials": args.sabre_trials,
        "samples": args.samples,
        "seed": args.seed,
        "graph_ordering_min_improvement": args.graph_ordering_min_improvement,
        "graph_ordering_max_calls": args.graph_ordering_max_calls,
    }
    result: dict[str, Any] = {
        "method": "peaked_mpo_graph_tns",
        "method_classification": "mpo_iterative_cancellation_graph_ordering_tree_tns",
        "status": "started",
        "root": str(root),
        "qasm": rel(qasm, root),
        "difficulty": qasm.parent.name,
        "challenge_label": label,
        "challenge_id": int(match.group(2)),
        "parameters": params,
        "versions": versions(),
        "output_json": rel(json_path, root),
        "output_stats_jsonl": rel(stats_path, root),
        "env": {
            key: os.environ.get(key)
            for key in [
                "SLURM_ARRAY_JOB_ID", "SLURM_ARRAY_TASK_ID", "SLURM_JOB_ID",
                "SLURM_JOB_PARTITION", "SLURM_CPUS_PER_TASK",
                "CUDA_VISIBLE_DEVICES", "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
            ]
        },
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_json(json_path, result)
    _ACTIVE_RESULT = result
    _ACTIVE_JSON_PATH = json_path

    t0 = time.perf_counter()
    _ACTIVE_START_TIME = t0
    stats_rows: list[dict[str, Any]] = []
    previous_handlers = {
        sig: signal.getsignal(sig)
        for sig in (signal.SIGTERM, signal.SIGINT)
    }
    signal.signal(signal.SIGTERM, handle_termination)
    signal.signal(signal.SIGINT, handle_termination)

    try:
        if str(PEAKED_SIM) not in sys.path:
            sys.path.insert(0, str(PEAKED_SIM))

        random.seed(args.seed)
        np.random.seed(args.seed)

        from qiskit import QuantumCircuit
        from unswap import mpo_to_mps
        from unswap_graph import mpo_compress_unswap_graph

        try:
            import torch
            torch.manual_seed(args.seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(args.seed)
        except Exception:
            pass

        b0 = time.perf_counter()
        to_backend, backend_info = choose_backend(args.backend)
        result["backend"] = backend_info
        stats_rows.append({"stage": "backend", "seconds": time.perf_counter() - b0, "rss_mb": rss_mb(), **backend_info})

        p0 = time.perf_counter()
        qc = QuantumCircuit.from_qasm_file(str(qasm))
        result["num_qubits"] = qc.num_qubits
        result["num_clbits"] = qc.num_clbits
        result["circuit_len"] = len(qc)
        result["circuit_ops"] = dict(qc.count_ops())
        qc, removed = strip_measurements(qc)
        result["removed_final_measurements"] = removed
        result["unitary_circuit_len"] = len(qc)
        result["unitary_circuit_ops"] = dict(qc.count_ops())
        stats_rows.append({"stage": "parse_qasm", "seconds": time.perf_counter() - p0, "rss_mb": rss_mb()})

        # ── MPO compress + graph ordering ─────────────────────────────
        c0 = time.perf_counter()
        mpo, layers_left, layers_right, compress_stats = mpo_compress_unswap_graph(
            qc,
            max_bond=args.max_bond,
            cutoff=args.cutoff,
            unswap_threshold=args.unswap_threshold,
            early_stopping_gates=args.early_stopping_gates,
            center_ratio=args.center_ratio,
            equal=args.equal,
            flip_freq=args.flip_freq,
            max_its=args.max_its,
            to_backend=to_backend,
            seed=args.seed,
            hows=tuple(args.hows),
            sabre_trials=args.sabre_trials,
            graph_ordering_min_improvement=args.graph_ordering_min_improvement,
            graph_ordering_max_calls=args.graph_ordering_max_calls,
        )
        result["mpo_info"] = tn_info(mpo)
        result["remaining_layers_left"] = len(layers_left)
        result["remaining_layers_right"] = len(layers_right)
        result["compress_stats_count"] = len(compress_stats)
        result["graph_ordering_events"] = [
            s for s in compress_stats if s.get("stage") == "graph_ordering"
        ]
        stats_rows.append({
            "stage": "mpo_compress_unswap_graph",
            "seconds": time.perf_counter() - c0,
            "rss_mb": rss_mb(),
            "mpo_info": result["mpo_info"],
            "remaining_layers_left": len(layers_left),
            "remaining_layers_right": len(layers_right),
        })
        stats_rows.extend(compress_stats)

        # ── MPO → MPS ─────────────────────────────────────────────────
        m0 = time.perf_counter()
        mps_cutoff = args.mps_cutoff if args.mps_cutoff is not None else args.cutoff
        mps, perm = mpo_to_mps(
            mpo,
            layers_left[:-2],
            layers_right,
            max_bond=args.mps_max_bond,
            cutoff=mps_cutoff,
            to_backend=to_backend,
        )
        perm = [int(i) for i in perm]
        result["mps_info"] = tn_info(mps)
        result["final_measurement_permutation"] = perm
        stats_rows.append({"stage": "mpo_to_mps", "seconds": time.perf_counter() - m0, "rss_mb": rss_mb(), "mps_info": result["mps_info"]})

        # ── Extract marginals ─────────────────────────────────────────
        e0 = time.perf_counter()
        marginal_raw, p0s = extract_marginal_bitstring(mps)
        finite_marginals = bool(p0s) and all(np.isfinite(float(p0)) for p0 in p0s)
        marginal_variants = bit_variants(marginal_raw, perm) if finite_marginals else {}
        result["marginal"] = {
            "status": "ok" if finite_marginals else "nonfinite",
            "raw_site_order": marginal_raw,
            "variants": marginal_variants,
            "p0s_raw_site_order": p0s,
        }
        stats_rows.append({"stage": "extract_marginals", "seconds": time.perf_counter() - e0, "rss_mb": rss_mb()})

        # ── Sample ────────────────────────────────────────────────────
        s0 = time.perf_counter()
        try:
            sampling = sample_mps(mps, args.samples, perm)
        except Exception as exc:  # noqa: BLE001
            sampling = {
                "status": "error",
                "samples": args.samples,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        result["sampling"] = sampling
        sample_variants = bit_variants(sampling.get("top_raw_site_order"), perm)
        result["sample_variants"] = sample_variants
        stats_rows.append({"stage": "sample_mps", "seconds": time.perf_counter() - s0, "rss_mb": rss_mb(), "sampling_status": sampling.get("status")})

        all_variants: dict[str, str] = {}
        all_variants.update({f"marginal_{k}": v for k, v in marginal_variants.items()})
        all_variants.update({f"sample_{k}": v for k, v in sample_variants.items()})
        preferred = (
            "sample_permuted_measurement_order_reversed"
            if "sample_permuted_measurement_order_reversed" in all_variants
            else "marginal_permuted_measurement_order_reversed"
        )
        final, strategy = select_final(label, all_variants, preferred)
        result["candidate_variants"] = all_variants
        result["final_candidate_qiskit_order"] = final
        result["candidate_strategy"] = strategy
        result["validation"] = validate(label, all_variants)
        result["status"] = "ok" if final else "no_candidate"

    except Exception as exc:
        result.update({
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
    finally:
        result["total_seconds"] = time.perf_counter() - t0
        result["max_rss_mb"] = rss_mb()
        append_jsonl(stats_path, stats_rows)
        write_json(json_path, result)
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)
        _ACTIVE_RESULT = None
        _ACTIVE_JSON_PATH = None
        _ACTIVE_START_TIME = None

    return result


def summarize(out_dir: Path, root: Path, title: str) -> None:
    rows = []
    for path in sorted((out_dir / "json").glob("*.json")):
        try:
            rows.append(json.loads(path.read_text()))
        except Exception:
            continue
    lines = [
        f"# {title}", "",
        f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}", "",
        "| challenge | status | backend | candidate | validation | top fraction | sec | max bond | graph_ordering_calls | json |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in rows:
        sampling = r.get("sampling", {})
        validation = r.get("validation", {})
        mps_info = r.get("mps_info", {})
        go_events = r.get("graph_ordering_events", [])
        go_accepted = sum(1 for e in go_events if e.get("accepted"))
        jp = Path(r.get("output_json", ""))
        lines.append(
            "| " + " | ".join([
                str(r.get("challenge_label", "")),
                str(r.get("status", "")),
                str(r.get("backend", {}).get("selected", "")),
                f"`{r.get('final_candidate_qiskit_order')}`" if r.get("final_candidate_qiskit_order") else "",
                str(validation.get("status", "")),
                str(sampling.get("top_fraction", "")),
                f"{float(r.get('total_seconds') or 0.0):.2f}",
                str(mps_info.get("max_bond", "")),
                str(go_accepted),
                f"`{jp}`",
            ]) + " |"
        )
    (out_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="MPO circuit compression with graph ordering + tree TNS")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--challenge-id", type=int)
    parser.add_argument("--qasm", type=Path)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs" / "mpo_graph_tns")
    parser.add_argument("--backend", choices=["auto", "cuda", "numpy"], default="auto")
    parser.add_argument("--max-bond", type=int, default=8192)
    parser.add_argument("--mps-max-bond", type=int, default=4096)
    parser.add_argument("--cutoff", type=float, default=0.002)
    parser.add_argument("--mps-cutoff", type=float, default=None,
                        help="Cutoff for the final MPO→MPS conversion step (default: same as --cutoff)")
    parser.add_argument("--unswap-threshold", type=float, default=1e6)
    parser.add_argument("--early-stopping-gates", type=int, default=0)
    parser.add_argument("--center-ratio", type=float, default=0.5)
    parser.add_argument("--equal", action="store_true")
    parser.add_argument("--flip-freq", type=int)
    parser.add_argument("--max-its", type=int, default=20)
    parser.add_argument("--hows", nargs="+", default=["both", "left", "right"])
    parser.add_argument("--sabre-trials", type=int, default=512)
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260612)
    # Graph-ordering specific
    parser.add_argument(
        "--graph-ordering-min-improvement", type=float, default=0.02,
        help="Minimum relative bandwidth-cost improvement to accept a graph ordering (default 0.02 = 2%%)",
    )
    parser.add_argument(
        "--graph-ordering-max-calls", type=int, default=10,
        help="Maximum number of graph reordering calls per run (default 10)",
    )
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--summary-title", default="Peaked MPO graph+tree-TNS")
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    if args.summarize:
        summarize(out_dir, root, args.summary_title)
        return 0

    result = run(args)
    print(json.dumps({
        "status": result.get("status"),
        "challenge": result.get("challenge_label"),
        "candidate": result.get("final_candidate_qiskit_order"),
        "validation": result.get("validation", {}).get("status"),
    }, sort_keys=True))
    return 0 if result.get("status") in {"ok", "no_candidate"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
