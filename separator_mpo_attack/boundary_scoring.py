from __future__ import annotations

import math
from dataclasses import dataclass

from circuit_tools import gate_layers
from graph_tools import weighted_cut, cut_ratio, boundary_size


@dataclass
class BoundaryScore:
    cut: float
    cut_ratio: float
    boundary_size: int
    temporal_spread: int
    temporal_entropy: float
    mpo_proxy: float
    total: float


# ── Temporal diagnostics ────────────────────────────────────────────


def temporal_boundary_density(qc, A: set, B: set, num_windows: int = 20) -> list[int]:
    """
    Divide the circuit into num_windows time windows.
    Return density[w] = # boundary 2q gates in window w.
    """
    from circuit_tools import get_qubit_index_map, iter_two_qubit_gates
    q2i = get_qubit_index_map(qc)
    gates = list(iter_two_qubit_gates(qc))
    T = max((g["time"] for g in gates), default=0) + 1
    density = [0] * num_windows
    for g in gates:
        i, j = g["qubits"]
        if (i in A) != (j in A):  # boundary gate
            w = min(int(g["time"] * num_windows / T), num_windows - 1)
            density[w] += 1
    return density


def temporal_spread(density: list[int]) -> int:
    return sum(1 for d in density if d > 0)


def temporal_entropy(density: list[int]) -> float:
    total = sum(density)
    if total == 0:
        return 0.0
    H = 0.0
    for d in density:
        if d > 0:
            p = d / total
            H -= p * math.log(p)
    return H


# ── MPO boundary proxy ──────────────────────────────────────────────


def mpo_boundary_proxy(G, A: set, B: set, density: list[int] | None, cap: int = 20) -> float:
    """
    Proxy for MPO boundary complexity (no real tensor contraction).
    Uses log-space to avoid overflow.
    """
    bsz = boundary_size(G, A, B)
    sp = temporal_spread(density) if density else 0
    sq_density = sum(d * d for d in density) if density else 0

    # log( 2^min(bsz, cap) * (1 + sp) ) + sqrt(sq_density)
    log_proxy = min(bsz, cap) * math.log(2) + math.log(1.0 + sp)
    return log_proxy + math.sqrt(sq_density)


# ── Combined scorer ─────────────────────────────────────────────────


def score_boundary(qc, G, A: set, B: set, params, scorer_fn=None) -> BoundaryScore:
    """
    Compute BoundaryScore for partition (A, B).
    If params.scorer_fn or scorer_fn is provided, its return value replaces mpo_proxy.
    scorer_fn(qc, G, A, B, params) -> float
    """
    c = weighted_cut(G, A, B)
    cr = cut_ratio(G, A, B)
    bsz = boundary_size(G, A, B)
    density = temporal_boundary_density(qc, A, B, params.num_windows)
    sp = temporal_spread(density)
    he = temporal_entropy(density)

    fn = scorer_fn or getattr(params, "scorer_fn", None)
    if fn is not None:
        proxy = fn(qc, G, A, B, params)
    else:
        proxy = mpo_boundary_proxy(G, A, B, density, cap=params.mpo_proxy_cap)

    imbalance = abs(len(A) - len(B))
    total = (
        params.alpha_cut * c
        + params.beta_mpo_proxy * proxy
        + params.gamma_boundary_size * bsz
        + params.lambda_temporal_spread * sp
        + params.lambda_temporal_entropy * he
        + params.lambda_balance * imbalance
    )
    return BoundaryScore(
        cut=c,
        cut_ratio=cr,
        boundary_size=bsz,
        temporal_spread=sp,
        temporal_entropy=he,
        mpo_proxy=proxy,
        total=total,
    )
