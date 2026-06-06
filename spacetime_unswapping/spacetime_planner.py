"""
Spacetime planner: coordinates horizontal and vertical diagnostics into a SpacetimePlan.

Currently implements:
    horizontal_first — scan temporal centers, then find global vertical partition.
    vertical_first — find global partition, then evaluate horizontal structure.

All plans produced in proxy mode carry risk_flags marking them as structural diagnostics.
They do not prove MPO compressibility and do not recover a bitstring.
"""
from __future__ import annotations

import logging

from plan_types import GateInfo, TemporalWindow, SpacetimePlan
from params import SpacetimeParams
from mpo_scoring import MPOScorer, make_scorer

log = logging.getLogger(__name__)


def _make_plan_empty(risk_flags: list[str]) -> SpacetimePlan:
    return SpacetimePlan(
        best_center=None,
        windows=[],
        global_partition=None,
        vertical_partitions={},
        boundary_density_by_window={},
        cut_ratio_by_window={},
        boundary_size_by_window={},
        window_merges=[],
        horizontal_unswaps=[],
        vertical_unswaps=[],
        total_score=float("inf"),
        fallback_recommended=True,
        risk_flags=risk_flags,
    )


# ── Horizontal-first planner ──────────────────────────────────────────────────

def run_horizontal_first_planner(
    qc,
    params: SpacetimeParams,
    scorer: MPOScorer,
) -> SpacetimePlan:
    """
    1. Layerize the circuit.
    2. Scan candidate temporal centers across all window_sizes.
    3. Build temporal windows using the best window_size.
    4. Score mirror and consecutive window pairs for horizontal unswap candidates.
    5. Build global qubit interaction graph and find/refine partition.
    6. Compute per-window boundary diagnostics under the global partition.
    7. Compute a proxy total score and fallback recommendation.
    """
    from circuit_tools import remove_measurements, iter_gate_infos
    from layer_tools import greedy_layerize, layers_to_gate_list
    from window_tools import make_fixed_layer_windows
    from horizontal_unswapping import (
        scan_temporal_centers,
        scan_mirror_pairs,
        find_best_horizontal_unswap,
    )
    from vertical_unswapping import (
        build_spacetime_interaction_graph,
        find_initial_partition,
        refine_partition,
        compute_boundary_density_per_window,
        compute_window_cut_ratios,
        compute_window_boundary_sizes,
        detect_cross_partition_swaps,
        _weighted_cut,
        _total_weight,
    )

    qc_clean = remove_measurements(qc)
    n_qubits = qc_clean.num_qubits
    layers = greedy_layerize(qc_clean)
    all_gates = layers_to_gate_list(layers)

    log.info(f"[horizontal_first] {n_qubits} qubits, {len(layers)} layers, "
             f"{len(all_gates)} gates")

    if not layers:
        return _make_plan_empty(["empty_circuit"])

    risk_flags: list[str] = []

    # ── Step 1: Scan temporal centers ────────────────────────────────────────
    center_results_by_ws: dict[int, list[dict]] = {}
    best_ws = params.window_sizes[0]
    best_center_cost = float("inf")
    best_center: int | None = None
    best_windows: list[TemporalWindow] | None = None

    for ws in params.window_sizes:
        windows = make_fixed_layer_windows(layers, ws)
        if len(windows) < 2:
            continue
        centers = scan_temporal_centers(layers, scorer, params)
        center_results_by_ws[ws] = centers
        if centers and centers[0]["cost"] < best_center_cost:
            best_center_cost = centers[0]["cost"]
            best_center = centers[0]["center"]
            best_ws = ws
            best_windows = windows

    if best_windows is None:
        best_windows = make_fixed_layer_windows(layers, params.window_sizes[0])

    log.info(f"[horizontal_first] Best center: layer={best_center} "
             f"(proxy cost={best_center_cost:.3f}, window_size={best_ws})")

    # ── Step 2: Mirror + consecutive pair unswap candidates ──────────────────
    mirror_results = scan_mirror_pairs(best_windows, scorer, params)
    horizontal_unswaps = []

    for mr in mirror_results:
        i, j = mr["window_i"], mr["window_j"]
        if i >= len(best_windows) or j >= len(best_windows):
            continue
        improvement = mr.get("improvement", 0.0)
        if improvement > params.horizontal_acceptance_margin:
            horizontal_unswaps.append({
                "pair_type": mr["pair_type"],
                "window_pair": [i, j],
                "kind": mr["kind"],
                "permutation": mr["best_permutation"],
                "score_before": mr["score_before"],
                "score_after": mr["best_cost"],
                "improvement": improvement,
                "proxy_used": mr["proxy_used"],
                "risk_flags": mr["risk_flags"],
            })

    if horizontal_unswaps:
        risk_flags.append("proxy_mpo_score_no_tensor_validation")
        risk_flags.append("symbolic_inverse_score_requires_real_mpo_validation")

    log.info(f"[horizontal_first] Horizontal unswap candidates with improvement: "
             f"{len(horizontal_unswaps)}")

    # ── Step 3: Vertical partitioning ────────────────────────────────────────
    G = build_spacetime_interaction_graph(all_gates, n_qubits, params)
    A, B = find_initial_partition(G, seed=params.seed)
    log.info(f"[horizontal_first] Initial partition: |A|={len(A)} |B|={len(B)}")

    A, B, vert_history = refine_partition(all_gates, G, A, B, best_windows, params)
    log.info(f"[horizontal_first] Refined partition: |A|={len(A)} |B|={len(B)} "
             f"({len(vert_history)} moves)")

    vertical_unswaps = [
        {
            "iteration": h["iteration"],
            "move": list(h["move"]),
            "old_score": h["old_score"],
            "new_score": h["new_score"],
        }
        for h in vert_history
    ]

    # Cross-partition SWAP detection
    cross_swaps = detect_cross_partition_swaps(all_gates, A, B)
    if cross_swaps:
        risk_flags.append("cross_partition_swap_detected")
        log.warning(f"[horizontal_first] {len(cross_swaps)} SWAP gate(s) cross the "
                    f"A|B partition — decomposition may be physically invalid.")

    # ── Step 4: Per-window diagnostics ───────────────────────────────────────
    density = compute_boundary_density_per_window(best_windows, A, B)
    cut_ratios = compute_window_cut_ratios(best_windows, G, A, B)
    bsz_by_window = compute_window_boundary_sizes(best_windows, G, A, B)

    # ── Step 5: Fallback decision ─────────────────────────────────────────────
    tw = _total_weight(G)
    global_cut = _weighted_cut(G, A, B)
    global_cut_ratio = global_cut / tw if tw > 0 else 0.0

    num_w = len(best_windows)
    spread = sum(1 for d in density.values() if d > 0)
    spread_fraction = spread / num_w if num_w > 0 else 1.0

    fallback = (
        global_cut_ratio > params.max_cut_ratio
        and spread_fraction > params.max_temporal_spread_fraction
        and not horizontal_unswaps
    )
    if fallback:
        risk_flags.append("fallback_to_global_mpo_recommended")

    if scorer.proxy_used:
        risk_flags.append("proxy_mpo_score_no_tensor_validation")

    # ── Step 6: Total proxy score ────────────────────────────────────────────
    avg_bsz = sum(bsz_by_window.values()) / max(num_w, 1)
    best_mirror_score = mirror_results[0]["best_cost"] if mirror_results else 0.0

    total_score = (
        params.alpha_q_cut * global_cut_ratio
        + params.gamma_boundary_size * avg_bsz
        + params.lambda_temporal_spread * spread_fraction
        - params.mu_inverse_match * (1.0 - best_mirror_score / max(best_center_cost, 1e-9))
        + (params.proxy_risk_penalty if risk_flags else 0.0)
    )

    log.info(f"[horizontal_first] cut_ratio={global_cut_ratio:.3f} "
             f"spread_fraction={spread_fraction:.2f} "
             f"fallback={fallback} total_score={total_score:.3f}")

    return SpacetimePlan(
        best_center=best_center,
        windows=best_windows,
        global_partition=(A, B),
        vertical_partitions={},
        boundary_density_by_window=density,
        cut_ratio_by_window=cut_ratios,
        boundary_size_by_window=bsz_by_window,
        window_merges=[],
        horizontal_unswaps=horizontal_unswaps,
        vertical_unswaps=vertical_unswaps,
        total_score=total_score,
        fallback_recommended=fallback,
        risk_flags=list(dict.fromkeys(risk_flags)),  # deduplicate, preserve order
    )


