"""
MPO scorer hierarchy.

ProxyMPOScorer: structural diagnostics only — no tensor-network validation.
RealMPOScorer: placeholder for future Stage 5 implementation.

Every proxy output carries proxy_used=True and the risk flag
"proxy_mpo_score_no_tensor_validation".
"""
from __future__ import annotations

from plan_types import GateInfo, TemporalWindow, MPOScore
from feature_tools import (
    inverse_symbolic_score,
    permuted_inverse_symbolic_score,
    interaction_graph_similarity,
    proxy_window_mpo_cost,
)


_PROXY_FLAG = "proxy_mpo_score_no_tensor_validation"
_INV_FLAG = "symbolic_inverse_score_requires_real_mpo_validation"


class MPOScorer:
    """Abstract base class for MPO scoring."""

    proxy_used: bool = False

    def score_center(self, qc, layers, center: int, params) -> MPOScore:
        raise NotImplementedError

    def score_window(self, window: TemporalWindow, params) -> MPOScore:
        raise NotImplementedError

    def score_window_product(
        self,
        window_a: TemporalWindow,
        window_b: TemporalWindow,
        permutation: dict[int, int] | None,
        params,
    ) -> MPOScore:
        raise NotImplementedError

    def score_boundary(self, qc, A: set, B: set, windows, params) -> MPOScore:
        raise NotImplementedError


class ProxyMPOScorer(MPOScorer):
    """
    Proxy MPO scorer using gate counts, support size, symbolic inverse matching,
    and interaction graph similarity. No tensor-network computation is performed.

    All outputs carry proxy_used=True and the risk flag
    "proxy_mpo_score_no_tensor_validation".
    """

    proxy_used: bool = True

    def score_window(self, window: TemporalWindow, params) -> MPOScore:
        cost = proxy_window_mpo_cost(window)
        return MPOScore(
            cost=cost,
            max_bond_dim=None,
            sum_log_bond_dim=None,
            size=None,
            discarded_weight=None,
            proxy_used=True,
            risk_flags=[_PROXY_FLAG],
        )

    def score_window_product(
        self,
        window_a: TemporalWindow,
        window_b: TemporalWindow,
        permutation: dict[int, int] | None,
        params,
    ) -> MPOScore:
        """
        Proxy for the product cost window_b @ window_a (right to left).

        Low cost = the product looks like it would compress well (possible inverse).
        High cost = the product looks dense/random.

        Formula (lower is better):
            cost = base_a + base_b
                   - mu_I * inv_score * base_total
                   - mu_G * graph_sim * base_total
                   + small_proxy_penalty
        """
        base_a = proxy_window_mpo_cost(window_a)
        base_b = proxy_window_mpo_cost(window_b)
        base_total = base_a + base_b

        if permutation:
            inv_score = permuted_inverse_symbolic_score(window_a, window_b, permutation)
            graph_sim = interaction_graph_similarity(window_a, window_b, permutation)
        else:
            inv_score = inverse_symbolic_score(window_a, window_b)
            graph_sim = interaction_graph_similarity(window_a, window_b)

        bonus = (
            params.mu_inverse_match * inv_score
            + params.mu_graph_similarity * graph_sim
        ) * base_total

        cost = base_total - bonus + 0.1 * params.proxy_risk_penalty

        return MPOScore(
            cost=max(cost, 0.0),
            max_bond_dim=None,
            sum_log_bond_dim=None,
            size=None,
            discarded_weight=None,
            proxy_used=True,
            risk_flags=[_PROXY_FLAG, _INV_FLAG],
        )

    def score_center(self, qc, layers, center: int, params) -> MPOScore:
        """
        Score a candidate temporal center by evaluating trial windows on both sides.
        """
        from window_tools import window_from_layer_range

        L = len(layers)
        K = min(params.trial_absorb_layers, max(1, L // 2))

        layer_start_l = max(0, center - K)
        layer_end_l = center - 1
        layer_start_r = center
        layer_end_r = min(L - 1, center + K - 1)

        if layer_end_l < layer_start_l or layer_end_r < layer_start_r:
            return MPOScore(
                cost=float("inf"),
                max_bond_dim=None,
                sum_log_bond_dim=None,
                size=None,
                discarded_weight=None,
                proxy_used=True,
                risk_flags=[_PROXY_FLAG, "invalid_center_range"],
            )

        left_w = window_from_layer_range(0, layers, layer_start_l, layer_end_l)
        right_w = window_from_layer_range(1, layers, layer_start_r, layer_end_r)

        return self.score_window_product(left_w, right_w, None, params)

    def score_boundary(self, qc, A: set, B: set, windows, params) -> MPOScore:
        """
        Proxy for the difficulty of applying boundary gates between partitions A and B.
        Based on boundary density across windows and number of boundary gates.
        """
        import math

        total_boundary = sum(
            1 for w in windows
            for g in w.gates
            if len(g.qubits) == 2 and (g.qubits[0] in A) != (g.qubits[1] in A)
        )
        spread = sum(
            1 for w in windows
            if any(
                len(g.qubits) == 2 and (g.qubits[0] in A) != (g.qubits[1] in A)
                for g in w.gates
            )
        )

        boundary_qubits = set()
        for w in windows:
            for g in w.gates:
                if len(g.qubits) == 2 and (g.qubits[0] in A) != (g.qubits[1] in A):
                    boundary_qubits.update(g.qubits)

        bsz = len(boundary_qubits)
        log_proxy = min(bsz, 20) * math.log(2) + math.log(1 + spread)
        cost = log_proxy + math.sqrt(total_boundary)

        return MPOScore(
            cost=cost,
            max_bond_dim=None,
            sum_log_bond_dim=None,
            size=None,
            discarded_weight=None,
            proxy_used=True,
            risk_flags=[_PROXY_FLAG],
        )


class RealMPOScorer(MPOScorer):
    """
    Real partial MPO scorer for temporal center validation.

    Currently only score_center is implemented. Window-product and boundary
    real scoring still need dedicated implementations.
    """

    proxy_used: bool = False

    def score_center(self, qc, layers, center: int, params) -> MPOScore:
        from real_mpo_tools import trial_middle_mpo_score

        result = trial_middle_mpo_score(
            qc,
            center_layer=center,
            params=params,
            trial_absorb_layers=params.trial_absorb_layers,
            absorb_policy=params.trial_absorb_policy,
            run_unswap=params.run_trial_unswap,
            use_rewire=params.use_trial_rewire,
        )
        return result.score

    def score_window(self, window: TemporalWindow, params) -> MPOScore:
        raise NotImplementedError(
            "Real window scoring is not yet implemented. Use --score-mode proxy "
            "or call real_mpo_tools.trial_middle_mpo_score for center trials."
        )

    def score_window_product(self, window_a, window_b, permutation, params) -> MPOScore:
        raise NotImplementedError(
            "Real window-product scoring is not yet implemented. Use --score-mode proxy."
        )

    def score_boundary(self, qc, A, B, windows, params) -> MPOScore:
        raise NotImplementedError(
            "Real boundary scoring is not yet implemented. Use --score-mode proxy."
        )


def make_scorer(params) -> MPOScorer:
    """Factory: return the right scorer for params.score_mode."""
    if params.score_mode == "proxy":
        return ProxyMPOScorer()
    if params.score_mode == "real":
        return RealMPOScorer()
    raise ValueError(f"Unknown score_mode: {params.score_mode!r}. Use 'proxy' or 'real'.")
