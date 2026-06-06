"""
Temporal global MPO execution.

This is the first end-to-end temporal pipeline:

1. strip measurements,
2. validate a temporal center with real partial MPO trials,
3. map the layer center to the instruction split used by the existing global
   MPO executor,
4. run full MPO compression,
5. convert the MPO to an MPS,
6. extract a peak candidate from single-qubit marginals.

It intentionally does not implement spacetime blocking or new rewiring logic.
"""
from __future__ import annotations

import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from circuit_tools import remove_measurements
from layer_tools import greedy_layerize
from params import SpacetimeParams
from temporal_pipeline import exact_peak_bitstring
from temporal_validation import (
    ValidatedTemporalPlan,
    validate_temporal_centers,
    validated_temporal_plan_to_dict,
)


def _ensure_peaked_sim_on_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    peaked = root / "peaked-circuit-simulation"
    if str(peaked) not in sys.path:
        sys.path.insert(0, str(peaked))
    return peaked


def _jsonable(x):
    """Convert numpy scalars and nested containers into JSON-friendly values."""
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return str(x)
    return x


@dataclass
class TemporalGlobalResult:
    """Result of a global temporal MPO execution."""
    label: str
    n_qubits: int
    n_gates: int
    n_layers: int
    validated_plan: ValidatedTemporalPlan
    center_layer: int | None
    center_instruction: int | None
    center_ratio: float | None
    raw_site_bitstring: str | None
    bitstring_original_order: str | None
    site_to_qubit: list[int]
    marginal_p0s: list[float]
    extracted_probability_estimate: float | None
    exact_peak_bitstring: str | None
    exact_peak_probability: float | None
    exact_match: bool | None
    mpo_max_bond: int | None
    mps_max_bond: int | None
    stats: list[dict[str, Any]]
    risk_flags: list[str]
    wall_seconds: float


def layer_center_to_instruction_center(qc_clean, center_layer: int) -> int:
    """
    Convert a layer boundary to the instruction index expected by unswap.py.

    `center_layer` means the cut between layer center_layer - 1 and
    center_layer. The returned instruction index is the first original
    instruction belonging to `center_layer`.
    """
    layers = greedy_layerize(qc_clean)
    if not layers:
        return 0
    if center_layer <= 0:
        return 0
    if center_layer >= len(layers):
        return len(qc_clean.data)
    return min(g.time for g in layers[center_layer])


def site_bits_to_qiskit_bitstring(raw_bits: str, site_to_qubit: list[int]) -> str:
    """
    Convert site-order extracted bits to Qiskit big-endian bitstring order.

    raw_bits[site] is the bit at MPS site `site`; site_to_qubit[site] gives the
    original circuit qubit measured at that site.
    """
    n = len(raw_bits)
    if len(site_to_qubit) != n:
        site_to_qubit = list(range(n))
    qubit_bits = ["?"] * n
    for site, bit in enumerate(raw_bits):
        q = site_to_qubit[site]
        if 0 <= q < n:
            qubit_bits[q] = bit
    return "".join(reversed(qubit_bits))


def _count_quantum_ops(circuit) -> int:
    ignored = {"barrier", "measure", "delay"}
    return sum(v for k, v in circuit.count_ops().items() if k not in ignored)


def _apply_layer_to_mps(mps, layer, *, max_bond, cutoff, to_backend):
    _ensure_peaked_sim_on_path()
    from quimb.tensor import Circuit
    from qiskit_quimb import quimb_circuit
    from circuit_mpo import mpo_from_circuit

    q2c = lambda qc: quimb_circuit(qc.decompose("unitary"), Circuit, to_backend=to_backend)
    layer_mpo = mpo_from_circuit(q2c(layer))
    return layer_mpo.apply(mps, compress=True, max_bond=max_bond, cutoff=cutoff)


