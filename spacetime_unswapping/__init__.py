"""
spacetime_unswapping — Stage 1-3 diagnostics prototype.

Provides horizontal and vertical spacetime analysis for peaked-circuit MPO attacks.
All scoring in this stage is proxy-only. No bitstring recovery is performed.

Quick start:
    from spacetime_unswapping.spacetime_planner import run_planner
    from spacetime_unswapping.params import SpacetimeParams

    plan = run_planner(qc, SpacetimeParams())
"""
