"""
Validated temporal center selection.

This is Stage 4: use proxy diagnostics only to propose candidate centers, then
promote centers using real partial MPO trial scores.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from circuit_tools import remove_measurements
from horizontal_unswapping import scan_temporal_centers
from layer_tools import greedy_layerize
from mpo_scoring import ProxyMPOScorer
from plan_types import MPOScore
from real_mpo_tools import TrialMPOResult, scan_real_temporal_centers, trial_result_to_dict


@dataclass
class ValidatedTemporalPlan:
    """Proxy-suggested centers reranked by real partial MPO trials."""
    candidate_centers: list[int]
    proxy_center_scores: list[dict[str, Any]]
    real_center_trials: list[TrialMPOResult]
    best_center: int | None
    best_score: MPOScore | None
    risk_flags: list[str]


def validate_temporal_centers(
    qc,
    params,
    *,
    top_k: int = 5,
    centers: list[int] | None = None,
    trial_absorb_layers: int | None = None,
    absorb_policy: str | None = None,
    run_unswap: bool | None = None,
    use_rewire: bool | None = None,
    to_backend=None,
) -> ValidatedTemporalPlan:
    """
    Select temporal centers by real partial MPO score.

    If centers is None, top-k candidates are proposed by proxy center scan.
    The final ranking always uses real partial MPO trial scores.
    """
    qc_clean = remove_measurements(qc)
    layers = greedy_layerize(qc_clean)
    proxy_rows = scan_temporal_centers(layers, ProxyMPOScorer(), params)

    if centers is None:
        candidate_centers = [row["center"] for row in proxy_rows[:top_k]]
        if not candidate_centers and len(layers) >= 2:
            candidate_centers = [len(layers) // 2]
    else:
        candidate_centers = list(dict.fromkeys(centers))

    real_trials = scan_real_temporal_centers(
        qc_clean,
        candidate_centers,
        params,
        trial_absorb_layers=trial_absorb_layers,
        absorb_policy=absorb_policy,
        run_unswap=run_unswap,
        use_rewire=use_rewire,
        to_backend=to_backend,
    )

    best = real_trials[0] if real_trials else None
    risk_flags = ["validated_by_real_mpo_trial"]
    if not real_trials:
        risk_flags.append("no_real_center_trials")
    if any(t.score.cost == float("inf") for t in real_trials):
        risk_flags.append("some_real_center_trials_failed")
    if run_unswap or params.run_trial_unswap:
        risk_flags.append("trial_unswap_enabled")
    else:
        risk_flags.append("trial_unswap_disabled")
    if use_rewire or params.use_trial_rewire:
        risk_flags.append("trial_rewire_requested")
    else:
        risk_flags.append("trial_rewire_disabled")

    return ValidatedTemporalPlan(
        candidate_centers=candidate_centers,
        proxy_center_scores=proxy_rows,
        real_center_trials=real_trials,
        best_center=best.center_layer if best else None,
        best_score=best.score if best else None,
        risk_flags=list(dict.fromkeys(risk_flags)),
    )


def validated_temporal_plan_to_dict(
    plan: ValidatedTemporalPlan,
    *,
    include_stats: bool = True,
    top_proxy_rows: int = 20,
) -> dict:
    """JSON-friendly representation of ValidatedTemporalPlan."""
    return {
        "candidate_centers": list(plan.candidate_centers),
        "proxy_center_scores": plan.proxy_center_scores[:top_proxy_rows],
        "best_center": plan.best_center,
        "best_score": None if plan.best_score is None else {
            "cost": plan.best_score.cost,
            "max_bond_dim": plan.best_score.max_bond_dim,
            "sum_log_bond_dim": plan.best_score.sum_log_bond_dim,
            "size": plan.best_score.size,
            "discarded_weight": plan.best_score.discarded_weight,
            "proxy_used": plan.best_score.proxy_used,
            "risk_flags": list(plan.best_score.risk_flags),
        },
        "real_center_trials": [
            trial_result_to_dict(t, include_stats=include_stats)
            for t in plan.real_center_trials
        ],
        "risk_flags": list(plan.risk_flags),
    }