def _mpo_compress_no_rewire(
    circuit,
    *,
    center_instruction: int,
    max_bond: int,
    cutoff: float,
    to_backend=None,
) -> tuple[Any, list, list, list[dict[str, Any]]]:
    """
    Full global MPO compression without unswapping or rewiring.

    This mirrors the absorption logic of peaked-circuit-simulation/unswap.py but
    keeps the layer order fixed. It is the clean temporal-only baseline before
    permutation rewiring enters the algorithm.
    """
    _ensure_peaked_sim_on_path()
    from qiskit import QuantumCircuit
    from qiskit_quimb import quimb_circuit
    from quimb.tensor import Circuit
    from circuit_mpo import apply_circuit, mpo_from_circuit
    from utils import elem_counts, get_tn_info, iter_layers, merge_gates

    q2c = lambda qc: quimb_circuit(qc.decompose("unitary"), Circuit, to_backend=to_backend)
    t0 = time.perf_counter()
    n_qubits = circuit.num_qubits
    center_instruction = max(0, min(center_instruction, len(circuit.data)))

    circuit_left = merge_gates(circuit[:center_instruction], n_qubits).inverse()
    circuit_right = merge_gates(circuit[center_instruction:], n_qubits)
    layers_left = list(iter_layers(circuit_left))
    layers_right = list(iter_layers(circuit_right))

    mpo_core = mpo_from_circuit(q2c(QuantumCircuit(n_qubits)))
    stats: list[dict[str, Any]] = [{
        "time": 0.0,
        "stage": "start_no_rewire",
        "it_left": 0,
        "it_right": 0,
        **get_tn_info(mpo_core),
    }]

    ii_left = 0
    ii_right = 0
    total_u_consumed = 0
    while ii_left < len(layers_left) or ii_right < len(layers_right):
        if ii_left < len(layers_left):
            mpo_left = apply_circuit(
                mpo_core,
                q2c(layers_left[ii_left].inverse()),
                side="right",
                max_bond=max_bond,
                cutoff=cutoff,
            )
            counts_left = elem_counts(mpo_left)
        else:
            mpo_left = None
            counts_left = float("inf")

        if ii_right < len(layers_right):
            mpo_right = apply_circuit(
                mpo_core,
                q2c(layers_right[ii_right]),
                side="left",
                max_bond=max_bond,
                cutoff=cutoff,
            )
            counts_right = elem_counts(mpo_right)
        else:
            mpo_right = None
            counts_right = float("inf")

        choose_left = counts_left < counts_right
        if choose_left and mpo_left is not None:
            mpo_core = mpo_left
            new_us = _count_quantum_ops(layers_left[ii_left])
            ii_left += 1
            side = "L"
        elif mpo_right is not None:
            mpo_core = mpo_right
            new_us = _count_quantum_ops(layers_right[ii_right])
            ii_right += 1
            side = "R"
        else:
            break

        total_u_consumed += new_us
        stats.append({
            "time": time.perf_counter() - t0,
            "stage": "absorbing_no_rewire",
            "absorb_side": side,
            "it_left": ii_left,
            "it_right": ii_right,
            "layers_left": len(layers_left),
            "layers_right": len(layers_right),
            "u_consumed": new_us,
            "u_consumed_total": total_u_consumed,
            **get_tn_info(mpo_core),
        })

    leftover_left = layers_left[ii_left:]
    leftover_right = layers_right[ii_right:]
    stats.append({
        "time": time.perf_counter() - t0,
        "stage": "end_no_rewire",
        "leftover_left": len(leftover_left),
        "leftover_right": len(leftover_right),
        **get_tn_info(mpo_core),
    })
    return mpo_core, leftover_left, leftover_right, stats


def _mpo_to_mps_no_rewire(
    mpo_core,
    layers_left,
    layers_right,
    *,
    max_bond: int,
    cutoff: float,
    to_backend=None,
):
    """Convert a no-rewire global MPO and leftovers to an MPS."""
    _ensure_peaked_sim_on_path()
    from qiskit import QuantumCircuit
    from qiskit_quimb import quimb_circuit
    from quimb.tensor import CircuitMPS
    from utils import iter_layers, merge_layers

    final_mps = quimb_circuit(
        QuantumCircuit(len(mpo_core.sites)),
        quimb_circuit_class=CircuitMPS,
        to_backend=to_backend,
    ).psi

    left_forward = list(iter_layers(merge_layers(layers_left).inverse())) if layers_left else []
    for layer in left_forward:
        final_mps = _apply_layer_to_mps(
            final_mps,
            layer,
            max_bond=max_bond,
            cutoff=cutoff,
            to_backend=to_backend,
        )

    final_mps = mpo_core.apply(final_mps, compress=True, max_bond=max_bond, cutoff=cutoff)

    for layer in layers_right:
        final_mps = _apply_layer_to_mps(
            final_mps,
            layer,
            max_bond=max_bond,
            cutoff=cutoff,
            to_backend=to_backend,
        )

    return final_mps, list(range(len(mpo_core.sites)))


