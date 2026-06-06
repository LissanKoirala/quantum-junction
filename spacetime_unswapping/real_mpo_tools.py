"""
Real partial MPO trial scoring for temporal center validation.

This module is the bridge from proxy diagnostics to real tensor-network
telemetry. It is intentionally small and layer-based:

- center is a layer index,
- no measurements are inserted,
- no rewiring by default,
- no unswapping by default, but the hook is present,
- absorption is greedy with a strict per-side trial budget by default.

It depends on peaked-circuit-simulation at runtime.
"""
from __future__ import annotations

import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from qiskit import QuantumCircuit

from circuit_tools import remove_measurements
from layer_tools import greedy_layerize
from plan_types import GateInfo, MPOScore


_REAL_FLAG = "real_mpo_trial"


@dataclass
class TrialMPOResult:
    """Real partial MPO trial result plus absorption telemetry."""
    score: MPOScore
    stats: list[dict[str, Any]]
    consumed_left: int
    consumed_right: int
    center_layer: int


def _ensure_peaked_sim_on_path() -> Path:
    here = Path(__file__).resolve().parent
    root = here.parent
    peaked = root / "peaked-circuit-simulation"
    if str(peaked) not in sys.path:
        sys.path.insert(0, str(peaked))
    return peaked


def gate_layer_to_circuit(layer: list[GateInfo], n_qubits: int) -> QuantumCircuit:
    """Build a Qiskit circuit containing one GateInfo layer."""
    circ = QuantumCircuit(n_qubits)
    for g in sorted(layer, key=lambda x: x.time):
        if g.operation is None:
            raise ValueError(f"GateInfo at time={g.time} has no operation object")
        circ.append(g.operation, list(g.qubits))
    return circ


def adjacent_bond_sizes(mpo) -> list[int]:
    """Return adjacent chain bond sizes for a MatrixProductOperator."""
    return [int(mpo.bond_size(i, i + 1)) for i in range(len(mpo.sites) - 1)]


def mpo_score_from_core(mpo, params, risk_flags: list[str] | None = None) -> MPOScore:
    """Convert a real MPO core into the shared MPOScore dataclass."""
    _ensure_peaked_sim_on_path()
    from utils import elem_counts, get_tn_info

    bonds = adjacent_bond_sizes(mpo)
    sum_log = float(sum(math.log(max(1, b)) for b in bonds))
    info = get_tn_info(mpo)
    size = int(elem_counts(mpo))
    cost = sum_log + params.mpo_cost_eta * math.log1p(size)

    flags = [_REAL_FLAG]
    if risk_flags:
        flags.extend(risk_flags)
    if params.max_bond is not None and info["max_bond"] >= params.max_bond:
        flags.append("max_bond_reached")

    return MPOScore(
        cost=float(cost),
        max_bond_dim=int(info["max_bond"]),
        sum_log_bond_dim=sum_log,
        size=size,
        discarded_weight=None,
        proxy_used=False,
        risk_flags=list(dict.fromkeys(flags)),
    )


def _stats_entry(
    *,
    stage: str,
    side: str | None,
    accepted: bool,
    left_index: int,
    right_index: int,
    consumed_left: int,
    consumed_right: int,
    score: MPOScore,
    elapsed_s: float,
    extra: dict | None = None,
) -> dict:
    row = {
        "time": elapsed_s,
        "stage": stage,
        "side": side,
        "accepted": accepted,
        "left_index": left_index,
        "right_index": right_index,
        "consumed_left": consumed_left,
        "consumed_right": consumed_right,
        "cost": score.cost,
        "max_bond_dim": score.max_bond_dim,
        "sum_log_bond_dim": score.sum_log_bond_dim,
        "size": score.size,
        "risk_flags": list(score.risk_flags),
    }
    if extra:
        row.update(extra)
    return row


def _apply_layer_candidate(
    mpo_core,
    layer: list[GateInfo],
    n_qubits: int,
    side: str,
    params,
    to_backend=None,
):
    """
    Apply one original circuit layer to the trial MPO.

    side="left" means post-center/right-side absorption, applied to MPO left.
    side="right" means pre-center/left-side absorption, applied to MPO right.
    """
    _ensure_peaked_sim_on_path()
    from quimb.tensor import Circuit
    from qiskit_quimb import quimb_circuit
    from circuit_mpo import apply_circuit

    q2c = lambda qc: quimb_circuit(qc.decompose("unitary"), Circuit, to_backend=to_backend)
    qc_layer = gate_layer_to_circuit(layer, n_qubits)
    return apply_circuit(
        mpo_core,
        q2c(qc_layer),
        side=side,
        max_bond=params.max_bond,
        cutoff=params.cutoff_window,
    )


