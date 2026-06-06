import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from circuit_tools import remove_measurements
from layer_tools import greedy_layerize, layers_to_gate_list
from params import SpacetimeParams
from temporal_pipeline import (
    build_circuit_from_gates,
    normalized_identity_error,
    normalized_unitary_error,
    scan_temporal_centers_exact,
)
from test_circuits import make_clean_mirror, make_dense_random


def test_rebuild_from_gate_infos_preserves_unitary():
    qc = remove_measurements(make_clean_mirror(n=3, depth=2))
    layers = greedy_layerize(qc)
    rebuilt = build_circuit_from_gates(layers_to_gate_list(layers), qc.num_qubits)

    assert normalized_unitary_error(qc, rebuilt) < 1e-10


def test_clean_mirror_is_exact_identity_baby_case():
    qc = remove_measurements(make_clean_mirror(n=3, depth=2))

    assert normalized_identity_error(qc) < 1e-10


def test_exact_center_scan_finds_identity_like_segment_on_clean_mirror():
    qc = remove_measurements(make_clean_mirror(n=3, depth=2))
    layers = greedy_layerize(qc)
    params = SpacetimeParams(
        trial_absorb_layers=len(layers),
        center_margin=1,
        center_stride=1,
    )

    scores = scan_temporal_centers_exact(layers, qc.num_qubits, params)

    assert scores
    assert scores[0].identity_error < 1e-10


def test_dense_random_not_exact_identity_baby_case():
    qc = remove_measurements(make_dense_random(n=3, depth=3))

    assert normalized_identity_error(qc) > 1e-3

