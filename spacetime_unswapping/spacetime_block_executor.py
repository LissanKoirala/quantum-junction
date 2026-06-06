"""
Spacetime block execution.

This combines temporal center validation with a vertical A|B decomposition:

1. validate a temporal center,
2. build/refine a global vertical partition,
3. split gates into A, B, and cross-boundary gates,
4. run temporal MPO execution on A and B subcircuits,
5. combine the two product MPS blocks,
6. apply boundary gates,
7. extract a peak candidate from the combined MPS.

The first executable version uses one global partition for physical consistency.
Per-window partitions are reported as diagnostics elsewhere, but changing the
partition over time would require explicit migration operators between blocks.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qiskit import QuantumCircuit

from circuit_tools import remove_measurements
from layer_tools import greedy_layerize, layers_to_gate_list
from params import SpacetimeParams
from temporal_global_executor import (
    PeakExtractionResult,
    _ensure_peaked_sim_on_path,
    _mpo_compress_explicit_rewire,
    _mpo_compress_no_rewire,
    _mpo_to_mps_no_rewire,
    extract_peak_from_mps,
)
from temporal_pipeline import exact_peak_bitstring
from temporal_validation import (
    ValidatedTemporalPlan,
    validate_temporal_centers,
    validated_temporal_plan_to_dict,
)
from vertical_unswapping import (
    build_spacetime_interaction_graph,
    compute_boundary_density_per_window,
    compute_window_boundary_sizes,
    compute_window_cut_ratios,
    detect_cross_partition_swaps,
    find_initial_partition,
    refine_partition,
)
from window_tools import make_fixed_layer_windows


def _ensure_separator_on_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    sep = root / "separator_mpo_attack"
    if str(sep) not in sys.path:
        sys.path.insert(0, str(sep))
    return sep


@dataclass
class SpacetimeBlockResult:
    label: str
    n_qubits: int
    n_gates: int
    n_layers: int
    validated_plan: ValidatedTemporalPlan
    center_layer: int | None
    partition_A: list[int]
    partition_B: list[int]
    boundary_gate_count: int
    sub_mps_max_bonds: list[int]
    combined_mps_max_bond: int | None
    peak_extraction: PeakExtractionResult | None
    bitstring_original_order: str | None
    exact_peak_bitstring: str | None
    exact_peak_probability: float | None
    exact_match: bool | None
    vertical_diagnostics: dict[str, Any]
    stats: list[dict[str, Any]]
    risk_flags: list[str]
    wall_seconds: float


def _gate_to_dict(g) -> dict[str, Any]:
    return {
        "time": g.time,
        "name": g.name,
        "qubits": tuple(g.qubits),
        "params": list(g.params),
        "operation": g.operation,
    }


def _split_gates_by_partition(gates, A: set[int], B: set[int]) -> dict[str, list[dict[str, Any]]]:
    out = {"A": [], "B": [], "boundary": []}
    for g in gates:
        d = _gate_to_dict(g)
        qs = tuple(g.qubits)
        if len(qs) == 1:
            if qs[0] in A:
                out["A"].append(d)
            elif qs[0] in B:
                out["B"].append(d)
            else:
                out["boundary"].append(d)
        elif len(qs) == 2:
            if qs[0] in A and qs[1] in A:
                out["A"].append(d)
            elif qs[0] in B and qs[1] in B:
                out["B"].append(d)
            else:
                out["boundary"].append(d)
        else:
            out["boundary"].append(d)
    return out


def _build_remapped_circuit(gates: list[dict[str, Any]], qubit_subset: list[int]) -> QuantumCircuit:
    remap = {orig: new for new, orig in enumerate(qubit_subset)}
    sub = QuantumCircuit(len(qubit_subset))
    for g in sorted(gates, key=lambda x: x["time"]):
        if not all(q in remap for q in g["qubits"]):
            continue
        sub.append(g["operation"], [remap[q] for q in g["qubits"]])
    return sub


def _build_boundary_circuit(
    boundary_gates: list[dict[str, Any]],
    qubit_to_combined_site: dict[int, int],
    n_combined: int,
) -> QuantumCircuit:
    circ = QuantumCircuit(n_combined)
    for g in sorted(boundary_gates, key=lambda x: x["time"]):
        if not all(q in qubit_to_combined_site for q in g["qubits"]):
            continue
        circ.append(g["operation"], [qubit_to_combined_site[q] for q in g["qubits"]])
    return circ


def _sub_center_instruction(gates: list[dict[str, Any]], global_center_instruction: int) -> int:
    return sum(1 for g in gates if g["time"] < global_center_instruction)


def _run_sub_mps(
    subcircuit: QuantumCircuit,
    *,
    center_instruction: int,
    params: SpacetimeParams,
    executor_mode: str,
    run_global_unswap: bool,
    max_global_unswap_its: int,
    early_stopping_gates: int,
    global_hows: tuple[str, ...],
    global_equal: bool,
    sabre_trials: int,
    to_backend=None,
) -> tuple[Any, list[int], list[dict[str, Any]]]:
    if executor_mode == "explicit_rewire":
        threshold = params.unswap_threshold if run_global_unswap else float("inf")
        mpo_core, left, right, stats = _mpo_compress_explicit_rewire(
            subcircuit,
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
    else:
        mpo_core, left, right, stats = _mpo_compress_no_rewire(
            subcircuit,
            center_instruction=center_instruction,
            max_bond=params.max_bond,
            cutoff=params.cutoff_final,
            to_backend=to_backend,
        )
    mps, perm = _mpo_to_mps_no_rewire(
        mpo_core,
        left,
        right,
        max_bond=params.max_bond,
        cutoff=params.cutoff_final,
        to_backend=to_backend,
    )
    return mps, [int(p) for p in perm], stats


def run_spacetime_block_mpo(
    qc_raw,
    label: str,
    params: SpacetimeParams,
    *,
    top_k: int = 5,
    center: int | None = None,
    window_size: int | None = None,
    executor_mode: str = "no_rewire",
    run_global_unswap: bool = False,
    max_global_unswap_its: int = 20,
    early_stopping_gates: int = 100,
    global_hows: tuple[str, ...] = ("both", "left", "right"),
    global_equal: bool = False,
    sabre_trials: int = 10000,
    peak_num_samples: int = 0,
    peak_sample_top_k: int = 32,
    refine_bitflips: bool = True,
    bitflip_rounds: int = 2,
    exact_validate: bool = False,
    max_exact_qubits: int = 10,
    to_backend=None,
) -> SpacetimeBlockResult:
    _ensure_peaked_sim_on_path()
    _ensure_separator_on_path()
    from mps_combine import (
        apply_boundary_to_combined_mps,
        combined_site_map,
        combine_mps_product,
    )

    t0 = time.perf_counter()
    qc_clean = remove_measurements(qc_raw)
    layers = greedy_layerize(qc_clean)
    all_gates = layers_to_gate_list(layers)
    validated = validate_temporal_centers(
        qc_clean,
        params,
        top_k=top_k,
        centers=[center] if center is not None else None,
        to_backend=to_backend,
    )
    center_layer = validated.best_center
    risk_flags = [
        "spacetime_block_mpo",
        "measurements_removed",
        "temporal_center_validated_first",
        "global_partition_execution",
    ]

    if center_layer is None:
        return SpacetimeBlockResult(
            label=label,
            n_qubits=qc_clean.num_qubits,
            n_gates=qc_clean.size(),
            n_layers=len(layers),
            validated_plan=validated,
            center_layer=None,
            partition_A=[],
            partition_B=[],
            boundary_gate_count=0,
            sub_mps_max_bonds=[],
            combined_mps_max_bond=None,
            peak_extraction=None,
            bitstring_original_order=None,
            exact_peak_bitstring=None,
            exact_peak_probability=None,
            exact_match=None,
            vertical_diagnostics={},
            stats=[],
            risk_flags=risk_flags + ["no_validated_center"],
            wall_seconds=time.perf_counter() - t0,
        )

    ws = window_size or params.window_sizes[0]
    windows = make_fixed_layer_windows(layers, ws)
    G = build_spacetime_interaction_graph(all_gates, qc_clean.num_qubits, params)
    A, B = find_initial_partition(G, seed=params.seed)
    A, B, vert_history = refine_partition(all_gates, G, A, B, windows, params)
    cross_swaps = detect_cross_partition_swaps(all_gates, A, B)
    if cross_swaps:
        risk_flags.append("cross_partition_swap_detected")

    split = _split_gates_by_partition(all_gates, A, B)
    A_sorted = sorted(A)
    B_sorted = sorted(B)
    circ_A = _build_remapped_circuit(split["A"], A_sorted)
    circ_B = _build_remapped_circuit(split["B"], B_sorted)

    global_center_instruction = min(
        (g.time for layer in layers[center_layer:center_layer + 1] for g in layer),
        default=len(qc_clean.data),
    )
    center_A = _sub_center_instruction(split["A"], global_center_instruction)
    center_B = _sub_center_instruction(split["B"], global_center_instruction)

    if executor_mode not in {"no_rewire", "explicit_rewire"}:
        raise ValueError("spacetime block executor supports no_rewire or explicit_rewire")

    mps_A, perm_A, stats_A = _run_sub_mps(
        circ_A,
        center_instruction=center_A,
        params=params,
        executor_mode=executor_mode,
        run_global_unswap=run_global_unswap,
        max_global_unswap_its=max_global_unswap_its,
        early_stopping_gates=early_stopping_gates,
        global_hows=global_hows,
        global_equal=global_equal,
        sabre_trials=sabre_trials,
        to_backend=to_backend,
    )
    mps_B, perm_B, stats_B = _run_sub_mps(
        circ_B,
        center_instruction=center_B,
        params=params,
        executor_mode=executor_mode,
        run_global_unswap=run_global_unswap,
        max_global_unswap_its=max_global_unswap_its,
        early_stopping_gates=early_stopping_gates,
        global_hows=global_hows,
        global_equal=global_equal,
        sabre_trials=sabre_trials,
        to_backend=to_backend,
    )

    qubit_to_site = combined_site_map(A_sorted, B_sorted, perm_A, perm_B)
    combined = combine_mps_product(mps_A, mps_B)
    if split["boundary"]:
        boundary_circ = _build_boundary_circuit(
            split["boundary"],
            qubit_to_site,
            qc_clean.num_qubits,
        )
        combined = apply_boundary_to_combined_mps(
            combined,
            boundary_circ,
            params.max_bond,
            params.cutoff_final,
            to_backend=to_backend,
        )

    site_to_qubit = [None] * qc_clean.num_qubits
    for q, site in qubit_to_site.items():
        site_to_qubit[site] = q
    if any(q is None for q in site_to_qubit):
        risk_flags.append("combined_site_mapping_incomplete")
        site_to_qubit = list(range(qc_clean.num_qubits))

    peak, _p0s = extract_peak_from_mps(
        combined,
        [int(q) for q in site_to_qubit],
        num_samples=peak_num_samples,
        sample_top_k=peak_sample_top_k,
        refine_bitflips=refine_bitflips,
        bitflip_rounds=bitflip_rounds,
    )

    exact_bits = None
    exact_prob = None
    exact_match = None
    if exact_validate:
        if qc_clean.num_qubits <= max_exact_qubits:
            exact_bits, exact_prob = exact_peak_bitstring(qc_clean)
            exact_match = peak.best_original_order == exact_bits
        else:
            risk_flags.append("exact_validation_qubit_limit_exceeded")

    vertical_diagnostics = {
        "boundary_density_by_window": compute_boundary_density_per_window(windows, A, B),
        "cut_ratio_by_window": compute_window_cut_ratios(windows, G, A, B),
        "boundary_size_by_window": compute_window_boundary_sizes(windows, G, A, B),
        "vertical_refinement_history": vert_history,
        "cross_partition_swaps": [g.time for g in cross_swaps],
    }

    stats = [
        {"subblock": "A", **s} for s in stats_A
    ] + [
        {"subblock": "B", **s} for s in stats_B
    ]
    if executor_mode == "explicit_rewire":
        risk_flags.append("explicit_rewire_executor")
    else:
        risk_flags.append("no_rewire_executor")
    if run_global_unswap:
        risk_flags.append("global_unswap_enabled")
    else:
        risk_flags.append("global_unswap_disabled")

    return SpacetimeBlockResult(
        label=label,
        n_qubits=qc_clean.num_qubits,
        n_gates=qc_clean.size(),
        n_layers=len(layers),
        validated_plan=validated,
        center_layer=center_layer,
        partition_A=A_sorted,
        partition_B=B_sorted,
        boundary_gate_count=len(split["boundary"]),
        sub_mps_max_bonds=[int(mps_A.max_bond()), int(mps_B.max_bond())],
        combined_mps_max_bond=int(combined.max_bond()),
        peak_extraction=peak,
        bitstring_original_order=peak.best_original_order,
        exact_peak_bitstring=exact_bits,
        exact_peak_probability=exact_prob,
        exact_match=exact_match,
        vertical_diagnostics=vertical_diagnostics,
        stats=stats,
        risk_flags=list(dict.fromkeys(risk_flags)),
        wall_seconds=time.perf_counter() - t0,
    )


def spacetime_block_result_to_dict(
    result: SpacetimeBlockResult,
    *,
    include_stats: bool = True,
    include_validation_stats: bool = False,
) -> dict[str, Any]:
    return {
        "label": result.label,
        "mode": "spacetime_block_mpo",
        "n_qubits": result.n_qubits,
        "n_gates": result.n_gates,
        "n_layers": result.n_layers,
        "center_layer": result.center_layer,
        "partition_A": result.partition_A,
        "partition_B": result.partition_B,
        "boundary_gate_count": result.boundary_gate_count,
        "sub_mps_max_bonds": result.sub_mps_max_bonds,
        "combined_mps_max_bond": result.combined_mps_max_bond,
        "bitstring_original_order": result.bitstring_original_order,
        "exact_peak_bitstring": result.exact_peak_bitstring,
        "exact_peak_probability": result.exact_peak_probability,
        "exact_match": result.exact_match,
        "peak_extraction": None if result.peak_extraction is None else {
            "marginal_original_order": result.peak_extraction.marginal_original_order,
            "best_original_order": result.peak_extraction.best_original_order,
            "probability_estimate": result.peak_extraction.probability_estimate,
            "candidates": result.peak_extraction.candidates,
            "refinement_steps": result.peak_extraction.refinement_steps,
            "n_probability_evaluations": result.peak_extraction.n_probability_evaluations,
            "risk_flags": result.peak_extraction.risk_flags,
        },
        "validated_temporal_plan": validated_temporal_plan_to_dict(
            result.validated_plan,
            include_stats=include_validation_stats,
        ),
        "vertical_diagnostics": result.vertical_diagnostics,
        "stats": result.stats if include_stats else [],
        "risk_flags": result.risk_flags,
        "wall_seconds": result.wall_seconds,
    }