def run_temporal_global_mpo(
    qc_raw,
    label: str,
    params: SpacetimeParams,
    *,
    top_k: int = 5,
    center: int | None = None,
    run_trial_unswap: bool | None = None,
    run_global_unswap: bool = True,
    max_global_unswap_its: int = 20,
    early_stopping_gates: int = 100,
    global_hows: tuple[str, ...] = ("both", "left", "right"),
    global_equal: bool = False,
    flip_freq: int | None = None,
    sabre_trials: int = 10000,
    executor_mode: str = "no_rewire",
    to_backend=None,
    exact_validate: bool = False,
    max_exact_qubits: int = 10,
) -> TemporalGlobalResult:
    """Run validated temporal center selection followed by full MPO extraction."""
    _ensure_peaked_sim_on_path()
    from utils import bitstring_probability, extract_bitstring, get_tn_info

    t0 = time.perf_counter()
    qc_clean = remove_measurements(qc_raw)
    layers = greedy_layerize(qc_clean)
    centers = [center] if center is not None else None

    validated = validate_temporal_centers(
        qc_clean,
        params,
        top_k=top_k,
        centers=centers,
        run_unswap=run_trial_unswap,
        to_backend=to_backend,
    )
    center_layer = validated.best_center
    risk_flags = [
        "temporal_global_mpo",
        "measurements_removed",
        "center_validated_by_partial_real_mpo",
        "spacetime_blocking_not_run",
        "new_rewire_not_run",
    ]

    if center_layer is None:
        return TemporalGlobalResult(
            label=label,
            n_qubits=qc_clean.num_qubits,
            n_gates=qc_clean.size(),
            n_layers=len(layers),
            validated_plan=validated,
            center_layer=None,
            center_instruction=None,
            center_ratio=None,
            raw_site_bitstring=None,
            bitstring_original_order=None,
            site_to_qubit=[],
            marginal_p0s=[],
            extracted_probability_estimate=None,
            exact_peak_bitstring=None,
            exact_peak_probability=None,
            exact_match=None,
            mpo_max_bond=None,
            mps_max_bond=None,
            stats=[],
            risk_flags=risk_flags + ["no_validated_center"],
            wall_seconds=time.perf_counter() - t0,
        )

    center_instruction = layer_center_to_instruction_center(qc_clean, center_layer)
    center_ratio = center_instruction
    if executor_mode not in {"no_rewire", "existing_unswap"}:
        raise ValueError(f"unknown executor_mode: {executor_mode!r}")

    if executor_mode == "no_rewire":
        if run_global_unswap:
            risk_flags.append("global_unswap_requested_but_no_rewire_executor_selected")
        mpo_core, layers_left, layers_right, stats = _mpo_compress_no_rewire(
            qc_clean,
            center_instruction=center_instruction,
            max_bond=params.max_bond,
            cutoff=params.cutoff_final,
            to_backend=to_backend,
        )
        mps, site_to_qubit = _mpo_to_mps_no_rewire(
            mpo_core,
            layers_left,
            layers_right,
            max_bond=params.max_bond,
            cutoff=params.cutoff_final,
            to_backend=to_backend,
        )
        risk_flags.append("no_rewire_executor")
    else:
        from unswap import mpo_compress_unswap, mpo_to_mps

        unswap_threshold = params.unswap_threshold if run_global_unswap else float("inf")
        mpo_core, layers_left, layers_right, stats = mpo_compress_unswap(
            qc_clean,
            max_bond=params.max_bond,
            cutoff=params.cutoff_final,
            unswap_threshold=unswap_threshold,
            early_stopping_gates=early_stopping_gates,
            center_ratio=center_instruction,
            equal=global_equal,
            flip_freq=flip_freq,
            max_its=max_global_unswap_its,
            to_backend=to_backend,
            seed=params.seed,
            hows=global_hows,
            sabre_trials=sabre_trials,
        )
        mps, site_to_qubit = mpo_to_mps(
            mpo_core,
            layers_left[:-2],
            layers_right,
            max_bond=params.max_bond,
            cutoff=params.cutoff_final,
            to_backend=to_backend,
        )
        risk_flags.append("existing_unswap_executor")
    raw_bits, p0s = extract_bitstring(mps)
    bitstring = site_bits_to_qiskit_bitstring(raw_bits, site_to_qubit)

    try:
        probability = float(bitstring_probability(mps, raw_bits))
    except Exception:
        probability = None
        risk_flags.append("mps_probability_estimate_failed")

    exact_bits = None
    exact_prob = None
    exact_match = None
    if exact_validate:
        if qc_clean.num_qubits <= max_exact_qubits:
            exact_bits, exact_prob = exact_peak_bitstring(qc_clean)
            exact_match = bitstring == exact_bits
        else:
            risk_flags.append("exact_validation_qubit_limit_exceeded")

    if run_global_unswap:
        risk_flags.append("global_unswap_enabled")
    else:
        risk_flags.append("global_unswap_disabled")
    if executor_mode == "existing_unswap":
        risk_flags.append("existing_executor_uses_sabre_layer_rewrite")

    return TemporalGlobalResult(
        label=label,
        n_qubits=qc_clean.num_qubits,
        n_gates=qc_clean.size(),
        n_layers=len(layers),
        validated_plan=validated,
        center_layer=center_layer,
        center_instruction=center_instruction,
        center_ratio=float(center_instruction / max(1, len(qc_clean.data))),
        raw_site_bitstring=raw_bits,
        bitstring_original_order=bitstring,
        site_to_qubit=[int(q) for q in site_to_qubit],
        marginal_p0s=[float(p) for p in p0s],
        extracted_probability_estimate=probability,
        exact_peak_bitstring=exact_bits,
        exact_peak_probability=exact_prob,
        exact_match=exact_match,
        mpo_max_bond=int(get_tn_info(mpo_core).get("max_bond", mpo_core.max_bond())),
        mps_max_bond=int(mps.max_bond()),
        stats=_jsonable(stats),
        risk_flags=list(dict.fromkeys(risk_flags)),
        wall_seconds=time.perf_counter() - t0,
    )


