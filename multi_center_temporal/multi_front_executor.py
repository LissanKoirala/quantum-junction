"""Baby-case multi-front execution and bridge diagnostics."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

from .compat import ensure_spacetime_on_path
from .segment_planner import MultiFrontSegmentPlan, segment_plan_to_dict

ensure_spacetime_on_path()

from circuit_tools import remove_measurements
from layer_tools import greedy_layerize
from temporal_pipeline import (
    build_layer_range_circuit,
    exact_peak_bitstring,
    normalized_identity_error,
)


@dataclass
class BridgeDiagnostic:
    """Exact baby diagnostic for a temporal bridge between selected fronts."""
    bridge_index: int
    layer_start: int
    layer_end: int
    n_gates: int
    identity_error: float
    risk_flags: list[str]


@dataclass
class MultiFrontExecutionResult:
    """Result of chronological baby execution for a multi-front segment plan."""
    n_qubits: int
    n_layers: int
    n_gates: int
    segment_plan: MultiFrontSegmentPlan
    segment_identity_errors: list[dict[str, Any]]
    bridge_diagnostics: list[BridgeDiagnostic]
    exact_peak_bitstring: str | None
    exact_peak_probability: float | None
    risk_flags: list[str]
    wall_seconds: float


def bridge_to_dict(bridge: BridgeDiagnostic) -> dict[str, Any]:
    """JSON-friendly BridgeDiagnostic."""
    return {
        "bridge_index": bridge.bridge_index,
        "layer_start": bridge.layer_start,
        "layer_end": bridge.layer_end,
        "n_gates": bridge.n_gates,
        "identity_error": bridge.identity_error,
        "risk_flags": list(bridge.risk_flags),
    }


def multi_front_result_to_dict(result: MultiFrontExecutionResult) -> dict[str, Any]:
    """JSON-friendly MultiFrontExecutionResult."""
    return {
        "mode": "baby_exact_multi_front",
        "n_qubits": result.n_qubits,
        "n_layers": result.n_layers,
        "n_gates": result.n_gates,
        "segment_plan": segment_plan_to_dict(result.segment_plan),
        "segment_identity_errors": result.segment_identity_errors,
        "bridge_diagnostics": [bridge_to_dict(b) for b in result.bridge_diagnostics],
        "exact_peak_bitstring": result.exact_peak_bitstring,
        "exact_peak_probability": result.exact_peak_probability,
        "risk_flags": list(result.risk_flags),
        "wall_seconds": result.wall_seconds,
    }


def _score_layer_range(layers, n_qubits: int, start: int, end: int, max_exact_qubits: int):
    if start > end:
        return 0, 0.0, ["empty_bridge_identity"]
    circ = build_layer_range_circuit(layers, n_qubits, start, end)
    if n_qubits > max_exact_qubits:
        return circ.size(), math.inf, ["exact_bridge_qubit_limit_exceeded"]
    return circ.size(), normalized_identity_error(circ), ["exact_small_case_only"]


def execute_multi_front_exact(
    qc_raw,
    plan: MultiFrontSegmentPlan,
    *,
    max_exact_qubits: int = 10,
) -> MultiFrontExecutionResult:
    """
    Chronologically evaluate selected identity regions and bridges.

    This is not yet a scalable multi-MPO contraction. It provides the exact
    baby-case structure and diagnostics needed before replacing local exact
    scores with spawned MPO fronts.
    """
    t0 = time.perf_counter()
    qc = remove_measurements(qc_raw)
    layers = greedy_layerize(qc)
    risk_flags = ["baby_exact_multi_front_executor", "chronological_segment_order"]

    segment_rows: list[dict[str, Any]] = []
    for seg in plan.segments:
        n_gates, err, flags = _score_layer_range(
            layers,
            qc.num_qubits,
            seg.layer_start,
            seg.layer_end,
            max_exact_qubits,
        )
        segment_rows.append({
            "segment_index": seg.index,
            "layer_start": seg.layer_start,
            "layer_end": seg.layer_end,
            "n_gates": n_gates,
            "planned_identity_error": seg.identity_error,
            "exact_identity_error": err,
            "risk_flags": flags,
        })

    bridges: list[BridgeDiagnostic] = []
    cursor = 0
    for idx, seg in enumerate(plan.segments):
        start = cursor
        end = seg.layer_start - 1
        n_gates, err, flags = _score_layer_range(
            layers,
            qc.num_qubits,
            start,
            end,
            max_exact_qubits,
        )
        bridges.append(BridgeDiagnostic(idx, start, end, n_gates, err, flags))
        cursor = seg.layer_end + 1

    n_gates, err, flags = _score_layer_range(
        layers,
        qc.num_qubits,
        cursor,
        len(layers) - 1,
        max_exact_qubits,
    )
    bridges.append(BridgeDiagnostic(len(bridges), cursor, len(layers) - 1, n_gates, err, flags))

    peak_bits = None
    peak_prob = None
    if qc.num_qubits <= max_exact_qubits:
        peak_bits, peak_prob = exact_peak_bitstring(qc)
    else:
        risk_flags.append("exact_peak_qubit_limit_exceeded")

    return MultiFrontExecutionResult(
        n_qubits=qc.num_qubits,
        n_layers=len(layers),
        n_gates=qc.size(),
        segment_plan=plan,
        segment_identity_errors=segment_rows,
        bridge_diagnostics=bridges,
        exact_peak_bitstring=peak_bits,
        exact_peak_probability=peak_prob,
        risk_flags=risk_flags,
        wall_seconds=time.perf_counter() - t0,
    )

