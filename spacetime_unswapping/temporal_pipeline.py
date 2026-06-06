"""
Small exact temporal pipeline utilities.

This module is intentionally for baby cases only. It uses exact Qiskit
Operator/Statevector checks to validate temporal center and window logic before
we wire the planner into scalable MPO contraction.

Nothing here is a production peak-recovery pipeline.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator, Statevector

from plan_types import GateInfo, TemporalWindow
from window_tools import window_from_layer_range


@dataclass
class ExactTemporalScore:
    """Exact small-circuit score for a temporal segment or window product."""
    kind: str
    center: int | None
    window_pair: tuple[int, int] | None
    layer_range: tuple[int, int] | None
    n_qubits: int
    n_gates: int
    identity_error: float
    peak_bitstring: str | None
    peak_probability: float | None
    risk_flags: list[str]


def build_circuit_from_gates(
    gates: list[GateInfo],
    n_qubits: int,
    *,
    sort_by_time: bool = True,
) -> QuantumCircuit:
    """Build a circuit from GateInfo objects, preserving original gate order."""
    circ = QuantumCircuit(n_qubits)
    ordered = sorted(gates, key=lambda g: g.time) if sort_by_time else gates
    for g in ordered:
        if g.operation is None:
            raise ValueError(f"GateInfo at time={g.time} has no operation object")
        circ.append(g.operation, list(g.qubits))
    return circ


def build_window_circuit(window: TemporalWindow, n_qubits: int) -> QuantumCircuit:
    """Build the exact circuit represented by a temporal window."""
    return build_circuit_from_gates(window.gates, n_qubits)


def build_layer_range_circuit(
    layers: list[list[GateInfo]],
    n_qubits: int,
    layer_start: int,
    layer_end: int,
) -> QuantumCircuit:
    """Build an exact circuit for layers [layer_start, layer_end]."""
    gates: list[GateInfo] = []
    for li in range(max(0, layer_start), min(len(layers), layer_end + 1)):
        gates.extend(layers[li])
    return build_circuit_from_gates(gates, n_qubits)


def normalized_identity_error(circ: QuantumCircuit) -> float:
    """
    Return ||U - exp(i theta) I||_F / sqrt(dim), minimized over global phase.

    A perfect identity up to global phase returns near 0.
    """
    dim = 2 ** circ.num_qubits
    U = Operator(circ).data
    I = np.eye(dim, dtype=complex)
    tr = np.trace(U)
    phase = tr / abs(tr) if abs(tr) > 0 else 1.0
    return float(np.linalg.norm(U - phase * I, ord="fro") / math.sqrt(dim))


def normalized_unitary_error(a: QuantumCircuit, b: QuantumCircuit) -> float:
    """
    Return normalized Frobenius error between two circuits up to global phase.
    """
    if a.num_qubits != b.num_qubits:
        raise ValueError("circuits must have the same number of qubits")
    dim = 2 ** a.num_qubits
    Ua = Operator(a).data
    Ub = Operator(b).data
    overlap = np.trace(Ub.conj().T @ Ua)
    phase = overlap / abs(overlap) if abs(overlap) > 0 else 1.0
    return float(np.linalg.norm(Ua - phase * Ub, ord="fro") / math.sqrt(dim))


def exact_peak_bitstring(circ: QuantumCircuit) -> tuple[str, float]:
    """
    Compute the exact most-probable bitstring from |0...0>.

    Bitstrings follow Qiskit's display convention: qubit 0 is rightmost.
    """
    sv = Statevector.from_instruction(circ)
    probs = sv.probabilities_dict()
    bitstring = max(probs, key=probs.get)
    return bitstring, float(probs[bitstring])


def score_temporal_center_exact(
    layers: list[list[GateInfo]],
    n_qubits: int,
    center: int,
    trial_absorb_layers: int,
    *,
    max_exact_qubits: int = 10,
) -> ExactTemporalScore:
    """
    Exact baby-case score for a temporal center.

    Builds the segment layers [center-K, center+K) in original order and measures
    how close that local segment is to identity. This is a sanity check for
    mirror-like toy circuits, not a scalable algorithm.
    """
    if n_qubits > max_exact_qubits:
        return ExactTemporalScore(
            kind="center_identity",
            center=center,
            window_pair=None,
            layer_range=None,
            n_qubits=n_qubits,
            n_gates=0,
            identity_error=float("inf"),
            peak_bitstring=None,
            peak_probability=None,
            risk_flags=["exact_temporal_score_qubit_limit_exceeded"],
        )

    K = max(1, trial_absorb_layers)
    layer_start = max(0, center - K)
    layer_end = min(len(layers) - 1, center + K - 1)
    circ = build_layer_range_circuit(layers, n_qubits, layer_start, layer_end)
    bitstring, prob = exact_peak_bitstring(circ)
    return ExactTemporalScore(
        kind="center_identity",
        center=center,
        window_pair=None,
        layer_range=(layer_start, layer_end),
        n_qubits=n_qubits,
        n_gates=circ.size(),
        identity_error=normalized_identity_error(circ),
        peak_bitstring=bitstring,
        peak_probability=prob,
        risk_flags=["exact_small_case_only"],
    )


def scan_temporal_centers_exact(
    layers: list[list[GateInfo]],
    n_qubits: int,
    params,
    *,
    max_exact_qubits: int = 10,
) -> list[ExactTemporalScore]:
    """Rank candidate centers by exact small-case identity error."""
    if len(layers) < 2:
        return []

    margin = max(1, params.center_margin)
    stride = max(1, params.center_stride)
    scores = [
        score_temporal_center_exact(
            layers,
            n_qubits,
            center,
            params.trial_absorb_layers,
            max_exact_qubits=max_exact_qubits,
        )
        for center in range(margin, len(layers) - margin, stride)
    ]
    return sorted(scores, key=lambda s: s.identity_error)


def score_window_product_exact(
    window_a: TemporalWindow,
    window_b: TemporalWindow,
    n_qubits: int,
    *,
    max_exact_qubits: int = 10,
) -> ExactTemporalScore:
    """
    Exact baby-case score for the product W_b W_a in original temporal order.
    """
    if n_qubits > max_exact_qubits:
        return ExactTemporalScore(
            kind="window_product_identity",
            center=None,
            window_pair=(window_a.index, window_b.index),
            layer_range=None,
            n_qubits=n_qubits,
            n_gates=0,
            identity_error=float("inf"),
            peak_bitstring=None,
            peak_probability=None,
            risk_flags=["exact_temporal_score_qubit_limit_exceeded"],
        )

    gates = sorted(window_a.gates + window_b.gates, key=lambda g: g.time)
    circ = build_circuit_from_gates(gates, n_qubits)
    bitstring, prob = exact_peak_bitstring(circ)
    return ExactTemporalScore(
        kind="window_product_identity",
        center=None,
        window_pair=(window_a.index, window_b.index),
        layer_range=(window_a.layer_start, window_b.layer_end),
        n_qubits=n_qubits,
        n_gates=circ.size(),
        identity_error=normalized_identity_error(circ),
        peak_bitstring=bitstring,
        peak_probability=prob,
        risk_flags=["exact_small_case_only"],
    )


def scan_adjacent_window_products_exact(
    windows: list[TemporalWindow],
    n_qubits: int,
    *,
    max_exact_qubits: int = 10,
) -> list[ExactTemporalScore]:
    """Rank adjacent window products by exact identity error."""
    scores = [
        score_window_product_exact(windows[i], windows[i + 1], n_qubits,
                                   max_exact_qubits=max_exact_qubits)
        for i in range(len(windows) - 1)
    ]
    return sorted(scores, key=lambda s: s.identity_error)


def exact_score_to_dict(score: ExactTemporalScore) -> dict:
    """JSON-friendly representation of ExactTemporalScore."""
    return {
        "kind": score.kind,
        "center": score.center,
        "window_pair": list(score.window_pair) if score.window_pair else None,
        "layer_range": list(score.layer_range) if score.layer_range else None,
        "n_qubits": score.n_qubits,
        "n_gates": score.n_gates,
        "identity_error": score.identity_error,
        "peak_bitstring": score.peak_bitstring,
        "peak_probability": score.peak_probability,
        "risk_flags": list(score.risk_flags),
    }