def temporal_global_result_to_dict(
    result: TemporalGlobalResult,
    *,
    include_stats: bool = True,
    include_validation_stats: bool = False,
) -> dict:
    """JSON-friendly representation of TemporalGlobalResult."""
    return _jsonable({
        "label": result.label,
        "mode": "temporal_global_mpo",
        "n_qubits": result.n_qubits,
        "n_gates": result.n_gates,
        "n_layers": result.n_layers,
        "center_layer": result.center_layer,
        "center_instruction": result.center_instruction,
        "center_ratio": result.center_ratio,
        "raw_site_bitstring": result.raw_site_bitstring,
        "bitstring_original_order": result.bitstring_original_order,
        "site_to_qubit": result.site_to_qubit,
        "marginal_p0s": result.marginal_p0s,
        "extracted_probability_estimate": result.extracted_probability_estimate,
        "exact_peak_bitstring": result.exact_peak_bitstring,
        "exact_peak_probability": result.exact_peak_probability,
        "exact_match": result.exact_match,
        "mpo_max_bond": result.mpo_max_bond,
        "mps_max_bond": result.mps_max_bond,
        "validated_temporal_plan": validated_temporal_plan_to_dict(
            result.validated_plan,
            include_stats=include_validation_stats,
        ),
        "stats": result.stats if include_stats else [],
        "risk_flags": result.risk_flags,
        "wall_seconds": result.wall_seconds,
    })
