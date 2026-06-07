"""
Temporal global MPO execution.

This is the first end-to-end temporal pipeline:

1. strip measurements,
2. validate a temporal center with real partial MPO trials,
3. map the layer center to the instruction split used by the existing global
   MPO executor,
4. run full MPO compression,
5. convert the MPO to an MPS,
6. extract a peak candidate from single-qubit marginals, samples, and local
   MPS-probability refinement.

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
class PeakExtractionResult:
    """Peak candidate extraction from a final MPS."""
    marginal_site_bitstring: str | None
    marginal_original_order: str | None
    best_site_bitstring: str | None
    best_original_order: str | None
    probability_estimate: float | None
    marginal_probability_estimate: float | None
    candidates: list[dict[str, Any]]
    refinement_steps: list[dict[str, Any]]
    n_probability_evaluations: int
    risk_flags: list[str]


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
    peak_extraction: PeakExtractionResult | None
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


def qiskit_bitstring_to_site_bits(bitstring: str, site_to_qubit: list[int]) -> str:
    """Convert a Qiskit big-endian bitstring into MPS site order."""
    n = len(bitstring)
    if len(site_to_qubit) != n:
        site_to_qubit = list(range(n))
    qubit_bits = list(reversed(bitstring))
    return "".join(qubit_bits[q] for q in site_to_qubit)


def flip_site_bit(bitstring: str, site: int) -> str:
    """Return a site-order bitstring with one MPS-site bit flipped."""
    if site < 0 or site >= len(bitstring):
        raise IndexError("site out of range")
    flipped = "1" if bitstring[site] == "0" else "0"
    return bitstring[:site] + flipped + bitstring[site + 1:]


def _count_quantum_ops(circuit) -> int:
    ignored = {"barrier", "measure", "delay"}
    return sum(v for k, v in circuit.count_ops().items() if k not in ignored)


def _apply_layer_to_mps(mps, layer, *, max_bond, cutoff, to_backend):
    _ensure_peaked_sim_on_path()
    from quimb.tensor import Circuit
    from qiskit_quimb import quimb_circuit
    from circuit_mpo import mpo_from_circuit, stable_apply_operator

    q2c = lambda qc: quimb_circuit(qc.decompose("unitary"), Circuit, to_backend=to_backend)
    layer_mpo = mpo_from_circuit(q2c(layer))
    return stable_apply_operator(
        layer_mpo,
        mps,
        compress=True,
        max_bond=max_bond,
        cutoff=cutoff,
    )


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


def _mpo_compress_explicit_rewire(
    circuit,
    *,
    center_instruction: int,
    max_bond: int,
    cutoff: float,
    unswap_threshold: float,
    max_unswap_its: int,
    early_stopping_gates: int,
    hows: tuple[str, ...],
    equal: bool,
    seed: int | None,
    sabre_trials: int,
    to_backend=None,
) -> tuple[Any, list, list, list[dict[str, Any]]]:
    """
    Full global MPO compression with explicit threshold unswapping and rewiring.

    This is the transparent replacement for calling `mpo_compress_unswap` as a
    black box. It keeps the same broad mechanics but records when unswapping is
    triggered and when the remaining left/right layer stacks are rewired.
    """
    _ensure_peaked_sim_on_path()
    from qiskit import QuantumCircuit
    from qiskit_quimb import quimb_circuit
    from quimb.tensor import Circuit
    from circuit_mpo import apply_circuit, mpo_from_circuit
    from unswap import rewire_layers, unswap
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
    total_ops = _count_quantum_ops(circuit)
    total_consumed = 0
    ii_left = 0
    ii_right = 0
    stats: list[dict[str, Any]] = [{
        "time": 0.0,
        "stage": "start_explicit_rewire",
        "center_instruction": center_instruction,
        "layers_left": len(layers_left),
        "layers_right": len(layers_right),
        **get_tn_info(mpo_core),
    }]

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

        best_counts = min(counts_left, counts_right)
        if best_counts < unswap_threshold:
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

            total_consumed += new_us
            stats.append({
                "time": time.perf_counter() - t0,
                "stage": "absorbing_explicit_rewire",
                "absorb_side": side,
                "it_left": ii_left,
                "it_right": ii_right,
                "layers_left": len(layers_left),
                "layers_right": len(layers_right),
                "u_consumed": new_us,
                "u_consumed_total": total_consumed,
                **get_tn_info(mpo_core),
            })
            continue

        before = get_tn_info(mpo_core)
        mpo_core, (perm_left, perm_right), unswap_stats = unswap(
            mpo_core,
            hows=hows,
            max_bond=max_bond,
            cutoff=cutoff,
            max_its=max_unswap_its,
            equal=equal,
            to_backend=to_backend,
            t0=t0,
        )
        stats.append({
            "time": time.perf_counter() - t0,
            "stage": "explicit_unswap_trigger",
            "reason": "threshold",
            "it_left": ii_left,
            "it_right": ii_right,
            "counts_left": counts_left,
            "counts_right": counts_right,
            "before": before,
            "after": get_tn_info(mpo_core),
            "perm_left": list(perm_left),
            "perm_right": list(perm_right),
        })
        stats.extend(unswap_stats)

        if ii_left < len(layers_left):
            layers_left = rewire_layers(
                layers_left[ii_left:],
                np.array(perm_left, dtype=int),
                seed=seed,
                sabre_trials=sabre_trials,
            )
        else:
            layers_left = []
        if ii_right < len(layers_right):
            layers_right = rewire_layers(
                layers_right[ii_right:],
                np.array(perm_right, dtype=int),
                seed=seed,
                sabre_trials=sabre_trials,
            )
        else:
            layers_right = []
        stats.append({
            "time": time.perf_counter() - t0,
            "stage": "explicit_rewire_remaining_layers",
            "layers_left": len(layers_left),
            "layers_right": len(layers_right),
        })
        ii_left = 0
        ii_right = 0

        after_elems = get_tn_info(mpo_core)["total_elems"]
        if after_elems >= before["total_elems"] * 0.98:
            # Unswap made no meaningful progress; disable further threshold
            # triggers to prevent an infinite loop on circuits with no
            # swap-cancellable structure.
            unswap_threshold = float("inf")
            stats.append({
                "time": time.perf_counter() - t0,
                "stage": "explicit_rewire_unswap_disabled",
                "reason": "no_progress",
                "before_elems": before["total_elems"],
                "after_elems": after_elems,
            })

        if (total_ops - total_consumed) <= early_stopping_gates:
            stats.append({
                "time": time.perf_counter() - t0,
                "stage": "early_stop_after_explicit_rewire",
                "remaining_ops_estimate": total_ops - total_consumed,
            })
            break

    leftover_left = layers_left[ii_left:]
    leftover_right = layers_right[ii_right:]
    stats.append({
        "time": time.perf_counter() - t0,
        "stage": "end_explicit_rewire",
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

    from circuit_mpo import stable_apply_operator

    final_mps = stable_apply_operator(
        mpo_core,
        final_mps,
        compress=True,
        max_bond=max_bond,
        cutoff=cutoff,
    )

    for layer in layers_right:
        final_mps = _apply_layer_to_mps(
            final_mps,
            layer,
            max_bond=max_bond,
            cutoff=cutoff,
            to_backend=to_backend,
        )

    return final_mps, list(range(len(mpo_core.sites)))


def _score_site_candidate(mps, bitstring: str, cache: dict[str, float | None], optimize: str):
    """Evaluate an MPS site-order bitstring with caching."""
    if bitstring in cache:
        return cache[bitstring]
    from utils import bitstring_probability

    try:
        raw_value = bitstring_probability(mps, bitstring, optimize=optimize)
        if hasattr(raw_value, "item"):
            raw_value = raw_value.item()
        value = float(raw_value)
    except Exception:
        value = None
    cache[bitstring] = value
    return value


def _candidate_row(
    *,
    site_bitstring: str,
    site_to_qubit: list[int],
    probability: float | None,
    source: str,
    count: int | None = None,
) -> dict[str, Any]:
    return {
        "site_bitstring": site_bitstring,
        "bitstring_original_order": site_bits_to_qiskit_bitstring(site_bitstring, site_to_qubit),
        "probability_estimate": probability,
        "source": source,
        "sample_count": count,
    }


def refine_site_bitstring_by_flips(
    mps,
    start_bitstring: str,
    *,
    max_rounds: int = 2,
    min_improvement: float = 0.0,
    optimize: str = "auto-hq",
) -> tuple[str, float | None, list[dict[str, Any]], dict[str, float | None]]:
    """
    Greedy local search over one-bit-flip neighbors in MPS site order.

    This is not a circuit operation. It searches nearby computational-basis
    measurement outcomes using the approximate MPS probability model.
    """
    cache: dict[str, float | None] = {}
    current = start_bitstring
    current_prob = _score_site_candidate(mps, current, cache, optimize)
    steps: list[dict[str, Any]] = []

    if current_prob is None:
        return current, None, steps, cache

    for round_idx in range(max(0, int(max_rounds))):
        best_bits = current
        best_prob = current_prob
        best_site = None
        evaluated = 0

        for site in range(len(current)):
            neighbor = flip_site_bit(current, site)
            prob = _score_site_candidate(mps, neighbor, cache, optimize)
            evaluated += 1
            if prob is not None and prob > best_prob + min_improvement:
                best_bits = neighbor
                best_prob = prob
                best_site = site

        steps.append({
            "round": round_idx,
            "accepted": best_site is not None,
            "flipped_site": best_site,
            "from_site_bitstring": current,
            "to_site_bitstring": best_bits,
            "probability_before": current_prob,
            "probability_after": best_prob,
            "neighbors_evaluated": evaluated,
        })

        if best_site is None:
            break
        current = best_bits
        current_prob = best_prob

    return current, current_prob, steps, cache


def extract_peak_from_mps(
    mps,
    site_to_qubit: list[int],
    *,
    num_samples: int = 0,
    sample_top_k: int = 32,
    sample_max_distance: int = 0,
    refine_bitflips: bool = True,
    bitflip_rounds: int = 2,
    min_bitflip_improvement: float = 0.0,
    optimize: str = "auto-hq",
) -> tuple[PeakExtractionResult, list[float]]:
    """
    Extract a peak candidate from an MPS.

    Sources are marginal voting, optional direct MPS samples, exact MPS
    probability rescoring of candidates, and optional greedy one-bit-flip
    refinement.
    """
    from collections import Counter
    from utils import extract_bitstring, sample_tns

    risk_flags: list[str] = ["mps_peak_extraction"]
    try:
        raw_bits, p0s = extract_bitstring(mps)
    except Exception as exc:
        risk_flags.append("marginal_extraction_failed")
        risk_flags.append(repr(exc))
        raw_bits = "0" * len(site_to_qubit)
        p0s = [0.5 for _ in site_to_qubit]
    cache: dict[str, float | None] = {}
    candidate_sources: dict[str, set[str]] = {raw_bits: {"marginal"}}
    sample_counts: Counter[str] = Counter()
    exhaustive_rescore = False

    if "marginal_extraction_failed" in risk_flags:
        if len(raw_bits) <= 12:
            for idx in range(1 << len(raw_bits)):
                bits = format(idx, f"0{len(raw_bits)}b")
                candidate_sources.setdefault(bits, set()).add("exhaustive")
            exhaustive_rescore = True
            risk_flags.append("small_system_exhaustive_mps_rescore")
        else:
            risk_flags.append("exhaustive_mps_rescore_skipped_large_system")

    if num_samples > 0 and not exhaustive_rescore:
        try:
            samples = sample_tns(
                mps,
                int(num_samples),
                max_distance=sample_max_distance,
                optimize=optimize,
            )
            sample_counts.update(samples)
            for bits, _count in sample_counts.most_common(max(0, int(sample_top_k))):
                candidate_sources.setdefault(bits, set()).add("sample")
        except Exception as exc:
            risk_flags.append("mps_sampling_failed")
            risk_flags.append(repr(exc))
    elif num_samples > 0:
        risk_flags.append("mps_sampling_skipped_exhaustive_rescore")

    candidates: list[dict[str, Any]] = []
    for bits, sources in candidate_sources.items():
        probability = _score_site_candidate(
            mps,
            bits,
            cache,
            "auto" if "exhaustive" in sources else optimize,
        )
        candidates.append(_candidate_row(
            site_bitstring=bits,
            site_to_qubit=site_to_qubit,
            probability=probability,
            source="+".join(sorted(sources)),
            count=sample_counts.get(bits) or None,
        ))

    candidates.sort(
        key=lambda row: (
            row["probability_estimate"] is not None,
            row["probability_estimate"] if row["probability_estimate"] is not None else -1.0,
            row["sample_count"] or 0,
        ),
        reverse=True,
    )

    if candidates:
        best_site_bits = candidates[0]["site_bitstring"]
        best_probability = candidates[0]["probability_estimate"]
    else:
        best_site_bits = raw_bits
        best_probability = _score_site_candidate(mps, raw_bits, cache, optimize)
        risk_flags.append("no_ranked_candidates")

    refinement_steps: list[dict[str, Any]] = []
    if refine_bitflips and best_site_bits is not None:
        refined_bits, refined_prob, refinement_steps, refine_cache = refine_site_bitstring_by_flips(
            mps,
            best_site_bits,
            max_rounds=bitflip_rounds,
            min_improvement=min_bitflip_improvement,
            optimize=optimize,
        )
        cache.update(refine_cache)
        if refined_prob is not None and (best_probability is None or refined_prob >= best_probability):
            best_site_bits = refined_bits
            best_probability = refined_prob
        else:
            risk_flags.append("bitflip_refinement_rejected")
    else:
        risk_flags.append("bitflip_refinement_disabled")

    marginal_probability = _score_site_candidate(mps, raw_bits, cache, optimize)
    if best_site_bits is not None and all(c["site_bitstring"] != best_site_bits for c in candidates):
        candidates.append(_candidate_row(
            site_bitstring=best_site_bits,
            site_to_qubit=site_to_qubit,
            probability=best_probability,
            source="bitflip_refined",
        ))

    result = PeakExtractionResult(
        marginal_site_bitstring=raw_bits,
        marginal_original_order=site_bits_to_qiskit_bitstring(raw_bits, site_to_qubit),
        best_site_bitstring=best_site_bits,
        best_original_order=(
            site_bits_to_qiskit_bitstring(best_site_bits, site_to_qubit)
            if best_site_bits is not None else None
        ),
        probability_estimate=best_probability,
        marginal_probability_estimate=marginal_probability,
        candidates=candidates,
        refinement_steps=refinement_steps,
        n_probability_evaluations=len(cache),
        risk_flags=list(dict.fromkeys(risk_flags)),
    )
    return result, [float(p) for p in p0s]


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
    peak_num_samples: int = 0,
    peak_sample_top_k: int = 32,
    peak_sample_max_distance: int = 0,
    refine_bitflips: bool = True,
    bitflip_rounds: int = 2,
    min_bitflip_improvement: float = 0.0,
    peak_optimize: str = "auto-hq",
    to_backend=None,
    exact_validate: bool = False,
    max_exact_qubits: int = 10,
) -> TemporalGlobalResult:
    """Run validated temporal center selection followed by full MPO extraction."""
    _ensure_peaked_sim_on_path()
    from utils import get_tn_info

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
            peak_extraction=None,
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
    if executor_mode not in {"no_rewire", "explicit_rewire", "existing_unswap"}:
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
    elif executor_mode == "explicit_rewire":
        if not run_global_unswap:
            risk_flags.append("explicit_rewire_without_unswap_requested")
        threshold = params.unswap_threshold if run_global_unswap else float("inf")
        mpo_core, layers_left, layers_right, stats = _mpo_compress_explicit_rewire(
            qc_clean,
            center_instruction=center_instruction,
            max_bond=params.max_bond,
            cutoff=params.cutoff_final,
            unswap_threshold=threshold,
            max_unswap_its=max_global_unswap_its,
            early_stopping_gates=early_stopping_gates,
            hows=global_hows,
            equal=global_equal,
            seed=params.seed,
            sabre_trials=sabre_trials,
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
        risk_flags.append("explicit_rewire_executor")
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
    peak, p0s = extract_peak_from_mps(
        mps,
        site_to_qubit,
        num_samples=peak_num_samples,
        sample_top_k=peak_sample_top_k,
        sample_max_distance=peak_sample_max_distance,
        refine_bitflips=refine_bitflips,
        bitflip_rounds=bitflip_rounds,
        min_bitflip_improvement=min_bitflip_improvement,
        optimize=peak_optimize,
    )
    raw_bits = peak.best_site_bitstring
    bitstring = peak.best_original_order

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
        marginal_p0s=p0s,
        extracted_probability_estimate=peak.probability_estimate,
        peak_extraction=peak,
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
        "peak_extraction": None if result.peak_extraction is None else {
            "marginal_site_bitstring": result.peak_extraction.marginal_site_bitstring,
            "marginal_original_order": result.peak_extraction.marginal_original_order,
            "best_site_bitstring": result.peak_extraction.best_site_bitstring,
            "best_original_order": result.peak_extraction.best_original_order,
            "probability_estimate": result.peak_extraction.probability_estimate,
            "marginal_probability_estimate": (
                result.peak_extraction.marginal_probability_estimate
            ),
            "candidates": result.peak_extraction.candidates,
            "refinement_steps": result.peak_extraction.refinement_steps,
            "n_probability_evaluations": result.peak_extraction.n_probability_evaluations,
            "risk_flags": result.peak_extraction.risk_flags,
        },
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
