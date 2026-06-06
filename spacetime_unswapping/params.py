"""
Parameter dataclass for the spacetime unswapping planner.

All weights and thresholds are independent of separator_mpo_attack/params.py.
In particular, swap_weight=4.0 here (not 0.2 as in the old package) because
a cross-partition SWAP exchanges logical quantum states between sides and can
invalidate a fixed qubit-membership decomposition.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class SpacetimeParams:
    # ── Windowing ────────────────────────────────────────────────
    window_sizes: tuple[int, ...] = (4, 8, 12, 16)
    target_twoq_per_window: int = 32
    center_stride: int = 1
    center_margin: int = 2
    trial_absorb_layers: int = 8

    # ── Candidate limits ─────────────────────────────────────────
    max_horizontal_candidates: int = 64
    max_vertical_candidates: int = 256
    max_horizontal_refinement_iter: int = 20
    max_vertical_refinement_iter: int = 50
    max_alternating_iter: int = 10

    # ── Scoring weights ──────────────────────────────────────────
    alpha_q_cut: float = 1.0
    beta_temporal_mpo: float = 1.0
    gamma_boundary_size: float = 0.5
    lambda_temporal_spread: float = 0.75
    lambda_temporal_entropy: float = 0.25
    lambda_balance: float = 1.0
    mu_inverse_match: float = 0.75
    mu_graph_similarity: float = 0.5
    eta_permutation_cost: float = 0.05
    proxy_risk_penalty: float = 1.0

    # ── Acceptance thresholds ────────────────────────────────────
    horizontal_acceptance_margin: float = 1e-6
    vertical_acceptance_margin: float = 1e-9
    alternating_acceptance_margin: float = 1e-6
    max_cut_ratio: float = 0.15
    max_boundary_fraction: float = 0.35
    max_temporal_spread_fraction: float = 0.4
    max_size_imbalance: int = 2

    # ── Gate weights (new, independent of separator_mpo_attack) ──
    # SWAP gets high weight because a cross-partition SWAP is physically
    # much more damaging than a CX in a fixed qubit-membership decomposition.
    cx_weight: float = 1.0
    cz_weight: float = 1.0
    ecr_weight: float = 1.0
    iswap_weight: float = 2.0
    swap_weight: float = 4.0
    cross_swap_boundary_penalty: float = 8.0
    single_qubit_weight: float = 0.0
    other_two_qubit_weight: float = 0.5

    # ── MPO compression (for future Stage 5 real scoring) ────────
    max_bond: int = 8192
    cutoff_window: float = 1e-5
    cutoff_final: float = 1e-3
    unswap_threshold: float = 1e6
    trial_absorb_mode: str = "per_side"      # "per_side" | "total"
    trial_absorb_policy: str = "greedy"      # "greedy" | "symmetric"
    run_trial_unswap: bool = False
    max_trial_unswap_its: int = 0
    trial_unswap_trigger: str = "threshold"  # "threshold" | "final" | "never"
    trial_unswap_threshold_elems: int = 1_000_000
    trial_unswap_hows: tuple[str, ...] = ("both", "left", "right")
    use_trial_rewire: bool = False
    mpo_cost_eta: float = 0.01
    fail_fast_real_mpo: bool = False

    # ── Number of windows for boundary density computation ───────
    num_windows: int = 20

    # ── Partition mode ───────────────────────────────────────────
    # "global": one partition for all windows (default, easier to validate)
    # "per_window": separate partition per window (experimental)
    partition_mode: str = "global"

    # ── Reproducibility ──────────────────────────────────────────
    seed: int | None = 0

    # ── Planner / scorer modes ───────────────────────────────────
    score_mode: str = "proxy"           # "proxy" | "real"
    planner_mode: str = "horizontal_first"  # "horizontal_first" | "vertical_first"
