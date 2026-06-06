from __future__ import annotations

from graph_tools import boundary_vertices
from boundary_scoring import score_boundary


def generate_membership_swap_candidates(
    G, A: set, B: set, boundary_only: bool = True
) -> list[tuple[int, int]]:
    """
    Yield (a, b) pairs: a in A, b in B.
    If boundary_only=True, restrict to vertices with a cross-partition neighbour.
    """
    if boundary_only:
        bA, bB = boundary_vertices(G, A, B)
        candidates_A = bA if bA else A
        candidates_B = bB if bB else B
    else:
        candidates_A, candidates_B = A, B
    return [(a, b) for a in candidates_A for b in candidates_B]


def apply_membership_swap(A: set, B: set, a: int, b: int) -> tuple[set, set]:
    """Swap qubit a (from A) and b (from B); return new (A', B')."""
    A2 = (A - {a}) | {b}
    B2 = (B - {b}) | {a}
    return A2, B2


def refine_partition_by_boundary_swaps(
    qc,
    G,
    A: set,
    B: set,
    params,
    scorer_fn=None,
) -> tuple[set, set, list[dict]]:
    """
    Greedy membership-swap refinement.
    At each iteration, score all (a,b) swap candidates and accept the best improvement.
    Returns (A_refined, B_refined, history).
    """
    current_score = score_boundary(qc, G, A, B, params, scorer_fn=scorer_fn)
    history = []

    for iteration in range(params.max_refinement_iter):
        candidates = generate_membership_swap_candidates(
            G, A, B, boundary_only=params.boundary_only_candidates
        )
        best_move = None
        best_score = current_score.total
        best_new = current_score

        for a, b in candidates:
            A2, B2 = apply_membership_swap(A, B, a, b)
            if not A2 or not B2:
                continue  # don't allow empty sides
            s = score_boundary(qc, G, A2, B2, params, scorer_fn=scorer_fn)
            if s.total < best_score:
                best_score = s.total
                best_move = (a, b)
                best_new = s

        if best_move is None:
            break  # converged

        a, b = best_move
        history.append({
            "iteration": iteration,
            "accepted_move": best_move,
            "old_score": current_score.total,
            "new_score": best_score,
            "old_cut": current_score.cut,
            "new_cut": best_new.cut,
            "old_boundary_size": current_score.boundary_size,
            "new_boundary_size": best_new.boundary_size,
        })
        A, B = apply_membership_swap(A, B, a, b)
        current_score = best_new

    return A, B, history


def generate_ordering_boundary_swaps(
    ordering: list[int], A: set, B: set, window: int = 4
) -> list[tuple[int, int]]:
    """
    Generate candidate adjacent-swap pairs near the A|B separator in the ordering.
    Used as a hook for MPO-boundary unswapping (not used in the minimal proxy phase).
    """
    # Find the A|B interface positions in the ordering
    candidates = []
    n = len(ordering)
    for k in range(n - 1):
        qi, qj = ordering[k], ordering[k + 1]
        # Near a cross-side boundary
        if (qi in A) != (qj in A):
            lo = max(0, k - window)
            hi = min(n - 1, k + window)
            for pos in range(lo, hi):
                candidates.append((ordering[pos], ordering[pos + 1]))
    # Deduplicate while preserving order
    seen = set()
    result = []
    for pair in candidates:
        key = tuple(sorted(pair))
        if key not in seen:
            seen.add(key)
            result.append(pair)
    return result
