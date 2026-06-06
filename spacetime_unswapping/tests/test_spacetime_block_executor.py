import sys
from pathlib import Path

import pytest

pytest.importorskip("qiskit")
pytest.importorskip("quimb")
pytest.importorskip("qiskit_quimb")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from circuit_tools import remove_measurements
from params import SpacetimeParams
from spacetime_block_executor import run_spacetime_block_mpo, spacetime_block_result_to_dict
from test_circuits import make_clean_mirror, make_modular_mirror


def test_spacetime_block_mpo_runs_clean_mirror_baby_case():
    qc = remove_measurements(make_clean_mirror(n=4, depth=1))
    params = SpacetimeParams(
        trial_absorb_layers=1,
        max_bond=128,
        cutoff_window=1e-8,
        cutoff_final=1e-8,
        seed=0,
    )

    result = run_spacetime_block_mpo(
        qc,
        "clean_mirror_block_baby",
        params,
        top_k=1,
        executor_mode="no_rewire",
        exact_validate=True,
    )
    data = spacetime_block_result_to_dict(result, include_stats=False)

    assert data["bitstring_original_order"] == "0000"
    assert data["exact_peak_bitstring"] == "0000"
    assert data["exact_match"] is True
    assert data["partition_A"]
    assert data["partition_B"]


def test_spacetime_block_mpo_records_boundary_on_modular_case():
    qc = remove_measurements(make_modular_mirror(na=2, nb=2, depth=1, n_cross=1))
    params = SpacetimeParams(
        trial_absorb_layers=1,
        max_bond=128,
        cutoff_window=1e-8,
        cutoff_final=1e-8,
        seed=0,
    )

    result = run_spacetime_block_mpo(
        qc,
        "modular_mirror_block_baby",
        params,
        top_k=1,
        executor_mode="no_rewire",
        exact_validate=True,
    )
    data = spacetime_block_result_to_dict(result, include_stats=False)

    assert data["boundary_gate_count"] >= 0
    assert data["peak_extraction"]["best_original_order"] is not None
    assert "global_partition_execution" in data["risk_flags"]
