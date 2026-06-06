#!/usr/bin/env python3
from __future__ import annotations

import sys


def main() -> int:
    # The long-running CPU array submitted earlier uses the Aer fallback CLI
    # (--array-index, --order-methods, --bond-dims, --shots). Keep that stable
    # while allowing the newer Quimb runner to remain available for explicit
    # Quimb/CircuitMPS jobs.
    aer_markers = {
        "--array-index",
        "--order-methods",
        "--bond-dims",
        "--shots",
        "--mps-truncation-threshold",
        "--exact-max-qubits",
        "--max-parallel-threads",
    }
    if any(arg in aer_markers for arg in sys.argv[1:]):
        from aer_tree_tensor_runner import main as aer_main

        return aer_main(sys.argv[1:])

    from quimb_tree_tensor_runner import main as quimb_main

    return quimb_main()


if __name__ == "__main__":
    raise SystemExit(main())
