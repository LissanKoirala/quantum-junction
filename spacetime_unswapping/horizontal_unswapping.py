"""
Horizontal unswapping: diagnostics and proposal only (Stage 1-3).

No physical SWAP-network MPOs are inserted. "Horizontal unswap" here means:
    Under this qubit relabeling, window_b looks more like inverse(window_a).
    This permutation is a promising candidate for later real MPO validation.

Risk flags on all outputs:
    proxy_mpo_score_no_tensor_validation
    symbolic_inverse_score_requires_real_mpo_validation
"""
from __future__ import annotations

from plan_types import GateInfo, TemporalWindow, UnswapMove, MPOScore
from feature_tools import window_support, window_interaction_graph
from mpo_scoring import MPOScorer


# ── Permutation candidate generation ─────────────────────────────────────────

def propose_permutations(
    window_a: TemporalWindow,
    window_b: TemporalWindow,
    params,
) -> list[dict[int, int]]:
    """
    Generate candidate qubit permutations mapping window_a qubits -> window_b qubits.

    Candidates (in order):
    1. Identity permutation.
    2. Degree-rank matching (highest degree in graph_a maps to highest in graph_b).
    3. Reversed degree order.
    4. All single adjacent transpositions in the sorted support (for small qubit counts).
    """
    support_a = sorted(window_support(window_a))
    support_b = sorted(window_support(window_b))

    if not support_a or not support_b:
        return [{}]

    candidates: list[dict[int, int]] = []

    # 1. Identity
    identity = {q: q for q in support_a}
    candidates.append(identity)

    if len(support_a) == len(support_b):
        ga = window_interaction_graph(window_a)
        gb = window_interaction_graph(window_b)

        # 2. Degree-rank matching (descending)
        deg_a = sorted(support_a, key=lambda q: ga.degree(q, weight="weight") if q in ga else 0, reverse=True)
        deg_b = sorted(support_b, key=lambda q: gb.degree(q, weight="weight") if q in gb else 0, reverse=True)
        degree_perm = dict(zip(deg_a, deg_b))
        if degree_perm != identity:
            candidates.append(degree_perm)

        # 3. Reversed degree order (A's highest to B's lowest)
        rev_perm = dict(zip(deg_a, reversed(deg_b)))
        if rev_perm not in candidates:
            candidates.append(rev_perm)

        # 4. Adjacent transpositions — swap adjacent qubits in sorted support_a
        if len(support_a) <= 10:
            for k in range(len(support_a) - 1):
                perm = {q: q for q in support_a}
                perm[support_a[k]] = support_a[k + 1]
                perm[support_a[k + 1]] = support_a[k]
                if perm not in candidates:
                    candidates.append(perm)

    return candidates[: params.max_horizontal_candidates]


# ── Per-pair scoring ──────────────────────────────────────────────────────────

def score_horizontal_unswap(
    window_a: TemporalWindow,
    window_b: TemporalWindow,
    permutation: dict[int, int],
    scorer: MPOScorer,
    params,
) -> UnswapMove:
    """
    Score a single candidate permutation for window pair (a, b).
    Returns an UnswapMove recording the before/after proxy costs.
    """
    baseline = scorer.score_window_product(window_a, window_b, None, params)
    with_perm = scorer.score_window_product(window_a, window_b, permutation, params)

    kind = "horizontal_identity" if all(k == v for k, v in permutation.items()) \
        else "horizontal_window_permutation"

    all_qubits = tuple(sorted(window_support(window_a) | window_support(window_b)))

    return UnswapMove(
        kind=kind,
        side=None,
        qubits=all_qubits,
        permutation=dict(permutation),
        window_pair=(window_a.index, window_b.index),
        score_before=baseline.cost,
        score_after=with_perm.cost,
        proxy_used=True,
        risk_flags=[
            "proxy_mpo_score_no_tensor_validation",
            "symbolic_inverse_score_requires_real_mpo_validation",
        ],
    )


