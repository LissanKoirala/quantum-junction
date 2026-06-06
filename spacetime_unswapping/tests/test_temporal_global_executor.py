import sys
from pathlib import Path

import pytest

pytest.importorskip("qiskit")
pytest.importorskip("quimb")
pytest.importorskip("qiskit_quimb")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from circuit_tools import remove_measurements
from layer_tools import greedy_layerize
from params import SpacetimeParams
from temporal_global_executor import (
    layer_center_to_instruction_center,
    run_temporal_global_mpo,
    site_bits_to_qiskit_bitstring,
    temporal_global_result_to_dict,
)
from test_circuits import make_clean_mirror


def test_layer_center_to_instruction_center_uses_first_gate_in_layer():
    qc = remove_measurements(make_clean_mirror(n=3, depth=1))
    layers = greedy_layerize(qc)
    center = len(layers) // 2

    inst_center = layer_center_to_instruction_center(qc, center)

    assert inst_center == min(g.time for g in layers[center])


def test_site_bits_to_qiskit_bitstring_reorders_site_order():
    assert site_bits_to_qiskit_bitstring("abc", [2, 0, 1]) == "acb"


def test_temporal_global_mpo_runs_clean_mirror_baby_case():
    qc = remove_measurements(make_clean_mirror(n=3, depth=1))
    params = SpacetimeParams(
        trial_absorb_layers=1,
        run_trial_unswap=False,
        max_bond=128,
        cutoff_window=1e-8,
        cutoff_final=1e-8,
        seed=0,
    )

    result = run_temporal_global_mpo(
        qc,
        "clean_mirror_baby",
        params,
        top_k=1,
        run_global_unswap=False,
        sabre_trials=1,
        exact_validate=True,
    )
    data = temporal_global_result_to_dict(result, include_stats=False)

    assert data["bitstring_original_order"] == "000"
    assert data["exact_peak_bitstring"] == "000"
    assert data["exact_match"] is True
    assert data["mps_max_bond"] is not None
