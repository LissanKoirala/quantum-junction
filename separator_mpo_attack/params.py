from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class SeparatorParams:
    # Graph / weighting
    weight_mode: str = "gate_aware"   # "uniform" | "gate_aware" | "time_decay" | "time_reverse_decay"
    num_windows: int = 20

    # Partition balance
    lambda_balance: float = 1.0

    # Boundary-score weights
    alpha_cut: float = 1.0
    beta_mpo_proxy: float = 0.2
    gamma_boundary_size: float = 0.5
    lambda_temporal_spread: float = 0.5
    lambda_temporal_entropy: float = 0.5

    # Refinement
    max_refinement_iter: int = 50
    boundary_only_candidates: bool = True

    # Acceptance thresholds
    max_cut_ratio: float = 0.10
    max_boundary_size: int = 8
    max_temporal_spread: int = 5
    max_size_imbalance: int = 2

    # MPO proxy cap (log-space overflow guard)
    mpo_proxy_cap: int = 20

    # Optional plug-in scorer: scorer_fn(qc, G, A, B, params) -> float
    # If None, uses the built-in proxy formula.
    scorer_fn: Callable[..., float] | None = None

    # k-way partition: try k=2 first, escalate to 3,4,... if 2-way is rejected
    max_partitions: int = 4

    # Run the full pipeline regardless of acceptance thresholds.
    # Thresholds are still logged and stored but do not block execution.
    # Pass force_accept=False (or --strict on CLI) to restore rejection behaviour.
    force_accept: bool = True

    # MPO compression params (used in full pipeline)
    max_bond: int = 8192
    cutoff: float = 0.001
    unswap_threshold: float = 1e6
    early_stopping_gates: int = 100
    sabre_trials: int = 1000
    seed: int | None = None
