"""Path helpers for reusing sibling experimental packages."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPACETIME_DIR = ROOT / "spacetime_unswapping"
MULTI_CENTER_DIR = ROOT / "multi_center_temporal"
PEAKED_SIM_DIR = ROOT / "peaked-circuit-simulation"


def ensure_repo_paths() -> Path:
    """Expose flat modules from the existing packages in a stable order."""
    for path in (ROOT, SPACETIME_DIR, MULTI_CENTER_DIR, PEAKED_SIM_DIR):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    return ROOT

