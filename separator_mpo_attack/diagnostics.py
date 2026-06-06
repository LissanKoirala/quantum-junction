from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from graph_tools import total_edge_weight, weighted_cut, cut_ratio, boundary_size
from boundary_scoring import (
    score_boundary,
    temporal_boundary_density,
    temporal_spread,
    temporal_entropy,
)
from partition_tools import is_balanced


def summarize_partition(qc, G, A: set, B: set, params, scorer_fn=None) -> dict[str, Any]:
    """
    Compute and return a full diagnostic dict for partition (A, B).
    """
    c = weighted_cut(G, A, B)
    cr = cut_ratio(G, A, B)
    bsz = boundary_size(G, A, B)
    density = temporal_boundary_density(qc, A, B, params.num_windows)
    sp = temporal_spread(density)
    he = temporal_entropy(density)
    score = score_boundary(qc, G, A, B, params, scorer_fn=scorer_fn)

    A_sorted = sorted(A)
    B_sorted = sorted(B)

    accepted, risk_flags = separator_acceptance_decision(
        {
            "cut_ratio": cr,
            "boundary_size": bsz,
            "temporal_spread": sp,
            "size_A": len(A),
            "size_B": len(B),
        },
        params,
    )

    return {
        "n_qubits": qc.num_qubits,
        "n_edges": G.number_of_edges(),
        "total_weight": total_edge_weight(G),
        "size_A": len(A),
        "size_B": len(B),
        "A_qubits": A_sorted,
        "B_qubits": B_sorted,
        "cut": c,
        "cut_ratio": cr,
        "boundary_size": bsz,
        "temporal_spread": sp,
        "temporal_entropy": he,
        "temporal_density": density,
        "mpo_proxy": score.mpo_proxy,
        "total_score": score.total,
        "accepted": accepted,
        "risk_flags": risk_flags,
        "balanced": is_balanced(A, B),
    }


def separator_acceptance_decision(
    summary: dict[str, Any], params
) -> tuple[bool, list[str]]:
    """
    Return (accepted, risk_flags) based on thresholds in params.
    """
    flags = []

    if summary["cut_ratio"] > params.max_cut_ratio:
        flags.append(f"cut_ratio={summary['cut_ratio']:.3f} > {params.max_cut_ratio}")

    if summary["boundary_size"] > params.max_boundary_size:
        flags.append(f"boundary_size={summary['boundary_size']} > {params.max_boundary_size}")

    if summary["temporal_spread"] > params.max_temporal_spread:
        flags.append(f"temporal_spread={summary['temporal_spread']} > {params.max_temporal_spread}")

    imbalance = abs(summary["size_A"] - summary["size_B"])
    if imbalance > params.max_size_imbalance:
        flags.append(f"size_imbalance={imbalance} > {params.max_size_imbalance}")

    accepted = len(flags) == 0
    return accepted, flags


def print_summary(summary: dict[str, Any]) -> None:
    print(f"\nn_qubits={summary['n_qubits']}  n_edges={summary['n_edges']}  "
          f"total_weight={summary['total_weight']:.2f}")
    print(f"|A|={summary['size_A']}  |B|={summary['size_B']}  "
          f"balanced={'yes' if summary['balanced'] else 'no'}")
    print(f"cut={summary['cut']:.3f}  cut_ratio={summary['cut_ratio']:.4f}")
    print(f"boundary_size={summary['boundary_size']}  "
          f"temporal_spread={summary['temporal_spread']}  "
          f"temporal_entropy={summary['temporal_entropy']:.3f}")
    print(f"mpo_proxy={summary['mpo_proxy']:.3f}  total_score={summary['total_score']:.3f}")
    status = "ACCEPT" if summary["accepted"] else "REJECT"
    print(f"\n→ {status} separator")
    if summary["risk_flags"]:
        for f in summary["risk_flags"]:
            print(f"  ✗ {f}")


def write_summary_json(summary: dict[str, Any], path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    def _safe(x):
        if isinstance(x, (set, frozenset)):
            return sorted(x)
        if isinstance(x, dict):
            return {str(k): _safe(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [_safe(v) for v in x]
        return x

    path.write_text(json.dumps(_safe(summary), indent=2, sort_keys=True) + "\n")