def _run_optional_trial_unswap(
    mpo_core,
    params,
    to_backend,
    t0: float,
    *,
    reason: str,
    left_index: int,
    right_index: int,
    consumed_left: int,
    consumed_right: int,
):
    """Run a small unswap pass if enabled. Default params keep this off."""
    if not params.run_trial_unswap or params.max_trial_unswap_its <= 0:
        return mpo_core, [], ["unswap_not_run"], False

    _ensure_peaked_sim_on_path()
    from unswap import unswap

    before = mpo_score_from_core(mpo_core, params, risk_flags=["trial_unswap_before"])
    mpo_out, (_perm_l, _perm_r), stats = unswap(
        mpo_core,
        hows=params.trial_unswap_hows,
        max_bond=params.max_bond,
        cutoff=params.cutoff_window,
        max_its=params.max_trial_unswap_its,
        to_backend=to_backend,
        t0=t0,
    )
    after = mpo_score_from_core(mpo_out, params, risk_flags=["trial_unswap_after"])
    accepted = after.cost <= before.cost
    row = _stats_entry(
        stage="trial_unswap",
        side=None,
        accepted=accepted,
        left_index=left_index,
        right_index=right_index,
        consumed_left=consumed_left,
        consumed_right=consumed_right,
        score=after,
        elapsed_s=time.perf_counter() - t0,
        extra={
            "reason": reason,
            "cost_before": before.cost,
            "cost_after": after.cost,
            "size_before": before.size,
            "size_after": after.size,
            "max_bond_before": before.max_bond_dim,
            "max_bond_after": after.max_bond_dim,
            "improvement": before.cost - after.cost,
        },
    )
    if accepted:
        return mpo_out, [row] + stats, ["trial_unswap_run"], True
    return mpo_core, [row] + stats, ["trial_unswap_rejected"], False


