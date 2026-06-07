"""Local temporal identity-window detection."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .compat import ensure_spacetime_on_path

ensure_spacetime_on_path()

from circuit_tools import remove_measurements
from layer_tools import greedy_layerize
from temporal_pipeline import exact_score_to_dict, score_window_product_exact
from window_tools import make_fixed_layer_windows


@dataclass
class IdentityWindowCandidate:
    """A local window product that looks close to identity in baby exact scoring."""
    window_i: int
    window_j: int
    layer_start: int
    layer_end: int
    n_gates: int
    identity_error: float
    peak_bitstring: str | None
    peak_probability: float | None
    risk_flags: list[str]


def identity_candidate_to_dict(candidate: IdentityWindowCandidate) -> dict[str, Any]:
    """JSON-friendly IdentityWindowCandidate."""
    return {
        "window_i": candidate.window_i,
        "window_j": candidate.window_j,
        "layer_start": candidate.layer_start,
        "layer_end": candidate.layer_end,
        "n_gates": candidate.n_gates,
        "identity_error": candidate.identity_error,
        "peak_bitstring": candidate.peak_bitstring,
        "peak_probability": candidate.peak_probability,
        "risk_flags": list(candidate.risk_flags),
    }


def detect_identity_windows(
    qc_raw,
    params,
    *,
    window_size: int | None = None,
    max_exact_qubits: int = 10,
    adjacent_only: bool = True,
    max_pair_distance: int | None = None,
    identity_error_threshold: float | None = None,
) -> list[IdentityWindowCandidate]:
    """
    Scan temporal windows for products that contract close to identity.

    This is an exact baby-case detector. It is meant to find candidate spawn
    regions before scalable MPO machinery is attached to the same plan.
    """
    qc = remove_measurements(qc_raw)
    layers = greedy_layerize(qc)
    ws = window_size or params.window_sizes[0]
    windows = make_fixed_layer_windows(layers, ws)
    if len(windows) < 2:
        return []

    out: list[IdentityWindowCandidate] = []
    max_dist = 1 if adjacent_only else max_pair_distance or len(windows)
    for i, w_i in enumerate(windows):
        upper = min(len(windows), i + max_dist + 1)
        for j in range(i + 1, upper):
            score = score_window_product_exact(
                w_i,
                windows[j],
                qc.num_qubits,
                max_exact_qubits=max_exact_qubits,
            )
            if identity_error_threshold is not None and score.identity_error > identity_error_threshold:
                continue
            row = exact_score_to_dict(score)
            layer_range = row["layer_range"] or [w_i.layer_start, windows[j].layer_end]
            out.append(IdentityWindowCandidate(
                window_i=i,
                window_j=j,
                layer_start=int(layer_range[0]),
                layer_end=int(layer_range[1]),
                n_gates=int(row["n_gates"]),
                identity_error=float(row["identity_error"]),
                peak_bitstring=row["peak_bitstring"],
                peak_probability=row["peak_probability"],
                risk_flags=list(row["risk_flags"]) + ["exact_identity_window_detector"],
            ))

    return sorted(out, key=lambda c: (c.identity_error, c.layer_start, c.layer_end))

