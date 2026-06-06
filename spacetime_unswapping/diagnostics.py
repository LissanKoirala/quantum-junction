"""
Diagnostics output: JSON serialization and human-readable summary of SpacetimePlan.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from plan_types import SpacetimePlan, TemporalWindow


# ── JSON serialization ────────────────────────────────────────────────────────

def _safe(x: Any) -> Any:
    """Recursively make x JSON-serializable."""
    if isinstance(x, dict):
        return {str(k): _safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_safe(v) for v in x]
    if isinstance(x, (set, frozenset)):
        return sorted(_safe(v) for v in x)
    if isinstance(x, float):
        if x != x:      # NaN
            return None
        if x == float("inf") or x == float("-inf"):
            return None
        return round(x, 6)
    if isinstance(x, (int, str, bool)) or x is None:
        return x
    return repr(x)


def _window_summary(w: TemporalWindow) -> dict:
    n_twoq = sum(1 for g in w.gates if len(g.qubits) == 2)
    support = sorted(set(q for g in w.gates for q in g.qubits))
    return {
        "index": w.index,
        "layer_start": w.layer_start,
        "layer_end": w.layer_end,
        "n_layers": w.layer_end - w.layer_start + 1,
        "n_gates": len(w.gates),
        "n_twoq_gates": n_twoq,
        "support": support,
        "support_size": len(support),
    }


def plan_to_dict(plan: SpacetimePlan) -> dict:
    """Convert a SpacetimePlan to a JSON-serializable dict."""

    def _partition(p):
        if p is None:
            return None
        A, B = p
        return {"A": sorted(A), "B": sorted(B), "size_A": len(A), "size_B": len(B)}

    return {
        "best_center": plan.best_center,
        "num_windows": len(plan.windows),
        "windows": [_window_summary(w) for w in plan.windows],
        "global_partition": _partition(plan.global_partition),
        "vertical_partitions": {
            str(k): _partition(v) for k, v in plan.vertical_partitions.items()
        },
        "boundary_density_by_window": {
            str(k): v for k, v in plan.boundary_density_by_window.items()
        },
        "cut_ratio_by_window": {
            str(k): round(v, 4) for k, v in plan.cut_ratio_by_window.items()
        },
        "boundary_size_by_window": {
            str(k): v for k, v in plan.boundary_size_by_window.items()
        },
        "window_merges": plan.window_merges,
        "horizontal_unswaps": _safe(plan.horizontal_unswaps),
        "vertical_unswaps": _safe(plan.vertical_unswaps),
        "total_score": _safe(plan.total_score),
        "fallback_recommended": plan.fallback_recommended,
        "risk_flags": plan.risk_flags,
    }


def plan_to_json(plan: SpacetimePlan, indent: int = 2) -> str:
    return json.dumps(plan_to_dict(plan), indent=indent, sort_keys=True)


def write_plan_json(plan: SpacetimePlan, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plan_to_json(plan) + "\n")


# ── Human-readable summary ────────────────────────────────────────────────────

def print_plan_summary(plan: SpacetimePlan, label: str = "") -> None:
    """Print a concise human-readable summary of the SpacetimePlan."""
    hdr = f" SpacetimePlan: {label} " if label else " SpacetimePlan "
    print("\n" + "=" * 60)
    print(hdr.center(60))
    print("=" * 60)

    print(f"\nWindows     : {len(plan.windows)}")
    if plan.best_center is not None:
        print(f"Best center : layer {plan.best_center}")
    else:
        print(f"Best center : (not scanned in this mode)")

    if plan.global_partition is not None:
        A, B = plan.global_partition
        print(f"\nGlobal partition  : |A|={len(A)} |B|={len(B)}")
        print(f"  A qubits : {sorted(A)}")
        print(f"  B qubits : {sorted(B)}")

    if plan.boundary_density_by_window:
        density_vals = list(plan.boundary_density_by_window.values())
        non_zero = sum(1 for d in density_vals if d > 0)
        total_w = len(density_vals)
        print(f"\nBoundary density  : "
              f"min={min(density_vals)} max={max(density_vals)} "
              f"spread={non_zero}/{total_w} windows "
              f"total_boundary_gates={sum(density_vals)}")

    if plan.cut_ratio_by_window:
        cr_vals = list(plan.cut_ratio_by_window.values())
        print(f"Cut ratios        : "
              f"min={min(cr_vals):.3f} max={max(cr_vals):.3f} "
              f"mean={sum(cr_vals)/len(cr_vals):.3f}")

    vert_improved = sum(
        1 for v in plan.vertical_unswaps
        if v.get("new_score", 0) < v.get("old_score", 0)
    )
    print(f"\nVertical unswaps  : {len(plan.vertical_unswaps)} accepted moves "
          f"({vert_improved} improved score)")

    horiz_improved = [h for h in plan.horizontal_unswaps
                      if h.get("improvement", 0) > 0]
    print(f"Horiz. candidates : {len(plan.horizontal_unswaps)} with improvement "
          f"(best: {horiz_improved[0]['improvement']:.4f})"
          if horiz_improved else
          f"Horiz. candidates : {len(plan.horizontal_unswaps)} (none improved baseline)")

    print(f"\nTotal proxy score : {plan.total_score:.4f}")
    print(f"Fallback recommended : {plan.fallback_recommended}")

    if plan.risk_flags:
        print(f"\nRisk flags ({len(plan.risk_flags)}):")
        for f in plan.risk_flags:
            print(f"  ✗ {f}")
    else:
        print("\nRisk flags : none")

    print("\n" + "─" * 60)
    print("WARNING: running in proxy mode. Scores are structural")
    print("diagnostics only. They do not prove MPO compressibility")
    print("and do not recover a bitstring.")
    print("─" * 60)
