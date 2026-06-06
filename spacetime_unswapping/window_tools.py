"""
Temporal windowing utilities.

All functions operate on list[list[GateInfo]] (layers) and return
list[TemporalWindow].
"""
from __future__ import annotations

from plan_types import GateInfo, TemporalWindow


def _make_window(
    index: int,
    layers: list[list[GateInfo]],
    layer_start: int,
    layer_end: int,
) -> TemporalWindow:
    """Build a TemporalWindow from a slice of layers [layer_start, layer_end]."""
    gates: list[GateInfo] = []
    for li in range(layer_start, layer_end + 1):
        if 0 <= li < len(layers):
            gates.extend(layers[li])
    return TemporalWindow(
        index=index,
        layer_start=layer_start,
        layer_end=layer_end,
        gates=gates,
    )


def make_fixed_layer_windows(
    layers: list[list[GateInfo]],
    window_size: int,
) -> list[TemporalWindow]:
    """
    Group layers into non-overlapping windows of exactly `window_size` layers.
    The last window may be shorter if len(layers) is not a multiple of window_size.
    """
    if window_size <= 0:
        raise ValueError(f"window_size must be positive, got {window_size}")

    windows: list[TemporalWindow] = []
    L = len(layers)
    for i in range(0, L, window_size):
        end = min(i + window_size, L) - 1
        windows.append(_make_window(len(windows), layers, i, end))
    return windows


def make_twoq_count_windows(
    layers: list[list[GateInfo]],
    target_twoq: int,
) -> list[TemporalWindow]:
    """
    Group layers such that each window contains approximately `target_twoq`
    two-qubit gates. Splits at the first layer that reaches the target.
    """
    if target_twoq <= 0:
        raise ValueError(f"target_twoq must be positive, got {target_twoq}")

    windows: list[TemporalWindow] = []
    L = len(layers)
    window_start = 0
    count = 0

    for li, layer in enumerate(layers):
        count += sum(1 for g in layer if len(g.qubits) == 2)
        if count >= target_twoq or li == L - 1:
            windows.append(_make_window(len(windows), layers, window_start, li))
            window_start = li + 1
            count = 0

    return windows


def make_multi_offset_windows(
    layers: list[list[GateInfo]],
    window_size: int,
    offset: int,
) -> list[TemporalWindow]:
    """
    Skip the first `offset` layers, then create fixed-size windows.
    The skipped layers form a partial window prepended at index 0 if offset > 0.
    """
    if offset < 0 or offset >= window_size:
        raise ValueError(f"offset must be in [0, window_size), got {offset}")

    windows: list[TemporalWindow] = []
    L = len(layers)

    # Optional partial prefix window covering the skipped layers
    if offset > 0 and offset <= L:
        windows.append(_make_window(len(windows), layers, 0, offset - 1))

    for i in range(offset, L, window_size):
        end = min(i + window_size, L) - 1
        windows.append(_make_window(len(windows), layers, i, end))

    return windows


def flatten_window(window: TemporalWindow) -> list[GateInfo]:
    """Return all GateInfo objects in a window, sorted by original time index."""
    return sorted(window.gates, key=lambda g: g.time)


def window_from_layer_range(
    index: int,
    layers: list[list[GateInfo]],
    layer_start: int,
    layer_end: int,
) -> TemporalWindow:
    """Build a TemporalWindow from an explicit [layer_start, layer_end] range."""
    return _make_window(index, layers, layer_start, min(layer_end, len(layers) - 1))