def trial_middle_mpo_score(
    qc,
    center_layer: int,
    params,
    *,
    trial_absorb_layers: int | None = None,
    absorb_policy: str | None = None,
    run_unswap: bool | None = None,
    use_rewire: bool | None = None,
    to_backend=None,
) -> TrialMPOResult:
    """
    Real partial MPO center score.

    Splits the cleaned circuit at a layer index, initializes an identity MPO,
    greedily absorbs original left layers onto the MPO right and original right
    layers onto the MPO left, and returns real bond/size telemetry.

    This function does not add measurements and does not recover a bitstring.
    """
    _ensure_peaked_sim_on_path()
    from quimb.tensor import Circuit
    from qiskit_quimb import quimb_circuit
    from circuit_mpo import mpo_from_circuit

    t0 = time.perf_counter()
    qc_clean = remove_measurements(qc)
    n_qubits = qc_clean.num_qubits
    layers = greedy_layerize(qc_clean)

    if not layers:
        return TrialMPOResult(
            score=MPOScore(
                cost=float("inf"),
                max_bond_dim=None,
                sum_log_bond_dim=None,
                size=None,
                discarded_weight=None,
                proxy_used=False,
                risk_flags=[_REAL_FLAG, "empty_circuit"],
            ),
            stats=[],
            consumed_left=0,
            consumed_right=0,
            center_layer=center_layer,
        )

    if center_layer <= 0 or center_layer >= len(layers):
        return TrialMPOResult(
            score=MPOScore(
                cost=float("inf"),
                max_bond_dim=None,
                sum_log_bond_dim=None,
                size=None,
                discarded_weight=None,
                proxy_used=False,
                risk_flags=[_REAL_FLAG, "invalid_center_layer"],
            ),
            stats=[],
            consumed_left=0,
            consumed_right=0,
            center_layer=center_layer,
        )

    if use_rewire is None:
        use_rewire = params.use_trial_rewire
    if use_rewire:
        return TrialMPOResult(
            score=MPOScore(
                cost=float("inf"),
                max_bond_dim=None,
                sum_log_bond_dim=None,
                size=None,
                discarded_weight=None,
                proxy_used=False,
                risk_flags=[_REAL_FLAG, "trial_rewire_not_implemented"],
            ),
            stats=[],
            consumed_left=0,
            consumed_right=0,
            center_layer=center_layer,
        )

    old_run_unswap = params.run_trial_unswap
    if run_unswap is not None:
        params.run_trial_unswap = run_unswap

    try:
        K = trial_absorb_layers if trial_absorb_layers is not None else params.trial_absorb_layers
        K = max(1, int(K))
        policy = absorb_policy or params.trial_absorb_policy
        if policy not in {"greedy", "symmetric"}:
            raise ValueError(f"unknown absorb policy: {policy!r}")
        if params.trial_absorb_mode not in {"per_side", "total"}:
            raise ValueError(f"unknown trial_absorb_mode: {params.trial_absorb_mode!r}")

        left_idx = center_layer - 1
        right_idx = center_layer
        consumed_left = 0
        consumed_right = 0
        total_consumed = 0
        unswap_was_run = False
        stats: list[dict[str, Any]] = []

        q2c = lambda qc_: quimb_circuit(qc_.decompose("unitary"), Circuit, to_backend=to_backend)
        mpo_core = mpo_from_circuit(q2c(QuantumCircuit(n_qubits)))
        current_score = mpo_score_from_core(
            mpo_core,
            params,
            risk_flags=["measurements_removed", "rewire_not_run"],
        )
        stats.append(_stats_entry(
            stage="start",
            side=None,
            accepted=True,
            left_index=left_idx,
            right_index=right_idx,
            consumed_left=consumed_left,
            consumed_right=consumed_right,
            score=current_score,
            elapsed_s=time.perf_counter() - t0,
        ))

        def side_available(side: str) -> bool:
            if params.trial_absorb_mode == "total" and total_consumed >= K:
                return False
            if side == "left":
                return left_idx >= 0 and consumed_left < K
            return right_idx < len(layers) and consumed_right < K

        while side_available("left") or side_available("right"):
            candidates = []

            if side_available("left"):
                try:
                    mpo_l = _apply_layer_candidate(
                        mpo_core, layers[left_idx], n_qubits, "right", params, to_backend
                    )
                    score_l = mpo_score_from_core(mpo_l, params)
                    candidates.append(("left", mpo_l, score_l))
                    stats.append(_stats_entry(
                        stage="candidate",
                        side="left",
                        accepted=False,
                        left_index=left_idx,
                        right_index=right_idx,
                        consumed_left=consumed_left,
                        consumed_right=consumed_right,
                        score=score_l,
                        elapsed_s=time.perf_counter() - t0,
                    ))
                except Exception as exc:
                    if params.fail_fast_real_mpo:
                        raise
                    stats.append({
                        "time": time.perf_counter() - t0,
                        "stage": "candidate_failed",
                        "side": "left",
                        "left_index": left_idx,
                        "error": repr(exc),
                    })

            if side_available("right"):
                try:
                    mpo_r = _apply_layer_candidate(
                        mpo_core, layers[right_idx], n_qubits, "left", params, to_backend
                    )
                    score_r = mpo_score_from_core(mpo_r, params)
                    candidates.append(("right", mpo_r, score_r))
                    stats.append(_stats_entry(
                        stage="candidate",
                        side="right",
                        accepted=False,
                        left_index=left_idx,
                        right_index=right_idx,
                        consumed_left=consumed_left,
                        consumed_right=consumed_right,
                        score=score_r,
                        elapsed_s=time.perf_counter() - t0,
                    ))
                except Exception as exc:
                    if params.fail_fast_real_mpo:
                        raise
                    stats.append({
                        "time": time.perf_counter() - t0,
                        "stage": "candidate_failed",
                        "side": "right",
                        "right_index": right_idx,
                        "error": repr(exc),
                    })

            if not candidates:
                current_score.risk_flags.append("all_trial_candidates_failed")
                break

            if policy == "symmetric":
                preferred = "left" if consumed_left <= consumed_right else "right"
                preferred_candidates = [c for c in candidates if c[0] == preferred]
                chosen = preferred_candidates[0] if preferred_candidates else candidates[0]
            else:
                chosen = min(
                    candidates,
                    key=lambda c: (
                        c[2].cost,
                        c[2].max_bond_dim if c[2].max_bond_dim is not None else 10**18,
                        c[2].size if c[2].size is not None else 10**18,
                    ),
                )

            side, mpo_core, current_score = chosen
            if side == "left":
                left_idx -= 1
                consumed_left += 1
            else:
                right_idx += 1
                consumed_right += 1
            total_consumed += 1

            stats.append(_stats_entry(
                stage="absorbed",
                side=side,
                accepted=True,
                left_index=left_idx,
                right_index=right_idx,
                consumed_left=consumed_left,
                consumed_right=consumed_right,
                score=current_score,
                elapsed_s=time.perf_counter() - t0,
            ))

            if (
                params.trial_unswap_trigger == "threshold"
                and params.run_trial_unswap
                and current_score.size is not None
                and current_score.size >= params.trial_unswap_threshold_elems
            ):
                mpo_core, unswap_stats, unswap_flags, did_unswap = _run_optional_trial_unswap(
                    mpo_core,
                    params,
                    to_backend,
                    t0,
                    reason="threshold",
                    left_index=left_idx,
                    right_index=right_idx,
                    consumed_left=consumed_left,
                    consumed_right=consumed_right,
                )
                if unswap_stats:
                    stats.extend(unswap_stats)
                if did_unswap:
                    unswap_was_run = True
                    current_score = mpo_score_from_core(
                        mpo_core,
                        params,
                        risk_flags=["measurements_removed", "rewire_not_run", "trial_unswap_run"],
                    )

        final_unswap_flags = []
        if params.trial_unswap_trigger == "final":
            mpo_core, unswap_stats, final_unswap_flags, did_unswap = _run_optional_trial_unswap(
                mpo_core,
                params,
                to_backend,
                t0,
                reason="final",
                left_index=left_idx,
                right_index=right_idx,
                consumed_left=consumed_left,
                consumed_right=consumed_right,
            )
            if unswap_stats:
                stats.extend(unswap_stats)
            unswap_was_run = unswap_was_run or did_unswap

        if not final_unswap_flags:
            final_unswap_flags = ["trial_unswap_run"] if unswap_was_run else ["unswap_not_run"]

        final_flags = ["measurements_removed", "rewire_not_run"] + final_unswap_flags
        if consumed_left < K or consumed_right < K:
            final_flags.append("trial_absorption_incomplete")
        final_score = mpo_score_from_core(mpo_core, params, risk_flags=final_flags)

        return TrialMPOResult(
            score=final_score,
            stats=stats,
            consumed_left=consumed_left,
            consumed_right=consumed_right,
            center_layer=center_layer,
        )
    except Exception as exc:
        if params.fail_fast_real_mpo:
            raise
        return TrialMPOResult(
            score=MPOScore(
                cost=float("inf"),
                max_bond_dim=None,
                sum_log_bond_dim=None,
                size=None,
                discarded_weight=None,
                proxy_used=False,
                risk_flags=[_REAL_FLAG, "real_mpo_trial_failed", repr(exc)],
            ),
            stats=[],
            consumed_left=0,
            consumed_right=0,
            center_layer=center_layer,
        )
    finally:
        params.run_trial_unswap = old_run_unswap


