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
    flip_site_bit,
    layer_center_to_instruction_center,
    qiskit_bitstring_to_site_bits,
    refine_site_bitstring_by_flips,
    run_temporal_global_mpo,
    site_bits_to_qiskit_bitstring,
    temporal_global_result_to_dict,
)
import temporal_global_executor as tge
from test_circuits import make_clean_mirror


def test_layer_center_to_instruction_center_uses_first_gate_in_layer():
    qc = remove_measurements(make_clean_mirror(n=3, depth=1))
    layers = greedy_layerize(qc)
    center = len(layers) // 2

    inst_center = layer_center_to_instruction_center(qc, center)

    assert inst_center == min(g.time for g in layers[center])


def test_site_bits_to_qiskit_bitstring_reorders_site_order():
    assert site_bits_to_qiskit_bitstring("abc", [2, 0, 1]) == "acb"


def test_qiskit_bitstring_to_site_bits_inverts_site_reordering():
    site_to_qubit = [2, 0, 1]
    site_bits = "101"
    qiskit_bits = site_bits_to_qiskit_bitstring(site_bits, site_to_qubit)

    assert qiskit_bitstring_to_site_bits(qiskit_bits, site_to_qubit) == site_bits


def test_flip_site_bit_is_classical_bitstring_update():
    assert flip_site_bit("000", 1) == "010"
    assert flip_site_bit("010", 1) == "000"


def test_bitflip_refinement_improves_candidate(monkeypatch):
    scores = {
        "000": 0.10,
        "100": 0.20,
        "110": 0.40,
    }

    def fake_score(_mps, bitstring, cache, _optimize):
        value = scores.get(bitstring, 0.0)
        cache[bitstring] = value
        return value

    monkeypatch.setattr(tge, "_score_site_candidate", fake_score)

    refined, refined_prob, steps, cache = refine_site_bitstring_by_flips(
        None,
        "000",
        max_rounds=3,
    )

    assert refined != "000"
    assert refined_prob == scores[refined]
    assert refined_prob > cache["000"]
    assert any(step["accepted"] for step in steps)


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
    assert data["peak_extraction"]["best_original_order"] == "000"
    assert data["peak_extraction"]["marginal_original_order"] == "000"
    assert data["peak_extraction"]["n_probability_evaluations"] >= 1
    assert data["exact_peak_bitstring"] == "000"
    assert data["exact_match"] is True
    assert data["mps_max_bond"] is not None


def test_temporal_global_mpo_explicit_rewire_mode_runs_baby_case():
    qc = remove_measurements(make_clean_mirror(n=3, depth=1))
    params = SpacetimeParams(
        trial_absorb_layers=1,
        max_bond=128,
        cutoff_window=1e-8,
        cutoff_final=1e-8,
        unswap_threshold=1,
        seed=0,
    )

    result = run_temporal_global_mpo(
        qc,
        "clean_mirror_explicit_rewire_baby",
        params,
        top_k=1,
        executor_mode="explicit_rewire",
        run_global_unswap=True,
        max_global_unswap_its=1,
        sabre_trials=1,
        exact_validate=True,
    )
    data = temporal_global_result_to_dict(result, include_stats=False)

    assert data["bitstring_original_order"] == "000"
    assert "explicit_rewire_executor" in data["risk_flags"]
    assert data["exact_match"] is True
