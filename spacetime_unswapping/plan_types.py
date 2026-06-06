"""
Shared dataclasses for the spacetime unswapping package.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GateInfo:
    """Immutable record of a single gate instruction with original metadata."""
    time: int               # original instruction index in qc.data
    layer: int | None       # causal depth layer (None until layerized)
    name: str
    qubits: tuple[int, ...]
    params: tuple[float, ...]
    # operation is excluded from hashing/equality — Qiskit gate objects are mutable
    operation: object = field(default=None, hash=False, compare=False)


@dataclass
class TemporalWindow:
    """A contiguous slice of circuit depth containing a list of gates."""
    index: int
    layer_start: int
    layer_end: int
    gates: list[GateInfo]


@dataclass
class MPOScore:
    """Scoring result from an MPO scorer (proxy or real)."""
    cost: float
    max_bond_dim: int | None
    sum_log_bond_dim: float | None
    size: int | None
    discarded_weight: float | None
    proxy_used: bool
    risk_flags: list[str]


@dataclass
class UnswapMove:
    """A proposed or accepted horizontal/vertical unswap move."""
    kind: str                              # e.g. "horizontal_window_permutation"
    side: str | None                       # "left" | "right" | "both" | None
    qubits: tuple[int, ...]                # qubits involved
    permutation: dict[int, int] | None    # qubit relabeling (src -> dst)
    window_pair: tuple[int, int] | None   # (window_i, window_j) if horizontal
    score_before: float
    score_after: float
    proxy_used: bool
    risk_flags: list[str]


@dataclass
class SpacetimePlan:
    """
    Full output of the spacetime planner.

    global_partition: single (A, B) used across all windows (default).
    vertical_partitions: per-window overrides, keyed by TemporalWindow.index.
    boundary_density_by_window: # cross-partition 2q gates per window index.
    cut_ratio_by_window: cut_ratio computed from gates within each window.
    boundary_size_by_window: # unique qubits in cross-partition gates per window.
    """
    best_center: int | None
    windows: list[TemporalWindow]

    global_partition: tuple[set[int], set[int]] | None

    vertical_partitions: dict[int, tuple[set[int], set[int]]]

    boundary_density_by_window: dict[int, int]
    cut_ratio_by_window: dict[int, float]
    boundary_size_by_window: dict[int, int]

    window_merges: list[dict]
    horizontal_unswaps: list[dict]
    vertical_unswaps: list[dict]

    total_score: float
    fallback_recommended: bool
    risk_flags: list[str]
