"""Choose non-overlapping multi-front temporal spawn segments."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .identity_windows import IdentityWindowCandidate, identity_candidate_to_dict


@dataclass
class MultiFrontSegment:
    """A selected local identity region used as a multi-front spawn site."""
    index: int
    window_i: int
    window_j: int
    layer_start: int
    layer_end: int
    center_layer: int
    identity_error: float
    n_gates: int
    source: str


@dataclass
class MultiFrontSegmentPlan:
    """A chronological set of selected non-overlapping spawn regions."""
    segments: list[MultiFrontSegment]
    rejected_candidates: list[dict[str, Any]]
    total_identity_error: float
    risk_flags: list[str]


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int, gap: int) -> bool:
    return not (a_end + gap < b_start or b_end + gap < a_start)


def segment_to_dict(segment: MultiFrontSegment) -> dict[str, Any]:
    """JSON-friendly MultiFrontSegment."""
    return {
        "index": segment.index,
        "window_i": segment.window_i,
        "window_j": segment.window_j,
        "layer_start": segment.layer_start,
        "layer_end": segment.layer_end,
        "center_layer": segment.center_layer,
        "identity_error": segment.identity_error,
        "n_gates": segment.n_gates,
        "source": segment.source,
    }


def segment_plan_to_dict(plan: MultiFrontSegmentPlan) -> dict[str, Any]:
    """JSON-friendly MultiFrontSegmentPlan."""
    return {
        "segments": [segment_to_dict(s) for s in plan.segments],
        "rejected_candidates": list(plan.rejected_candidates),
        "total_identity_error": plan.total_identity_error,
        "risk_flags": list(plan.risk_flags),
    }


def plan_multi_front_segments(
    candidates: list[IdentityWindowCandidate],
    *,
    max_segments: int = 4,
    min_separation_layers: int = 0,
    identity_error_threshold: float = 1e-3,
) -> MultiFrontSegmentPlan:
    """
    Greedily choose low-error, non-overlapping identity regions.

    The selected segments define where future MPO fronts should spawn. The plan
    is chronological, but the greedy choice is by identity error first.
    """
    selected: list[MultiFrontSegment] = []
    rejected: list[dict[str, Any]] = []

    for cand in sorted(candidates, key=lambda c: (c.identity_error, c.layer_start)):
        reason = None
        if cand.identity_error > identity_error_threshold:
            reason = "identity_error_above_threshold"
        elif len(selected) >= max_segments:
            reason = "max_segments_reached"
        else:
            for seg in selected:
                if _overlaps(
                    cand.layer_start,
                    cand.layer_end,
                    seg.layer_start,
                    seg.layer_end,
                    min_separation_layers,
                ):
                    reason = "overlaps_selected_segment"
                    break

        if reason is not None:
            row = identity_candidate_to_dict(cand)
            row["reject_reason"] = reason
            rejected.append(row)
            continue

        center = (cand.layer_start + cand.layer_end + 1) // 2
        selected.append(MultiFrontSegment(
            index=len(selected),
            window_i=cand.window_i,
            window_j=cand.window_j,
            layer_start=cand.layer_start,
            layer_end=cand.layer_end,
            center_layer=center,
            identity_error=cand.identity_error,
            n_gates=cand.n_gates,
            source="identity_window",
        ))

    selected.sort(key=lambda s: s.layer_start)
    for idx, seg in enumerate(selected):
        seg.index = idx

    risk_flags = ["greedy_non_overlapping_segment_plan"]
    if not selected:
        risk_flags.append("no_segments_selected")

    return MultiFrontSegmentPlan(
        segments=selected,
        rejected_candidates=rejected,
        total_identity_error=sum(s.identity_error for s in selected),
        risk_flags=risk_flags,
    )