def find_best_horizontal_unswap(
    window_a: TemporalWindow,
    window_b: TemporalWindow,
    scorer: MPOScorer,
    params,
) -> UnswapMove | None:
    """
    Try all candidate permutations and return the best UnswapMove.
    If no permutation improves the baseline by more than horizontal_acceptance_margin,
    returns an identity move (score_before == score_after).
    Returns None only if both windows are empty.
    """
    perms = propose_permutations(window_a, window_b, params)
    if not perms:
        return None

    baseline = scorer.score_window_product(window_a, window_b, None, params)
    best_cost = baseline.cost
    best_perm = perms[0]  # identity by default

    for perm in perms:
        s = scorer.score_window_product(window_a, window_b, perm, params)
        if s.cost < best_cost:
            best_cost = s.cost
            best_perm = perm

    improved = best_cost < baseline.cost - params.horizontal_acceptance_margin
    kind = "horizontal_identity" if (
        not improved or all(k == v for k, v in best_perm.items())
    ) else "horizontal_window_permutation"

    all_qubits = tuple(sorted(window_support(window_a) | window_support(window_b)))

    return UnswapMove(
        kind=kind,
        side=None,
        qubits=all_qubits,
        permutation=dict(best_perm),
        window_pair=(window_a.index, window_b.index),
        score_before=baseline.cost,
        score_after=best_cost,
        proxy_used=True,
        risk_flags=[
            "proxy_mpo_score_no_tensor_validation",
            "symbolic_inverse_score_requires_real_mpo_validation",
        ],
    )


# ── Center scanning ───────────────────────────────────────────────────────────

def scan_temporal_centers(
    layers: list[list[GateInfo]],
    scorer: MPOScorer,
    params,
) -> list[dict]:
    """
    For each candidate temporal center c (a layer index), evaluate a trial split:
        left trial window: layers [c - K, c)
        right trial window: layers [c, c + K)

    Returns a list of result dicts sorted by proxy cost (lowest = most promising).
    Each dict: {center, cost, proxy_used, risk_flags}.
    """
    from window_tools import window_from_layer_range

    L = len(layers)
    if L < 2:
        return []

    K = min(params.trial_absorb_layers, max(1, L // 2))
    margin = max(1, params.center_margin)

    results = []

    for c in range(margin, L - margin, max(1, params.center_stride)):
        layer_start_l = max(0, c - K)
        layer_end_l = c - 1
        layer_start_r = c
        layer_end_r = min(L - 1, c + K - 1)

        if layer_end_l < layer_start_l or layer_end_r < layer_start_r:
            continue

        left_w = window_from_layer_range(0, layers, layer_start_l, layer_end_l)
        right_w = window_from_layer_range(1, layers, layer_start_r, layer_end_r)

        score = scorer.score_window_product(left_w, right_w, None, params)

        results.append({
            "center": c,
            "cost": score.cost,
            "proxy_used": score.proxy_used,
            "risk_flags": list(score.risk_flags),
            "left_layers": (layer_start_l, layer_end_l),
            "right_layers": (layer_start_r, layer_end_r),
        })

    results.sort(key=lambda x: x["cost"])
    return results


# ── Mirror pair scanning ──────────────────────────────────────────────────────

def scan_mirror_pairs(
    windows: list[TemporalWindow],
    scorer: MPOScorer,
    params,
) -> list[dict]:
    """
    Score all mirror window pairs (i, m-1-i) as potential inverse pairs.
    Also scores consecutive pairs (i, i+1) for sequential inverse structure.

    Returns a sorted list of result dicts (best proxy score first).
    """
    m = len(windows)
    results = []

    # Mirror pairs
    for i in range(m // 2):
        j = m - 1 - i
        if i >= j:
            break
        wa, wb = windows[i], windows[j]
        move = find_best_horizontal_unswap(wa, wb, scorer, params)
        if move is not None:
            results.append({
                "pair_type": "mirror",
                "window_i": i,
                "window_j": j,
                "best_cost": move.score_after,
                "score_before": move.score_before,
                "improvement": move.score_before - move.score_after,
                "best_permutation": dict(move.permutation) if move.permutation else {},
                "kind": move.kind,
                "proxy_used": move.proxy_used,
                "risk_flags": list(move.risk_flags),
            })

    # Consecutive pairs (for short-range cancellation)
    for i in range(m - 1):
        j = i + 1
        wa, wb = windows[i], windows[j]
        move = find_best_horizontal_unswap(wa, wb, scorer, params)
        if move is not None:
            results.append({
                "pair_type": "consecutive",
                "window_i": i,
                "window_j": j,
                "best_cost": move.score_after,
                "score_before": move.score_before,
                "improvement": move.score_before - move.score_after,
                "best_permutation": dict(move.permutation) if move.permutation else {},
                "kind": move.kind,
                "proxy_used": move.proxy_used,
                "risk_flags": list(move.risk_flags),
            })

    results.sort(key=lambda x: x["best_cost"])
    return results