def trial_result_to_dict(result: TrialMPOResult, include_stats: bool = True) -> dict:
    """JSON-friendly representation of a trial MPO result."""
    d = {
        "center_layer": result.center_layer,
        "consumed_left": result.consumed_left,
        "consumed_right": result.consumed_right,
        "score": {
            "cost": result.score.cost,
            "max_bond_dim": result.score.max_bond_dim,
            "sum_log_bond_dim": result.score.sum_log_bond_dim,
            "size": result.score.size,
            "discarded_weight": result.score.discarded_weight,
            "proxy_used": result.score.proxy_used,
            "risk_flags": list(result.score.risk_flags),
        },
    }
    if include_stats:
        d["stats"] = result.stats
    return d


def scan_real_temporal_centers(
    qc,
    centers: list[int],
    params,
    *,
    trial_absorb_layers: int | None = None,
    absorb_policy: str | None = None,
    run_unswap: bool | None = None,
    use_rewire: bool | None = None,
    to_backend=None,
) -> list[TrialMPOResult]:
    """Run trial_middle_mpo_score on several centers and rank by real cost."""
    results = [
        trial_middle_mpo_score(
            qc,
            center_layer=c,
            params=params,
            trial_absorb_layers=trial_absorb_layers,
            absorb_policy=absorb_policy,
            run_unswap=run_unswap,
            use_rewire=use_rewire,
            to_backend=to_backend,
        )
        for c in centers
    ]
    return sorted(results, key=lambda r: r.score.cost)
