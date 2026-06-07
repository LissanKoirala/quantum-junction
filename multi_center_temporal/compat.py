"""Import-path helpers for reusing the existing temporal pipeline modules."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPACETIME_DIR = ROOT / "spacetime_unswapping"


def ensure_spacetime_on_path() -> Path:
    """Make spacetime_unswapping's flat modules importable."""
    if str(SPACETIME_DIR) not in sys.path:
        sys.path.insert(0, str(SPACETIME_DIR))
    return SPACETIME_DIR

