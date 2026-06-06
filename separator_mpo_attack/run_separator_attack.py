#!/usr/bin/env python3
"""
Separator-guided MPO attack on peaked quantum circuits.

Usage:
    # Real challenge circuits
    python run_separator_attack.py --challenge-id 2
    python run_separator_attack.py --qasm ../challenges/easy/challenge-8_1.qasm

    # Synthetic test circuits
    python run_separator_attack.py --test weakly_coupled
    python run_separator_attack.py --test dense_random
    python run_separator_attack.py --test hidden_swapped
    python run_separator_attack.py --test temporal_boundary
    python run_separator_attack.py --test independent_blocks
    python run_separator_attack.py --test mirror_like

    # Summarise all saved results
    python run_separator_attack.py --summarize

Full pipeline (when separator accepted):
    1. Strict split: C_A (pure-A gates), C_B (pure-B gates), C_∂ (boundary gates)
    2. mpo_compress_unswap on C_A and C_B independently
    3. mpo_to_mps on each → MPS_A, MPS_B
    4. Combine: MPS_A ⊗ MPS_B (A-first chain, trivial dim-1 bond at interface)
    5. Apply C_∂ to combined MPS layer by layer
    6. Extract bitstring; reorder from combined-site order to original qubit order
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import logging
import re
import resource
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

# ── Path setup ────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PEAKED_SIM = ROOT / "peaked-circuit-simulation"

for _p in [str(HERE), str(PEAKED_SIM)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from params import SeparatorParams
from circuit_tools import remove_measurements
from graph_tools import build_weighted_interaction_graph
from partition_tools import (
    initial_balanced_partition,
    make_ordering_from_partition,
    recursive_bisection,
    k_way_cut_ratio,
    k_way_boundary_size,
)
from boundary_scoring import score_boundary
from boundary_refinement import refine_partition_by_boundary_swaps
from split_tools import (
    split_circuit_by_partition,
    split_circuit_by_k_partition,
    build_remapped_subcircuit,
    build_remapped_boundary_circuit,
)
from diagnostics import summarize_partition, print_summary, write_summary_json
from mps_combine import (
    combine_mps_k_product,
    combined_site_map_k,
    apply_boundary_to_combined_mps,
    reorder_bitstring,
)
from test_circuits import (
    make_two_independent_blocks,
    make_weakly_coupled_blocks,
    make_dense_random_circuit,
    make_hidden_swapped_blocks,
    make_temporally_spread_boundary,
    make_small_mirror_like_circuit,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────
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

TEST_CIRCUITS = {
    "independent_blocks": lambda: make_two_independent_blocks(4, 4, 4),
    "weakly_coupled": lambda: make_weakly_coupled_blocks(4, 4, 4, 2),
    "dense_random": lambda: make_dense_random_circuit(8, 10, 4),
    "hidden_swapped": lambda: make_hidden_swapped_blocks(4, 4, 4),
    "temporal_boundary": lambda: make_temporally_spread_boundary(4, 4, 20),
    "mirror_like": lambda: make_small_mirror_like_circuit(6, 3),
}


# ── Helpers ───────────────────────────────────────────────────────────

def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _json_safe(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): _json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_json_safe(v) for v in x]
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    return repr(x)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(data), indent=2, sort_keys=True) + "\n")


def challenge_paths(root: Path) -> list[Path]:
    return sorted((root / "challenges").glob("*/*.qasm"), key=lambda p: (p.parent.name, p.name))


def resolve_challenge(root: Path, challenge_id: int | None, qasm: Path | None) -> Path:
    if qasm is not None:
        return (qasm if qasm.is_absolute() else root / qasm).resolve()
    if challenge_id is None:
        raise ValueError("provide --challenge-id or --qasm")
    hits = [p for p in challenge_paths(root)
            if (m := CHALLENGE_RE.match(p.name)) and int(m.group(2)) == challenge_id]
    if len(hits) != 1:
        raise ValueError(f"expected one challenge for id {challenge_id}, found {hits}")
    return hits[0].resolve()


def versions() -> dict[str, str]:
    out = {}
    for pkg in ["qiskit", "qiskit-quimb", "quimb", "networkx", "numpy", "scipy"]:
        try:
            out[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            out[pkg] = "not-installed"
    return out


# ── Phase 1: separator analysis ───────────────────────────────────────

def run_separator_analysis(qc_clean, params: SeparatorParams) -> tuple[dict, set, set, object]:
    """
    Build graph, find partition, refine, summarize.
    Returns (summary, A, B, G).
    """
    G = build_weighted_interaction_graph(qc_clean, weight_mode=params.weight_mode)

    log.info("[separator] Finding initial balanced partition...")
    A, B = initial_balanced_partition(G, method="kernighan_lin")
    log.info(f"[separator] Initial: |A|={len(A)} |B|={len(B)}")

    init_score = score_boundary(qc_clean, G, A, B, params)
    log.info(f"[separator] Initial score: cut={init_score.cut:.3f} "
             f"cut_ratio={init_score.cut_ratio:.4f} boundary_size={init_score.boundary_size} "
             f"temporal_spread={init_score.temporal_spread}")

    log.info("[separator] Refining partition...")
    A, B, history = refine_partition_by_boundary_swaps(qc_clean, G, A, B, params)
    refined_score = score_boundary(qc_clean, G, A, B, params)
    log.info(f"[separator] Refined score: cut={refined_score.cut:.3f} "
             f"cut_ratio={refined_score.cut_ratio:.4f} "
             f"boundary_size={refined_score.boundary_size} "
             f"(moves accepted: {len(history)})")

    summary = summarize_partition(qc_clean, G, A, B, params)
    return summary, A, B, G


# ── Phase 1b: k-way partition search ─────────────────────────────────

def run_k_partition_search(
    qc_clean, G, params: SeparatorParams
) -> tuple[int, list[set], float, int]:
    """
    Try k = 3, 4, ..., max_partitions and return the best (lowest cut_ratio) partition.
    Returns (k, partitions, cut_ratio, boundary_size).
    Doesn't re-run refinement — uses raw recursive bisection.
    """
    best_k = 2
    best_parts, best_ratio, best_bsz = None, float("inf"), 0

    for k in range(3, params.max_partitions + 1):
        parts = recursive_bisection(G, k)
        ratio = k_way_cut_ratio(G, parts)
        bsz = k_way_boundary_size(G, parts)
        log.info(
            f"[k={k}] cut_ratio={ratio:.4f}  boundary_size={bsz}  "
            f"partition_sizes={[len(p) for p in parts]}"
        )
        if ratio < best_ratio:
            best_ratio, best_bsz, best_k, best_parts = ratio, bsz, k, parts

    return best_k, best_parts, best_ratio, best_bsz


def k_partition_accepted(cut_ratio: float, boundary_size: int, params: SeparatorParams) -> tuple[bool, list[str]]:
    flags = []
    if cut_ratio > params.max_cut_ratio:
        flags.append(f"cut_ratio={cut_ratio:.3f} > {params.max_cut_ratio}")
    if boundary_size > params.max_boundary_size:
        flags.append(f"boundary_size={boundary_size} > {params.max_boundary_size}")
    return len(flags) == 0, flags


# ── Phase 2: MPO sub-circuit contraction ─────────────────────────────

def run_k_sub_mpos(
    subcircuits: list,
    params: SeparatorParams,
    to_backend,
) -> tuple[list, list, list]:
    """
    Run mpo_compress_unswap + mpo_to_mps on each of the k sub-circuits.
    Returns (mps_list, perm_list, stats_list).
    """
    from qiskit_quimb import quimb_circuit
    from quimb.tensor import Circuit
    from unswap import mpo_compress_unswap, mpo_to_mps

    mps_list, perm_list, all_stats = [], [], []
    for i, circ in enumerate(subcircuits):
        log.info(f"[sub-MPO {i}] {circ.num_qubits} qubits, {circ.size()} gates")
        mpo_i, ll_i, lr_i, stats_i = mpo_compress_unswap(
            circ,
            max_bond=params.max_bond,
            cutoff=params.cutoff,
            unswap_threshold=params.unswap_threshold,
            early_stopping_gates=params.early_stopping_gates,
            sabre_trials=params.sabre_trials,
            seed=params.seed,
        )
        mps_i, perm_i = mpo_to_mps(
            mpo_i, ll_i[:-2], lr_i,
            max_bond=params.max_bond,
            cutoff=params.cutoff,
            to_backend=to_backend,
        )
        log.info(f"[sub-MPO {i}] done. max_bond={mps_i.max_bond()}")
        mps_list.append(mps_i)
        perm_list.append(perm_i)
        all_stats.extend(stats_i)

    return mps_list, perm_list, all_stats


# ── Phase 3: combine + boundary + bitstring ───────────────────────────

def run_k_combine_and_extract(
    mps_list: list,
    perm_list: list,
    partitions_sorted: list[list[int]],
    boundary_gates: list[dict],
    params: SeparatorParams,
    to_backend,
) -> tuple[str, dict[int, int]]:
    """
    Combine k MPS states into a product state, apply boundary circuit, extract bitstring.
    Returns (raw_bits, qubit_to_combined_site).
    """
    from utils import extract_bitstring

    qubit_to_site = combined_site_map_k(partitions_sorted, perm_list)
    log.info(f"[combine-k] qubit_to_combined_site={qubit_to_site}")

    log.info(f"[combine-k] Merging {len(mps_list)} sub-MPS states...")
    combined = combine_mps_k_product(mps_list)
    n_combined = sum(len(p) for p in partitions_sorted)
    log.info(f"[combine-k] Combined MPS: {len(combined.sites)} sites, max_bond={combined.max_bond()}")

    if boundary_gates:
        log.info(f"[combine-k] Applying {len(boundary_gates)} boundary gates...")
        boundary_circ = build_remapped_boundary_circuit(boundary_gates, qubit_to_site, n_combined)
        combined = apply_boundary_to_combined_mps(
            combined, boundary_circ, params.max_bond, params.cutoff, to_backend
        )
        log.info(f"[combine-k] After boundary: max_bond={combined.max_bond()}")
    else:
        log.info("[combine-k] No boundary gates.")

    raw_bits, _ = extract_bitstring(combined)
    return raw_bits, qubit_to_site


# ── Validation ────────────────────────────────────────────────────────

def validate(label: str, bitstring: str) -> dict[str, Any]:
    known = KNOWN.get(label)
    if known is None:
        return {"status": "unknown", "known_answer": None, "match": None}
    match = bitstring == known
    return {"status": "correct" if match else "incorrect", "known_answer": known, "match": match}


# ── Summarise mode ────────────────────────────────────────────────────

def summarize_all(output_dir: Path) -> None:
    results = list(output_dir.glob("*.json"))
    if not results:
        print("No results found in", output_dir)
        return
    rows = []
    for p in sorted(results):
        try:
            d = json.loads(p.read_text())
            rows.append({
                "label": d.get("challenge_label", p.stem),
                "accepted": d.get("separator_accepted"),
                "cut_ratio": d.get("separator_summary", {}).get("cut_ratio"),
                "boundary_size": d.get("separator_summary", {}).get("boundary_size"),
                "status": d.get("validation", {}).get("status"),
                "wall_s": d.get("wall_seconds"),
            })
        except Exception:
            pass
    header = f"{'label':<16} {'accepted':<10} {'cut_ratio':<12} {'bsz':<6} {'status':<12} {'wall_s':<10}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{str(r['label']):<16} {str(r['accepted']):<10} "
              f"{str(round(r['cut_ratio'], 4) if r['cut_ratio'] else '-'):<12} "
              f"{str(r['boundary_size'] or '-'):<6} "
              f"{str(r['status'] or '-'):<12} "
              f"{str(round(r['wall_s'], 1) if r['wall_s'] else '-'):<10}")


# ── Main ──────────────────────────────────────────────────────────────

def run_one(qc_raw, label: str, params: SeparatorParams, output_dir: Path, backend: str) -> dict:
    t0 = time.perf_counter()

    # Backend setup
    to_backend = None
    if backend in ("cuda", "auto"):
        try:
            import torch
            if torch.cuda.is_available():
                from utils import to_backend_cuda
                to_backend = to_backend_cuda
        except ImportError:
            pass

    # Strip measurements
    qc_clean = remove_measurements(qc_raw)

    # ── Phase 1: separator analysis ──
    log.info(f"[{label}] Phase 1: separator analysis ({qc_clean.num_qubits} qubits, {qc_clean.size()} gates)")
    summary, A, B, G = run_separator_analysis(qc_clean, params)
    print_summary(summary)

    result: dict[str, Any] = {
        "challenge_label": label,
        "method": "separator_mpo_attack",
        "separator_summary": summary,
        "separator_accepted": summary["accepted"],
        "versions": versions(),
        "backend": backend,
    }

    accepted_2way = summary["accepted"]

    # ── Escalate to k-way if 2-way rejected and max_partitions > 2 ──
    use_k = 2
    partitions: list[set] = [A, B]

    if not accepted_2way and params.max_partitions > 2:
        log.info(f"[{label}] 2-way rejected. Searching for better k-way partition (max_k={params.max_partitions})...")
        best_k, best_parts, best_ratio, best_bsz = run_k_partition_search(qc_clean, G, params)
        k_accepted, k_flags = k_partition_accepted(best_ratio, best_bsz, params)
        log.info(
            f"[{label}] Best k={best_k}: cut_ratio={best_ratio:.4f} boundary_size={best_bsz} "
            f"{'ACCEPTED' if k_accepted else 'REJECTED'}"
        )
        if k_accepted or params.force_accept:
            use_k = best_k
            partitions = best_parts
            k_cut_ratio = best_ratio
            k_boundary_size = best_bsz
            result["k_partition"] = {
                "k": best_k, "cut_ratio": best_ratio,
                "boundary_size": best_bsz,
                "partition_sizes": [len(p) for p in best_parts],
                "accepted": k_accepted,
                "forced": params.force_accept and not k_accepted,
                "flags": k_flags,
            }
        else:
            log.info(f"[{label}] k-way also rejected: {k_flags}")
            result["k_partition"] = {
                "k": best_k, "cut_ratio": best_ratio,
                "boundary_size": best_bsz, "accepted": False, "flags": k_flags,
            }

    if not accepted_2way and use_k == 2 and not params.force_accept:
        log.info(f"[{label}] Separator REJECTED (2-way and k-way). Exiting without MPO contraction.")
        log.info(f"  Risk flags: {summary['risk_flags']}")
        result["wall_seconds"] = time.perf_counter() - t0
        result["max_rss_mb"] = rss_mb()
        return result

    if params.force_accept and not accepted_2way and use_k == 2:
        log.info(f"[{label}] Thresholds exceeded but proceeding anyway (use --strict to reject). 2-way partition.")

    log.info(f"[{label}] Proceeding with k={use_k} partition.")
    result["separator_k"] = use_k

    # ── Phase 2: split circuit ──
    log.info(f"[{label}] Phase 2: splitting circuit by k={use_k} partition...")
    partitions_sorted = [sorted(p) for p in partitions]

    if use_k == 2:
        A_sorted, B_sorted = partitions_sorted
        buckets = split_circuit_by_partition(qc_clean, partitions[0], partitions[1])
        sub_gate_lists = [
            buckets["A_gates"] + buckets["single_A_gates"],
            buckets["B_gates"] + buckets["single_B_gates"],
        ]
        boundary_gates = buckets["boundary_gates"]
    else:
        kbuckets = split_circuit_by_k_partition(qc_clean, partitions)
        sub_gate_lists = kbuckets["partition_gates"]
        boundary_gates = kbuckets["boundary_gates"]

    subcircuits = []
    for i, (gate_list, part_sorted) in enumerate(zip(sub_gate_lists, partitions_sorted)):
        circ = build_remapped_subcircuit(gate_list, part_sorted)
        if "measure" not in circ.count_ops():
            circ.measure_all()
        subcircuits.append(circ)
        log.info(f"[{label}] C_{i}: {circ.size()} gates on {circ.num_qubits} qubits")

    log.info(f"[{label}] C_∂: {len(boundary_gates)} boundary gates")
    result["split"] = {
        "k": use_k,
        "partition_sizes": [len(p) for p in partitions_sorted],
        "n_subcircuit_gates": [c.size() for c in subcircuits],
        "n_boundary_gates": len(boundary_gates),
    }

    # ── Phase 3: sub-MPO contraction ──
    log.info(f"[{label}] Phase 3: sub-MPO contraction ({use_k} partitions)...")
    try:
        mps_list, perm_list, mpo_stats = run_k_sub_mpos(subcircuits, params, to_backend)
    except Exception as e:
        log.error(f"[{label}] Sub-MPO failed: {e}")
        result["error"] = repr(e)
        result["wall_seconds"] = time.perf_counter() - t0
        result["max_rss_mb"] = rss_mb()
        return result

    result["mps_max_bonds"] = [int(m.max_bond()) for m in mps_list]

    # ── Phase 4: combine + boundary + bitstring ──
    log.info(f"[{label}] Phase 4: combining and extracting bitstring...")
    try:
        raw_bits, qubit_to_site = run_k_combine_and_extract(
            mps_list, perm_list, partitions_sorted, boundary_gates, params, to_backend,
        )
        bitstring = reorder_bitstring(raw_bits, qubit_to_site)
        log.info(f"[{label}] raw (combined order): {raw_bits}")
        log.info(f"[{label}] bitstring (original qubit order): {bitstring}")
    except Exception as e:
        log.error(f"[{label}] Combine/extract failed: {e}")
        result["error"] = repr(e)
        result["wall_seconds"] = time.perf_counter() - t0
        result["max_rss_mb"] = rss_mb()
        return result

    result["bitstring_raw_combined_order"] = raw_bits
    result["bitstring_original_order"] = bitstring
    result["qubit_to_combined_site"] = {str(k): v for k, v in qubit_to_site.items()}
    result["validation"] = validate(label, bitstring)
    result["wall_seconds"] = time.perf_counter() - t0
    result["max_rss_mb"] = rss_mb()

    log.info(f"[{label}] Validation: {result['validation']}")
    log.info(f"[{label}] Finished in {result['wall_seconds']:.1f}s")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Separator-guided MPO attack")
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--challenge-id", type=int, help="Challenge ID (integer)")
    src.add_argument("--qasm", type=Path, help="Path to QASM file")
    src.add_argument("--test", choices=list(TEST_CIRCUITS), help="Synthetic test circuit name")
    src.add_argument("--summarize", action="store_true", help="Print summary of all saved results")

    parser.add_argument("--weight-mode", default="gate_aware",
                        choices=["uniform", "gate_aware", "time_decay", "time_reverse_decay"])
    parser.add_argument("--num-windows", type=int, default=20)
    parser.add_argument("--max-cut-ratio", type=float, default=0.10)
    parser.add_argument("--max-boundary-size", type=int, default=8)
    parser.add_argument("--max-temporal-spread", type=int, default=5)
    parser.add_argument("--max-size-imbalance", type=int, default=2)
    parser.add_argument("--max-partitions", type=int, default=4,
                        help="Maximum k for k-way partition (try k=2..max)")
    parser.add_argument("--strict", action="store_true",
                        help="Reject circuits that exceed acceptance thresholds (default: always run)")
    parser.add_argument("--max-bond", type=int, default=8192)
    parser.add_argument("--cutoff", type=float, default=0.001)
    parser.add_argument("--unswap-threshold", type=float, default=1e6)
    parser.add_argument("--sabre-trials", type=int, default=1000)
    parser.add_argument("--backend", default="auto", choices=["auto", "numpy", "cuda"])
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "separator_attack")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    output_dir = args.output_dir

    if args.summarize:
        summarize_all(output_dir)
        return

    params = SeparatorParams(
        weight_mode=args.weight_mode,
        num_windows=args.num_windows,
        max_cut_ratio=args.max_cut_ratio,
        max_boundary_size=args.max_boundary_size,
        max_temporal_spread=args.max_temporal_spread,
        max_size_imbalance=args.max_size_imbalance,
        max_partitions=args.max_partitions,
        force_accept=not args.strict,
        max_bond=args.max_bond,
        cutoff=args.cutoff,
        unswap_threshold=args.unswap_threshold,
        sabre_trials=args.sabre_trials,
        seed=args.seed,
    )

    if args.test:
        label = args.test
        log.info(f"Generating synthetic test circuit: {label}")
        qc_raw = TEST_CIRCUITS[label]()
        label = f"test_{label}"
    else:
        qasm_path = resolve_challenge(ROOT, args.challenge_id, args.qasm)
        from qiskit import qasm2
        qc_raw = qasm2.load(
            str(qasm_path),
            custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS,
        )
        m = CHALLENGE_RE.match(qasm_path.name)
        label = f"{m.group(1)}_{m.group(2)}" if m else qasm_path.stem

    result = run_one(qc_raw, label, params, output_dir, args.backend)

    out_path = output_dir / f"challenge-{label}.json"
    _write_json(out_path, result)
    log.info(f"Results saved to {out_path}")

    # Print concise terminal summary
    print("\n" + "=" * 60)
    print(f"Circuit : {label}")
    k = result.get("separator_k", 2)
    print(f"Accepted: {result.get('separator_accepted')}  k={k}")
    if "bitstring_original_order" in result:
        print(f"Bitstring (original qubit order): {result.get('bitstring_original_order')}")
        v = result.get("validation", {})
        print(f"Validation: {v.get('status')} (known={v.get('known_answer')})")
    else:
        flags = result.get("separator_summary", {}).get("risk_flags", [])
        kp = result.get("k_partition", {})
        if kp:
            print(f"Best k={kp.get('k')}: cut_ratio={kp.get('cut_ratio','?'):.3f} boundary_size={kp.get('boundary_size','?')}")
            print(f"k-way flags: {'; '.join(kp.get('flags', []))}")
        print(f"2-way flags: {'; '.join(flags)}")
    print(f"Wall time: {result.get('wall_seconds', 0):.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