# ── Vertical-first planner ────────────────────────────────────────────────────

def run_vertical_first_planner(
    qc,
    params: SpacetimeParams,
    scorer: MPOScorer,
) -> SpacetimePlan:
    """
    1. Layerize.
    2. Build global interaction graph, find/refine partition.
    3. Compute per-window boundary density to identify clustered boundary regions.
    4. Scan horizontal unswap candidates focused around high-density windows.
    5. Compute diagnostics and fallback.
    """
    from circuit_tools import remove_measurements
    from layer_tools import greedy_layerize, layers_to_gate_list
    from window_tools import make_fixed_layer_windows
    from horizontal_unswapping import scan_mirror_pairs
    from vertical_unswapping import (
        build_spacetime_interaction_graph,
        find_initial_partition,
        refine_partition,
        compute_boundary_density_per_window,
        compute_window_cut_ratios,
        compute_window_boundary_sizes,
        detect_cross_partition_swaps,
        _weighted_cut,
        _total_weight,
    )

    qc_clean = remove_measurements(qc)
    n_qubits = qc_clean.num_qubits
    layers = greedy_layerize(qc_clean)
    all_gates = layers_to_gate_list(layers)

    if not layers:
        return _make_plan_empty(["empty_circuit"])

    risk_flags: list[str] = []

    # ── Step 1: Global partition ──────────────────────────────────────────────
    G = build_spacetime_interaction_graph(all_gates, n_qubits, params)
    A, B = find_initial_partition(G, seed=params.seed)
    log.info(f"[vertical_first] Initial: |A|={len(A)} |B|={len(B)}")

    ws = params.window_sizes[0]
    windows = make_fixed_layer_windows(layers, ws)

    A, B, vert_history = refine_partition(all_gates, G, A, B, windows, params)
    log.info(f"[vertical_first] Refined: |A|={len(A)} |B|={len(B)} "
             f"({len(vert_history)} moves)")

    vertical_unswaps = [
        {"iteration": h["iteration"], "move": list(h["move"]),
         "old_score": h["old_score"], "new_score": h["new_score"]}
        for h in vert_history
    ]

    cross_swaps = detect_cross_partition_swaps(all_gates, A, B)
    if cross_swaps:
        risk_flags.append("cross_partition_swap_detected")

    # ── Step 2: Boundary density — find clustered windows ────────────────────
    density = compute_boundary_density_per_window(windows, A, B)
    cut_ratios = compute_window_cut_ratios(windows, G, A, B)
    bsz_by_window = compute_window_boundary_sizes(windows, G, A, B)

    # ── Step 3: Horizontal unswap scan ───────────────────────────────────────
    mirror_results = scan_mirror_pairs(windows, scorer, params)
    horizontal_unswaps = [
        {
            "pair_type": mr["pair_type"],
            "window_pair": [mr["window_i"], mr["window_j"]],
            "kind": mr["kind"],
            "permutation": mr["best_permutation"],
            "score_before": mr["score_before"],
            "score_after": mr["best_cost"],
            "improvement": mr.get("improvement", 0.0),
            "proxy_used": mr["proxy_used"],
            "risk_flags": mr["risk_flags"],
        }
        for mr in mirror_results
        if mr.get("improvement", 0.0) > params.horizontal_acceptance_margin
    ]

    if horizontal_unswaps:
        risk_flags += ["proxy_mpo_score_no_tensor_validation",
                       "symbolic_inverse_score_requires_real_mpo_validation"]

    if scorer.proxy_used:
        risk_flags.append("proxy_mpo_score_no_tensor_validation")

    # ── Step 4: Diagnostics and fallback ─────────────────────────────────────
    tw = _total_weight(G)
    global_cut_ratio = _weighted_cut(G, A, B) / tw if tw > 0 else 0.0
    num_w = len(windows)
    spread = sum(1 for d in density.values() if d > 0)
    spread_fraction = spread / num_w if num_w > 0 else 1.0

    fallback = (
        global_cut_ratio > params.max_cut_ratio
        and spread_fraction > params.max_temporal_spread_fraction
        and not horizontal_unswaps
    )
    if fallback:
        risk_flags.append("fallback_to_global_mpo_recommended")

    best_center_scan = None  # vertical_first doesn't scan centers

    avg_bsz = sum(bsz_by_window.values()) / max(num_w, 1)
    total_score = (
        params.alpha_q_cut * global_cut_ratio
        + params.gamma_boundary_size * avg_bsz
        + params.lambda_temporal_spread * spread_fraction
        + (params.proxy_risk_penalty if risk_flags else 0.0)
    )

    return SpacetimePlan(
        best_center=best_center_scan,
        windows=windows,
        global_partition=(A, B),
        vertical_partitions={},
        boundary_density_by_window=density,
        cut_ratio_by_window=cut_ratios,
        boundary_size_by_window=bsz_by_window,
        window_merges=[],
        horizontal_unswaps=horizontal_unswaps,
        vertical_unswaps=vertical_unswaps,
        total_score=total_score,
        fallback_recommended=fallback,
        risk_flags=list(dict.fromkeys(risk_flags)),
    )


# ── Dispatcher ────────────────────────────────────────────────────────────────

def run_planner(
    qc,
    params: SpacetimeParams | None = None,
    scorer: MPOScorer | None = None,
) -> SpacetimePlan:
    """
    Run the spacetime planner according to params.planner_mode.

    If params is None, uses SpacetimeParams() defaults (proxy mode, horizontal_first).
    If scorer is None, creates one via make_scorer(params).
    """
    if params is None:
        params = SpacetimeParams()

    if scorer is None:
        scorer = make_scorer(params)

    if params.planner_mode == "horizontal_first":
        return run_horizontal_first_planner(qc, params, scorer)
    if params.planner_mode == "vertical_first":
        return run_vertical_first_planner(qc, params, scorer)

    raise ValueError(
        f"Unknown planner_mode: {params.planner_mode!r}. "
        f"Use 'horizontal_first' or 'vertical_first'."
    )
