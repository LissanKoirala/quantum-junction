# Method Plan

Generated from `reports/qmill_method_report.csv` by `jobs/build_method_plan.py`.
This is a routing plan only; it does not execute any simulations.

## Summary

- Challenges planned: 49
- Missing QASM paths: 0

## Planned Routes

| route | challenges |
|---|---:|
| `exact_statevector_baseline` | 9 |
| `exact_statevector_optional` | 1 |
| `low_bond_mps_distillation` | 24 |
| `mpo_unswapping` | 10 |
| `tno_contraction` | 5 |

## Best Paper Methods

| method | challenges |
|---|---:|
| `low_bond_mps_distillation` | 33 |
| `mpo_unswapping` | 11 |
| `tno_contraction` | 5 |

## Challenge Plan

| challenge | difficulty | q | first action | best paper method | planned route | runner |
|---|---|---:|---|---|---|---|
| 16_12 | easy | 16 | Exact statevector baseline | low_bond_mps_distillation | exact_statevector_baseline | `agent_work/exact_baseline/aer_statevector_peaks.py` |
| 24_13 | easy | 24 | Exact statevector baseline | low_bond_mps_distillation | exact_statevector_baseline | `agent_work/exact_baseline/aer_statevector_peaks.py` |
| 32_14 | easy | 32 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 36_15 | easy | 36 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 40_16 | easy | 40 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 40_17 | easy | 40 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 40_18 | easy | 40 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 48_19 | easy | 48 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 48_20 | easy | 48 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 48_21 | easy | 48 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 56_22 | easy | 56 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 56_23 | easy | 56 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 56_24 | easy | 56 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 64_25 | easy | 64 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 64_26 | easy | 64 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 8_11 | easy | 8 | Exact statevector baseline | low_bond_mps_distillation | exact_statevector_baseline | `agent_work/exact_baseline/aer_statevector_peaks.py` |
| 40_35 | hard | 40 | Tensor Network Operator midpoint contraction | tno_contraction | tno_contraction | `jobs/tno_runner.py` |
| 48_36 | hard | 48 | MPO iterative cancellation with unswapping | mpo_unswapping | mpo_unswapping | `jobs/peaked_mpo_unswap_runner.py` |
| 48_37 | hard | 48 | Tensor Network Operator midpoint contraction | tno_contraction | tno_contraction | `jobs/tno_runner.py` |
| 56_38 | hard | 56 | MPO iterative cancellation with unswapping | mpo_unswapping | mpo_unswapping | `jobs/peaked_mpo_unswap_runner.py` |
| 56_39 | hard | 56 | Tensor Network Operator midpoint contraction | tno_contraction | tno_contraction | `jobs/tno_runner.py` |
| 64_40 | hard | 64 | Tensor Network Operator midpoint contraction | tno_contraction | tno_contraction | `jobs/tno_runner.py` |
| 64_41 | hard | 64 | Tensor Network Operator midpoint contraction | tno_contraction | tno_contraction | `jobs/tno_runner.py` |
| 16_28 | moderate | 16 | Exact statevector baseline | low_bond_mps_distillation | exact_statevector_baseline | `agent_work/exact_baseline/aer_statevector_peaks.py` |
| 24_29 | moderate | 24 | Exact statevector baseline | mpo_unswapping | exact_statevector_baseline | `agent_work/exact_baseline/aer_statevector_peaks.py` |
| 32_30 | moderate | 32 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 48_31 | moderate | 48 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 48_32 | moderate | 48 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 56_33 | moderate | 56 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 64_34 | moderate | 64 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 8_27 | moderate | 8 | Exact statevector baseline | low_bond_mps_distillation | exact_statevector_baseline | `agent_work/exact_baseline/aer_statevector_peaks.py` |
| 16_2 | very_easy | 16 | Exact statevector baseline | low_bond_mps_distillation | exact_statevector_baseline | `agent_work/exact_baseline/aer_statevector_peaks.py` |
| 24_3 | very_easy | 24 | Exact statevector baseline | low_bond_mps_distillation | exact_statevector_baseline | `agent_work/exact_baseline/aer_statevector_peaks.py` |
| 28_4 | very_easy | 28 | Exact if memory allows, then compare paper methods | low_bond_mps_distillation | exact_statevector_optional | `agent_work/exact_baseline/aer_statevector_peaks.py` |
| 32_5 | very_easy | 32 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 36_6 | very_easy | 36 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 40_7 | very_easy | 40 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 48_8 | very_easy | 48 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 56_9 | very_easy | 56 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 64_10 | very_easy | 64 | Low-bond MPS with bitstring distillation | low_bond_mps_distillation | low_bond_mps_distillation | `jobs/quimb_tree_tensor_runner.py` |
| 8_1 | very_easy | 8 | Exact statevector baseline | low_bond_mps_distillation | exact_statevector_baseline | `agent_work/exact_baseline/aer_statevector_peaks.py` |
| 104_49 | very_hard | 104 | MPO iterative cancellation with unswapping | mpo_unswapping | mpo_unswapping | `jobs/peaked_mpo_unswap_runner.py` |
| 48_42 | very_hard | 48 | MPO iterative cancellation with unswapping | mpo_unswapping | mpo_unswapping | `jobs/peaked_mpo_unswap_runner.py` |
| 56_43 | very_hard | 56 | MPO iterative cancellation with unswapping | mpo_unswapping | mpo_unswapping | `jobs/peaked_mpo_unswap_runner.py` |
| 64_44 | very_hard | 64 | MPO iterative cancellation with unswapping | mpo_unswapping | mpo_unswapping | `jobs/peaked_mpo_unswap_runner.py` |
| 72_45 | very_hard | 72 | MPO iterative cancellation with unswapping | mpo_unswapping | mpo_unswapping | `jobs/peaked_mpo_unswap_runner.py` |
| 80_46 | very_hard | 80 | MPO iterative cancellation with unswapping | mpo_unswapping | mpo_unswapping | `jobs/peaked_mpo_unswap_runner.py` |
| 88_47 | very_hard | 88 | MPO iterative cancellation with unswapping | mpo_unswapping | mpo_unswapping | `jobs/peaked_mpo_unswap_runner.py` |
| 96_48 | very_hard | 96 | MPO iterative cancellation with unswapping | mpo_unswapping | mpo_unswapping | `jobs/peaked_mpo_unswap_runner.py` |

## Artifacts

- `plan.jsonl`: full structured route plan with arguments and command previews.
- `plan.tsv`: compact tabular view for quick inspection.
