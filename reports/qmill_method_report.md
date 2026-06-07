# Quantum Peak Method Recommendations

This report ranks the three Kremer/Dupuis peaked-circuit methods from static QASM features.
Scores are triage signals, not correctness guarantees.

| circuit | group | q | ops | entanglers | density | swaps | exact baseline | first action | best paper method | score |
|---|---|---:|---:|---:|---:|---:|---|---|---|---:|
| `challenge-16_12.qasm` | easy | 16 | 291 | 137 | 0.5083 | 8 | recommended | Exact statevector baseline | Low-bond MPS with bitstring distillation | 48 |
| `challenge-24_13.qasm` | easy | 24 | 550 | 211 | 0.2428 | 5 | recommended | Exact statevector baseline | Low-bond MPS with bitstring distillation | 76 |
| `challenge-32_14.qasm` | easy | 32 | 875 | 333 | 0.2298 | 3 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 86 |
| `challenge-36_15.qasm` | easy | 36 | 1752 | 393 | 0.2810 | 0 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 90 |
| `challenge-40_16.qasm` | easy | 40 | 969 | 366 | 0.1744 | 5 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 86 |
| `challenge-40_17.qasm` | easy | 40 | 779 | 338 | 0.1615 | 12 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 86 |
| `challenge-40_18.qasm` | easy | 40 | 1328 | 516 | 0.2423 | 1 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 86 |
| `challenge-48_19.qasm` | easy | 48 | 901 | 356 | 0.1090 | 0 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 90 |
| `challenge-48_20.qasm` | easy | 48 | 917 | 328 | 0.1099 | 1 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 86 |
| `challenge-48_21.qasm` | easy | 48 | 1103 | 448 | 0.1472 | 4 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 86 |
| `challenge-56_22.qasm` | easy | 56 | 702 | 299 | 0.0734 | 0 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 90 |
| `challenge-56_23.qasm` | easy | 56 | 1746 | 686 | 0.1552 | 2 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 86 |
| `challenge-56_24.qasm` | easy | 56 | 1418 | 537 | 0.1370 | 1 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 86 |
| `challenge-64_25.qasm` | easy | 64 | 1706 | 704 | 0.1260 | 0 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 90 |
| `challenge-64_26.qasm` | easy | 64 | 1854 | 711 | 0.1270 | 0 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 90 |
| `challenge-8_11.qasm` | easy | 8 | 117 | 38 | 0.4286 | 2 | recommended | Exact statevector baseline | Low-bond MPS with bitstring distillation | 76 |
| `challenge-40_35.qasm` | hard | 40 | 2950 | 1193 | 0.4923 | 0 | not-first-choice | Tensor Network Operator midpoint contraction | Tensor Network Operator midpoint contraction | 74 |
| `challenge-48_36.qasm` | hard | 48 | 2805 | 1150 | 0.3555 | 5 | not-first-choice | MPO iterative cancellation with unswapping | MPO iterative cancellation with unswapping | 69 |
| `challenge-48_37.qasm` | hard | 48 | 3505 | 1481 | 0.4131 | 0 | not-first-choice | Tensor Network Operator midpoint contraction | Tensor Network Operator midpoint contraction | 74 |
| `challenge-56_38.qasm` | hard | 56 | 5939 | 2759 | 0.5409 | 0 | not-first-choice | MPO iterative cancellation with unswapping | MPO iterative cancellation with unswapping | 83 |
| `challenge-56_39.qasm` | hard | 56 | 2783 | 1145 | 0.2429 | 2 | not-first-choice | Tensor Network Operator midpoint contraction | Tensor Network Operator midpoint contraction | 79 |
| `challenge-64_40.qasm` | hard | 64 | 3758 | 1573 | 0.3011 | 0 | not-first-choice | Tensor Network Operator midpoint contraction | Tensor Network Operator midpoint contraction | 89 |
| `challenge-64_41.qasm` | hard | 64 | 3428 | 1428 | 0.2396 | 0 | not-first-choice | Tensor Network Operator midpoint contraction | Tensor Network Operator midpoint contraction | 91 |
| `challenge-16_28.qasm` | moderate | 16 | 1670 | 693 | 0.9250 | 0 | recommended | Exact statevector baseline | Low-bond MPS with bitstring distillation | 52 |
| `challenge-24_29.qasm` | moderate | 24 | 3086 | 1270 | 0.8696 | 3 | recommended | Exact statevector baseline | MPO iterative cancellation with unswapping | 43 |
| `challenge-32_30.qasm` | moderate | 32 | 1977 | 806 | 0.5040 | 5 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 58 |
| `challenge-48_31.qasm` | moderate | 48 | 1265 | 542 | 0.1879 | 11 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 86 |
| `challenge-48_32.qasm` | moderate | 48 | 1790 | 723 | 0.2270 | 5 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 86 |
| `challenge-56_33.qasm` | moderate | 56 | 1510 | 675 | 0.1630 | 0 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 90 |
| `challenge-64_34.qasm` | moderate | 64 | 1948 | 764 | 0.1518 | 3 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 86 |
| `challenge-8_27.qasm` | moderate | 8 | 459 | 173 | 0.9286 | 5 | recommended | Exact statevector baseline | Low-bond MPS with bitstring distillation | 48 |
| `challenge-16_2.qasm` | very_easy | 16 | 308 | 125 | 0.3500 | 1 | recommended | Exact statevector baseline | Low-bond MPS with bitstring distillation | 76 |
| `challenge-24_3.qasm` | very_easy | 24 | 363 | 131 | 0.1993 | 5 | recommended | Exact statevector baseline | Low-bond MPS with bitstring distillation | 76 |
| `challenge-28_4.qasm` | very_easy | 28 | 1220 | 278 | 0.3360 | 0 | possible | Exact if memory allows, then compare paper methods | Low-bond MPS with bitstring distillation | 80 |
| `challenge-32_5.qasm` | very_easy | 32 | 773 | 314 | 0.2137 | 7 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 86 |
| `challenge-36_6.qasm` | very_easy | 36 | 426 | 94 | 0.0714 | 0 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 90 |
| `challenge-40_7.qasm` | very_easy | 40 | 211 | 59 | 0.0346 | 0 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 90 |
| `challenge-48_8.qasm` | very_easy | 48 | 227 | 84 | 0.0293 | 0 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 90 |
| `challenge-56_9.qasm` | very_easy | 56 | 317 | 100 | 0.0247 | 6 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 86 |
| `challenge-64_10.qasm` | very_easy | 64 | 313 | 95 | 0.0193 | 4 | not-first-choice | Low-bond MPS with bitstring distillation | Low-bond MPS with bitstring distillation | 86 |
| `challenge-8_1.qasm` | very_easy | 8 | 46 | 15 | 0.2143 | 1 | recommended | Exact statevector baseline | Low-bond MPS with bitstring distillation | 76 |
| `challenge-104_49.qasm` | very_hard | 104 | 26361 | 5406 | 0.4240 | 0 | not-first-choice | MPO iterative cancellation with unswapping | MPO iterative cancellation with unswapping | 100 |
| `challenge-48_42.qasm` | very_hard | 48 | 20733 | 4221 | 0.9504 | 0 | not-first-choice | MPO iterative cancellation with unswapping | MPO iterative cancellation with unswapping | 100 |
| `challenge-56_43.qasm` | very_hard | 56 | 23004 | 4684 | 0.8792 | 0 | not-first-choice | MPO iterative cancellation with unswapping | MPO iterative cancellation with unswapping | 100 |
| `challenge-64_44.qasm` | very_hard | 64 | 28787 | 5844 | 0.8646 | 0 | not-first-choice | MPO iterative cancellation with unswapping | MPO iterative cancellation with unswapping | 100 |
| `challenge-72_45.qasm` | very_hard | 72 | 28777 | 5852 | 0.7559 | 0 | not-first-choice | MPO iterative cancellation with unswapping | MPO iterative cancellation with unswapping | 100 |
| `challenge-80_46.qasm` | very_hard | 80 | 34586 | 7030 | 0.7475 | 0 | not-first-choice | MPO iterative cancellation with unswapping | MPO iterative cancellation with unswapping | 100 |
| `challenge-88_47.qasm` | very_hard | 88 | 37660 | 7654 | 0.6975 | 0 | not-first-choice | MPO iterative cancellation with unswapping | MPO iterative cancellation with unswapping | 100 |
| `challenge-96_48.qasm` | very_hard | 96 | 28703 | 5866 | 0.5164 | 0 | not-first-choice | MPO iterative cancellation with unswapping | MPO iterative cancellation with unswapping | 100 |

## Details

### challenge-16_12.qasm

- Static band: `exact-friendly`
- Difficulty group: `easy`
- Features: q=16, ops=291, depth~96, entanglers=137, density=0.5083, swaps=8
- Exact baseline: `recommended` because Exact statevector should be the first solve and the verification baseline.
- First action: Exact statevector baseline

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: weak fit, score 48/100

- 16 qubits is inside the practical range for MPS trials.
- 291 operations is a reasonable first-pass simulation size.
- The static size band is exact-friendly, so a heuristic sampler is worth trying.

- Caveat: Dense entangling connectivity can inflate MPS bond dimension.
- Caveat: 8 explicit swaps can scramble bit positions; track bit order carefully.
- Caveat: Exact statevector is simpler for this size; use MPS only as a cross-check.

**Tensor Network Operator midpoint contraction**: poor fit, score 32/100

- Moderate graph density keeps TNO plausible if bond growth stays bounded.
- Repeated two-qubit pairs exist; max repetition is 7, which can indicate inverse blocks.

- Caveat: 8 swaps suggest permutation structure that TNO alone may not control.

**MPO iterative cancellation with unswapping**: poor fit, score 17/100

- Moderate-to-dense connectivity could still benefit from adaptive rewiring.
- 8 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: This is small enough that MPO unswapping is likely overkill.
- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-24_13.qasm

- Static band: `exact-friendly`
- Difficulty group: `easy`
- Features: q=24, ops=550, depth~138, entanglers=211, density=0.2428, swaps=5
- Exact baseline: `recommended` because Exact statevector should be the first solve and the verification baseline.
- First action: Exact statevector baseline

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 76/100

- 24 qubits is inside the practical range for MPS trials.
- 550 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is exact-friendly, so a heuristic sampler is worth trying.

- Caveat: 5 explicit swaps can scramble bit positions; track bit order carefully.
- Caveat: Exact statevector is simpler for this size; use MPS only as a cross-check.

**Tensor Network Operator midpoint contraction**: weak fit, score 54/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 13, which can indicate inverse blocks.

- Caveat: 5 swaps suggest permutation structure that TNO alone may not control.

**MPO iterative cancellation with unswapping**: poor fit, score 7/100

- 5 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: This is small enough that MPO unswapping is likely overkill.
- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-32_14.qasm

- Static band: `light or moderate`
- Difficulty group: `easy`
- Features: q=32, ops=875, depth~169, entanglers=333, density=0.2298, swaps=3
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 86/100

- 32 qubits is inside the practical range for MPS trials.
- 875 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

- Caveat: 3 explicit swaps can scramble bit positions; track bit order carefully.

**Tensor Network Operator midpoint contraction**: usable fit, score 71/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 11, which can indicate inverse blocks.

- Caveat: 3 swaps is low, but still weakens the no-permutation assumption.

**MPO iterative cancellation with unswapping**: weak fit, score 35/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 3 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-36_15.qasm

- Static band: `light or moderate`
- Difficulty group: `easy`
- Features: q=36, ops=1752, depth~207, entanglers=393, density=0.2810, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 90/100

- 36 qubits is inside the practical range for MPS trials.
- 1752 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

**Tensor Network Operator midpoint contraction**: usable fit, score 66/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 5, which can indicate inverse blocks.

- Caveat: A full-width leading one-qubit dressing layer looks like heavier obfuscation.

**MPO iterative cancellation with unswapping**: usable fit, score 57/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- A full-width leading one-qubit prefix is a strong obfuscation signal.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

### challenge-40_16.qasm

- Static band: `light or moderate`
- Difficulty group: `easy`
- Features: q=40, ops=969, depth~174, entanglers=366, density=0.1744, swaps=5
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 86/100

- 40 qubits is inside the practical range for MPS trials.
- 969 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

- Caveat: 5 explicit swaps can scramble bit positions; track bit order carefully.

**Tensor Network Operator midpoint contraction**: usable fit, score 71/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 11, which can indicate inverse blocks.

- Caveat: 5 swaps is low, but still weakens the no-permutation assumption.

**MPO iterative cancellation with unswapping**: weak fit, score 35/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 5 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-40_17.qasm

- Static band: `light or moderate`
- Difficulty group: `easy`
- Features: q=40, ops=779, depth~158, entanglers=338, density=0.1615, swaps=12
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 86/100

- 40 qubits is inside the practical range for MPS trials.
- 779 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

- Caveat: 12 explicit swaps can scramble bit positions; track bit order carefully.

**Tensor Network Operator midpoint contraction**: weak fit, score 51/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 10, which can indicate inverse blocks.

- Caveat: 12 swaps suggest permutation structure that TNO alone may not control.

**MPO iterative cancellation with unswapping**: weak fit, score 35/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 12 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-40_18.qasm

- Static band: `light or moderate`
- Difficulty group: `easy`
- Features: q=40, ops=1328, depth~199, entanglers=516, density=0.2423, swaps=1
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 86/100

- 40 qubits is inside the practical range for MPS trials.
- 1328 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

- Caveat: 1 explicit swaps can scramble bit positions; track bit order carefully.

**Tensor Network Operator midpoint contraction**: usable fit, score 70/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 10, which can indicate inverse blocks.

- Caveat: 1 swaps is low, but still weakens the no-permutation assumption.

**MPO iterative cancellation with unswapping**: weak fit, score 35/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 1 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-48_19.qasm

- Static band: `light or moderate`
- Difficulty group: `easy`
- Features: q=48, ops=901, depth~148, entanglers=356, density=0.1090, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 90/100

- 48 qubits is inside the practical range for MPS trials.
- 901 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

**Tensor Network Operator midpoint contraction**: strong fit, score 78/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 7, which can indicate inverse blocks.

**MPO iterative cancellation with unswapping**: poor fit, score 31/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-48_20.qasm

- Static band: `light or moderate`
- Difficulty group: `easy`
- Features: q=48, ops=917, depth~178, entanglers=328, density=0.1099, swaps=1
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 86/100

- 48 qubits is inside the practical range for MPS trials.
- 917 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

- Caveat: 1 explicit swaps can scramble bit positions; track bit order carefully.

**Tensor Network Operator midpoint contraction**: usable fit, score 69/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 9, which can indicate inverse blocks.

- Caveat: 1 swaps is low, but still weakens the no-permutation assumption.

**MPO iterative cancellation with unswapping**: weak fit, score 35/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 1 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-48_21.qasm

- Static band: `light or moderate`
- Difficulty group: `easy`
- Features: q=48, ops=1103, depth~199, entanglers=448, density=0.1472, swaps=4
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 86/100

- 48 qubits is inside the practical range for MPS trials.
- 1103 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

- Caveat: 4 explicit swaps can scramble bit positions; track bit order carefully.

**Tensor Network Operator midpoint contraction**: usable fit, score 70/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 10, which can indicate inverse blocks.

- Caveat: 4 swaps is low, but still weakens the no-permutation assumption.

**MPO iterative cancellation with unswapping**: weak fit, score 35/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 4 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-56_22.qasm

- Static band: `light or moderate`
- Difficulty group: `easy`
- Features: q=56, ops=702, depth~142, entanglers=299, density=0.0734, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 90/100

- 56 qubits is inside the practical range for MPS trials.
- 702 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

**Tensor Network Operator midpoint contraction**: strong fit, score 81/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 10, which can indicate inverse blocks.

**MPO iterative cancellation with unswapping**: poor fit, score 31/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-56_23.qasm

- Static band: `light or moderate`
- Difficulty group: `easy`
- Features: q=56, ops=1746, depth~304, entanglers=686, density=0.1552, swaps=2
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 86/100

- 56 qubits is inside the practical range for MPS trials.
- 1746 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

- Caveat: 2 explicit swaps can scramble bit positions; track bit order carefully.

**Tensor Network Operator midpoint contraction**: usable fit, score 70/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 10, which can indicate inverse blocks.

- Caveat: 2 swaps is low, but still weakens the no-permutation assumption.

**MPO iterative cancellation with unswapping**: weak fit, score 47/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 2 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

### challenge-56_24.qasm

- Static band: `light or moderate`
- Difficulty group: `easy`
- Features: q=56, ops=1418, depth~198, entanglers=537, density=0.1370, swaps=1
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 86/100

- 56 qubits is inside the practical range for MPS trials.
- 1418 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

- Caveat: 1 explicit swaps can scramble bit positions; track bit order carefully.

**Tensor Network Operator midpoint contraction**: usable fit, score 71/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 11, which can indicate inverse blocks.

- Caveat: 1 swaps is low, but still weakens the no-permutation assumption.

**MPO iterative cancellation with unswapping**: weak fit, score 35/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 1 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-64_25.qasm

- Static band: `light or moderate`
- Difficulty group: `easy`
- Features: q=64, ops=1706, depth~179, entanglers=704, density=0.1260, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 90/100

- 64 qubits is inside the practical range for MPS trials.
- 1706 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

**Tensor Network Operator midpoint contraction**: strong fit, score 82/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 11, which can indicate inverse blocks.

**MPO iterative cancellation with unswapping**: weak fit, score 43/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

### challenge-64_26.qasm

- Static band: `light or moderate`
- Difficulty group: `easy`
- Features: q=64, ops=1854, depth~260, entanglers=711, density=0.1270, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 90/100

- 64 qubits is inside the practical range for MPS trials.
- 1854 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

**Tensor Network Operator midpoint contraction**: strong fit, score 79/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 8, which can indicate inverse blocks.

**MPO iterative cancellation with unswapping**: weak fit, score 43/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

### challenge-8_11.qasm

- Static band: `exact-friendly`
- Difficulty group: `easy`
- Features: q=8, ops=117, depth~64, entanglers=38, density=0.4286, swaps=2
- Exact baseline: `recommended` because Exact statevector should be the first solve and the verification baseline.
- First action: Exact statevector baseline

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 76/100

- 8 qubits is inside the practical range for MPS trials.
- 117 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is exact-friendly, so a heuristic sampler is worth trying.

- Caveat: 2 explicit swaps can scramble bit positions; track bit order carefully.
- Caveat: Exact statevector is simpler for this size; use MPS only as a cross-check.

**Tensor Network Operator midpoint contraction**: weak fit, score 51/100

- Moderate graph density keeps TNO plausible if bond growth stays bounded.
- Repeated two-qubit pairs exist; max repetition is 7, which can indicate inverse blocks.

- Caveat: 2 swaps is low, but still weakens the no-permutation assumption.

**MPO iterative cancellation with unswapping**: poor fit, score 17/100

- Moderate-to-dense connectivity could still benefit from adaptive rewiring.
- 2 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: This is small enough that MPO unswapping is likely overkill.
- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-40_35.qasm

- Static band: `simulation-heavy`
- Difficulty group: `hard`
- Features: q=40, ops=2950, depth~316, entanglers=1193, density=0.4923, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Tensor Network Operator midpoint contraction

Suggested next steps for `tno_contraction`:

- Layer the circuit and absorb gates from the temporal midpoint outward.
- Track max bond and total tensor elements after each chunk.
- Abandon this path if bond dimension grows before many layers are absorbed.

**Tensor Network Operator midpoint contraction**: usable fit, score 74/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Moderate graph density keeps TNO plausible if bond growth stays bounded.
- Repeated two-qubit pairs exist; max repetition is 11, which can indicate inverse blocks.
- The file is hard but does not show strong explicit permutation evidence.

**MPO iterative cancellation with unswapping**: usable fit, score 65/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- Moderate-to-dense connectivity could still benefit from adaptive rewiring.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.
- The hard label plus size/density makes a structural deobfuscation path worth prioritizing.

**Low-bond MPS with bitstring distillation**: weak fit, score 44/100

- 40 qubits is inside the practical range for MPS trials.
- 2950 operations is a reasonable first-pass simulation size.
- The static size band is simulation-heavy, so a heuristic sampler is worth trying.

- Caveat: Dense entangling connectivity can inflate MPS bond dimension.
- Caveat: The problem is labeled hard, so MPS should be treated as a candidate generator.

### challenge-48_36.qasm

- Static band: `simulation-heavy`
- Difficulty group: `hard`
- Features: q=48, ops=2805, depth~306, entanglers=1150, density=0.3555, swaps=5
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: MPO iterative cancellation with unswapping

Suggested next steps for `mpo_unswapping`:

- Split the circuit near the midpoint and absorb left/right layers into a central MPO.
- When bond growth spikes, greedily test nearest-neighbor swaps and keep swaps that reduce MPO size.
- Use the resulting MPO/MPS to sample or extract per-qubit marginals for candidate bitstrings.

**MPO iterative cancellation with unswapping**: usable fit, score 69/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- Moderate-to-dense connectivity could still benefit from adaptive rewiring.
- 5 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

**Low-bond MPS with bitstring distillation**: usable fit, score 68/100

- 48 qubits is inside the practical range for MPS trials.
- 2805 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is simulation-heavy, so a heuristic sampler is worth trying.

- Caveat: The problem is labeled hard, so MPS should be treated as a candidate generator.
- Caveat: 5 explicit swaps can scramble bit positions; track bit order carefully.

**Tensor Network Operator midpoint contraction**: usable fit, score 55/100

- Moderate graph density keeps TNO plausible if bond growth stays bounded.
- Repeated two-qubit pairs exist; max repetition is 11, which can indicate inverse blocks.

- Caveat: 5 swaps is low, but still weakens the no-permutation assumption.

### challenge-48_37.qasm

- Static band: `simulation-heavy`
- Difficulty group: `hard`
- Features: q=48, ops=3505, depth~514, entanglers=1481, density=0.4131, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Tensor Network Operator midpoint contraction

Suggested next steps for `tno_contraction`:

- Layer the circuit and absorb gates from the temporal midpoint outward.
- Track max bond and total tensor elements after each chunk.
- Abandon this path if bond dimension grows before many layers are absorbed.

**Tensor Network Operator midpoint contraction**: usable fit, score 74/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Moderate graph density keeps TNO plausible if bond growth stays bounded.
- Repeated two-qubit pairs exist; max repetition is 11, which can indicate inverse blocks.
- The file is hard but does not show strong explicit permutation evidence.

**Low-bond MPS with bitstring distillation**: usable fit, score 72/100

- 48 qubits is inside the practical range for MPS trials.
- 3505 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is simulation-heavy, so a heuristic sampler is worth trying.

- Caveat: The problem is labeled hard, so MPS should be treated as a candidate generator.

**MPO iterative cancellation with unswapping**: usable fit, score 65/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- Moderate-to-dense connectivity could still benefit from adaptive rewiring.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.
- The hard label plus size/density makes a structural deobfuscation path worth prioritizing.

### challenge-56_38.qasm

- Static band: `simulation-heavy`
- Difficulty group: `hard`
- Features: q=56, ops=5939, depth~652, entanglers=2759, density=0.5409, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: MPO iterative cancellation with unswapping

Suggested next steps for `mpo_unswapping`:

- Split the circuit near the midpoint and absorb left/right layers into a central MPO.
- When bond growth spikes, greedily test nearest-neighbor swaps and keep swaps that reduce MPO size.
- Use the resulting MPO/MPS to sample or extract per-qubit marginals for candidate bitstrings.

**MPO iterative cancellation with unswapping**: strong fit, score 83/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 5939 operations is large enough to justify cancellation plus unswapping.
- Moderate-to-dense connectivity could still benefit from adaptive rewiring.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

**Tensor Network Operator midpoint contraction**: strong fit, score 75/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Moderate graph density keeps TNO plausible if bond growth stays bounded.
- Repeated two-qubit pairs exist; max repetition is 12, which can indicate inverse blocks.
- The file is hard but does not show strong explicit permutation evidence.

**Low-bond MPS with bitstring distillation**: weak fit, score 44/100

- 56 qubits is inside the practical range for MPS trials.
- 5939 operations is a reasonable first-pass simulation size.
- The static size band is simulation-heavy, so a heuristic sampler is worth trying.

- Caveat: Dense entangling connectivity can inflate MPS bond dimension.
- Caveat: The problem is labeled hard, so MPS should be treated as a candidate generator.

### challenge-56_39.qasm

- Static band: `simulation-heavy`
- Difficulty group: `hard`
- Features: q=56, ops=2783, depth~329, entanglers=1145, density=0.2429, swaps=2
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Tensor Network Operator midpoint contraction

Suggested next steps for `tno_contraction`:

- Layer the circuit and absorb gates from the temporal midpoint outward.
- Track max bond and total tensor elements after each chunk.
- Abandon this path if bond dimension grows before many layers are absorbed.

**Tensor Network Operator midpoint contraction**: strong fit, score 79/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 11, which can indicate inverse blocks.
- The file is hard but does not show strong explicit permutation evidence.

- Caveat: 2 swaps is low, but still weakens the no-permutation assumption.

**Low-bond MPS with bitstring distillation**: usable fit, score 68/100

- 56 qubits is inside the practical range for MPS trials.
- 2783 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is simulation-heavy, so a heuristic sampler is worth trying.

- Caveat: The problem is labeled hard, so MPS should be treated as a candidate generator.
- Caveat: 2 explicit swaps can scramble bit positions; track bit order carefully.

**MPO iterative cancellation with unswapping**: weak fit, score 47/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 2 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

### challenge-64_40.qasm

- Static band: `simulation-heavy`
- Difficulty group: `hard`
- Features: q=64, ops=3758, depth~307, entanglers=1573, density=0.3011, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Tensor Network Operator midpoint contraction

Suggested next steps for `tno_contraction`:

- Layer the circuit and absorb gates from the temporal midpoint outward.
- Track max bond and total tensor elements after each chunk.
- Abandon this path if bond dimension grows before many layers are absorbed.

**Tensor Network Operator midpoint contraction**: strong fit, score 89/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 10, which can indicate inverse blocks.
- The file is hard but does not show strong explicit permutation evidence.

**Low-bond MPS with bitstring distillation**: usable fit, score 72/100

- 64 qubits is inside the practical range for MPS trials.
- 3758 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is simulation-heavy, so a heuristic sampler is worth trying.

- Caveat: The problem is labeled hard, so MPS should be treated as a candidate generator.

**MPO iterative cancellation with unswapping**: weak fit, score 43/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

### challenge-64_41.qasm

- Static band: `simulation-heavy`
- Difficulty group: `hard`
- Features: q=64, ops=3428, depth~372, entanglers=1428, density=0.2396, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Tensor Network Operator midpoint contraction

Suggested next steps for `tno_contraction`:

- Layer the circuit and absorb gates from the temporal midpoint outward.
- Track max bond and total tensor elements after each chunk.
- Abandon this path if bond dimension grows before many layers are absorbed.

**Tensor Network Operator midpoint contraction**: strong fit, score 91/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 12, which can indicate inverse blocks.
- The file is hard but does not show strong explicit permutation evidence.

**Low-bond MPS with bitstring distillation**: usable fit, score 72/100

- 64 qubits is inside the practical range for MPS trials.
- 3428 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is simulation-heavy, so a heuristic sampler is worth trying.

- Caveat: The problem is labeled hard, so MPS should be treated as a candidate generator.

**MPO iterative cancellation with unswapping**: weak fit, score 43/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

### challenge-16_28.qasm

- Static band: `exact-friendly`
- Difficulty group: `moderate`
- Features: q=16, ops=1670, depth~500, entanglers=693, density=0.9250, swaps=0
- Exact baseline: `recommended` because Exact statevector should be the first solve and the verification baseline.
- First action: Exact statevector baseline

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: weak fit, score 52/100

- 16 qubits is inside the practical range for MPS trials.
- 1670 operations is a reasonable first-pass simulation size.
- The static size band is exact-friendly, so a heuristic sampler is worth trying.

- Caveat: Dense entangling connectivity can inflate MPS bond dimension.
- Caveat: Exact statevector is simpler for this size; use MPS only as a cross-check.

**MPO iterative cancellation with unswapping**: weak fit, score 49/100

- Dense entangling connectivity suggests hidden permutation/ordering trouble.
- Dense connectivity without explicit swaps can mean the permutation is hidden in rewrites.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: This is small enough that MPO unswapping is likely overkill.

**Tensor Network Operator midpoint contraction**: weak fit, score 43/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Repeated two-qubit pairs exist; max repetition is 18, which can indicate inverse blocks.

- Caveat: Dense all-to-all-like connectivity is a bad sign for plain TNO contraction.

### challenge-24_29.qasm

- Static band: `hard or very-hard`
- Difficulty group: `moderate`
- Features: q=24, ops=3086, depth~534, entanglers=1270, density=0.8696, swaps=3
- Exact baseline: `recommended` because Exact statevector should be the first solve and the verification baseline.
- First action: Exact statevector baseline

Suggested next steps for `mpo_unswapping`:

- Split the circuit near the midpoint and absorb left/right layers into a central MPO.
- When bond growth spikes, greedily test nearest-neighbor swaps and keep swaps that reduce MPO size.
- Use the resulting MPO/MPS to sample or extract per-qubit marginals for candidate bitstrings.

**MPO iterative cancellation with unswapping**: weak fit, score 43/100

- Dense entangling connectivity suggests hidden permutation/ordering trouble.
- 3 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: This is small enough that MPO unswapping is likely overkill.

**Low-bond MPS with bitstring distillation**: weak fit, score 40/100

- 24 qubits is inside the practical range for MPS trials.
- 3086 operations is a reasonable first-pass simulation size.

- Caveat: Dense entangling connectivity can inflate MPS bond dimension.
- Caveat: 3 explicit swaps can scramble bit positions; track bit order carefully.
- Caveat: Exact statevector is simpler for this size; use MPS only as a cross-check.

**Tensor Network Operator midpoint contraction**: poor fit, score 32/100

- Repeated two-qubit pairs exist; max repetition is 17, which can indicate inverse blocks.

- Caveat: 3 swaps is low, but still weakens the no-permutation assumption.
- Caveat: Dense all-to-all-like connectivity is a bad sign for plain TNO contraction.

### challenge-32_30.qasm

- Static band: `simulation-heavy`
- Difficulty group: `moderate`
- Features: q=32, ops=1977, depth~323, entanglers=806, density=0.5040, swaps=5
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: usable fit, score 58/100

- 32 qubits is inside the practical range for MPS trials.
- 1977 operations is a reasonable first-pass simulation size.
- The static size band is simulation-heavy, so a heuristic sampler is worth trying.

- Caveat: Dense entangling connectivity can inflate MPS bond dimension.
- Caveat: 5 explicit swaps can scramble bit positions; track bit order carefully.

**MPO iterative cancellation with unswapping**: usable fit, score 57/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- Moderate-to-dense connectivity could still benefit from adaptive rewiring.
- 5 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

**Tensor Network Operator midpoint contraction**: weak fit, score 38/100

- Moderate graph density keeps TNO plausible if bond growth stays bounded.
- Repeated two-qubit pairs exist; max repetition is 13, which can indicate inverse blocks.

- Caveat: 5 swaps suggest permutation structure that TNO alone may not control.

### challenge-48_31.qasm

- Static band: `light or moderate`
- Difficulty group: `moderate`
- Features: q=48, ops=1265, depth~254, entanglers=542, density=0.1879, swaps=11
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 86/100

- 48 qubits is inside the practical range for MPS trials.
- 1265 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

- Caveat: 11 explicit swaps can scramble bit positions; track bit order carefully.

**Tensor Network Operator midpoint contraction**: weak fit, score 53/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 12, which can indicate inverse blocks.

- Caveat: 11 swaps suggest permutation structure that TNO alone may not control.

**MPO iterative cancellation with unswapping**: weak fit, score 35/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 11 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-48_32.qasm

- Static band: `light or moderate`
- Difficulty group: `moderate`
- Features: q=48, ops=1790, depth~328, entanglers=723, density=0.2270, swaps=5
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 86/100

- 48 qubits is inside the practical range for MPS trials.
- 1790 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

- Caveat: 5 explicit swaps can scramble bit positions; track bit order carefully.

**Tensor Network Operator midpoint contraction**: usable fit, score 72/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 12, which can indicate inverse blocks.

- Caveat: 5 swaps is low, but still weakens the no-permutation assumption.

**MPO iterative cancellation with unswapping**: weak fit, score 47/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 5 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

### challenge-56_33.qasm

- Static band: `light or moderate`
- Difficulty group: `moderate`
- Features: q=56, ops=1510, depth~294, entanglers=675, density=0.1630, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 90/100

- 56 qubits is inside the practical range for MPS trials.
- 1510 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

**Tensor Network Operator midpoint contraction**: strong fit, score 82/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 11, which can indicate inverse blocks.

**MPO iterative cancellation with unswapping**: weak fit, score 43/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

### challenge-64_34.qasm

- Static band: `light or moderate`
- Difficulty group: `moderate`
- Features: q=64, ops=1948, depth~265, entanglers=764, density=0.1518, swaps=3
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 86/100

- 64 qubits is inside the practical range for MPS trials.
- 1948 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

- Caveat: 3 explicit swaps can scramble bit positions; track bit order carefully.

**Tensor Network Operator midpoint contraction**: usable fit, score 71/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 11, which can indicate inverse blocks.

- Caveat: 3 swaps is low, but still weakens the no-permutation assumption.

**MPO iterative cancellation with unswapping**: weak fit, score 47/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 3 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

### challenge-8_27.qasm

- Static band: `exact-friendly`
- Difficulty group: `moderate`
- Features: q=8, ops=459, depth~203, entanglers=173, density=0.9286, swaps=5
- Exact baseline: `recommended` because Exact statevector should be the first solve and the verification baseline.
- First action: Exact statevector baseline

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: weak fit, score 48/100

- 8 qubits is inside the practical range for MPS trials.
- 459 operations is a reasonable first-pass simulation size.
- The static size band is exact-friendly, so a heuristic sampler is worth trying.

- Caveat: Dense entangling connectivity can inflate MPS bond dimension.
- Caveat: 5 explicit swaps can scramble bit positions; track bit order carefully.
- Caveat: Exact statevector is simpler for this size; use MPS only as a cross-check.

**MPO iterative cancellation with unswapping**: weak fit, score 45/100

- Dense entangling connectivity suggests hidden permutation/ordering trouble.
- A full-width leading one-qubit prefix is a strong obfuscation signal.
- 5 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: This is small enough that MPO unswapping is likely overkill.
- Caveat: The circuit is small enough that simpler simulation should come first.

**Tensor Network Operator midpoint contraction**: poor fit, score 3/100

- Repeated two-qubit pairs exist; max repetition is 19, which can indicate inverse blocks.

- Caveat: 5 swaps suggest permutation structure that TNO alone may not control.
- Caveat: Dense all-to-all-like connectivity is a bad sign for plain TNO contraction.
- Caveat: A full-width leading one-qubit dressing layer looks like heavier obfuscation.

### challenge-16_2.qasm

- Static band: `exact-friendly`
- Difficulty group: `very_easy`
- Features: q=16, ops=308, depth~105, entanglers=125, density=0.3500, swaps=1
- Exact baseline: `recommended` because Exact statevector should be the first solve and the verification baseline.
- First action: Exact statevector baseline

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 76/100

- 16 qubits is inside the practical range for MPS trials.
- 308 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is exact-friendly, so a heuristic sampler is worth trying.

- Caveat: 1 explicit swaps can scramble bit positions; track bit order carefully.
- Caveat: Exact statevector is simpler for this size; use MPS only as a cross-check.

**Tensor Network Operator midpoint contraction**: usable fit, score 68/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 8, which can indicate inverse blocks.

- Caveat: 1 swaps is low, but still weakens the no-permutation assumption.

**MPO iterative cancellation with unswapping**: poor fit, score 17/100

- Moderate-to-dense connectivity could still benefit from adaptive rewiring.
- 1 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: This is small enough that MPO unswapping is likely overkill.
- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-24_3.qasm

- Static band: `exact-friendly`
- Difficulty group: `very_easy`
- Features: q=24, ops=363, depth~87, entanglers=131, density=0.1993, swaps=5
- Exact baseline: `recommended` because Exact statevector should be the first solve and the verification baseline.
- First action: Exact statevector baseline

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 76/100

- 24 qubits is inside the practical range for MPS trials.
- 363 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is exact-friendly, so a heuristic sampler is worth trying.

- Caveat: 5 explicit swaps can scramble bit positions; track bit order carefully.
- Caveat: Exact statevector is simpler for this size; use MPS only as a cross-check.

**Tensor Network Operator midpoint contraction**: weak fit, score 48/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 7, which can indicate inverse blocks.

- Caveat: 5 swaps suggest permutation structure that TNO alone may not control.

**MPO iterative cancellation with unswapping**: poor fit, score 7/100

- 5 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: This is small enough that MPO unswapping is likely overkill.
- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-28_4.qasm

- Static band: `exact-friendly`
- Difficulty group: `very_easy`
- Features: q=28, ops=1220, depth~229, entanglers=278, density=0.3360, swaps=0
- Exact baseline: `possible` because Exact statevector is memory-heavy but still plausible on a strong machine.
- First action: Exact if memory allows, then compare paper methods

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 80/100

- 28 qubits is inside the practical range for MPS trials.
- 1220 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is exact-friendly, so a heuristic sampler is worth trying.

- Caveat: Exact statevector is simpler for this size; use MPS only as a cross-check.

**Tensor Network Operator midpoint contraction**: usable fit, score 67/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 6, which can indicate inverse blocks.

- Caveat: A full-width leading one-qubit dressing layer looks like heavier obfuscation.

**MPO iterative cancellation with unswapping**: poor fit, score 17/100

- A full-width leading one-qubit prefix is a strong obfuscation signal.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: This is small enough that MPO unswapping is likely overkill.
- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-32_5.qasm

- Static band: `light or moderate`
- Difficulty group: `very_easy`
- Features: q=32, ops=773, depth~211, entanglers=314, density=0.2137, swaps=7
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 86/100

- 32 qubits is inside the practical range for MPS trials.
- 773 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

- Caveat: 7 explicit swaps can scramble bit positions; track bit order carefully.

**Tensor Network Operator midpoint contraction**: weak fit, score 49/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 8, which can indicate inverse blocks.

- Caveat: 7 swaps suggest permutation structure that TNO alone may not control.

**MPO iterative cancellation with unswapping**: weak fit, score 35/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 7 explicit swaps give the unswapping path concrete permutation evidence.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-36_6.qasm

- Static band: `light or moderate`
- Difficulty group: `very_easy`
- Features: q=36, ops=426, depth~79, entanglers=94, density=0.0714, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 90/100

- 36 qubits is inside the practical range for MPS trials.
- 426 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

**Tensor Network Operator midpoint contraction**: usable fit, score 65/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 4, which can indicate inverse blocks.

- Caveat: A full-width leading one-qubit dressing layer looks like heavier obfuscation.

**MPO iterative cancellation with unswapping**: weak fit, score 45/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- A full-width leading one-qubit prefix is a strong obfuscation signal.
- Many repeated entangling pairs support the mirror-circuit cancellation hypothesis.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-40_7.qasm

- Static band: `light or moderate`
- Difficulty group: `very_easy`
- Features: q=40, ops=211, depth~33, entanglers=59, density=0.0346, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 90/100

- 40 qubits is inside the practical range for MPS trials.
- 211 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

**Tensor Network Operator midpoint contraction**: strong fit, score 76/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 5, which can indicate inverse blocks.

**MPO iterative cancellation with unswapping**: poor fit, score 23/100

- Exact statevector is not a safe default, so a structure-aware method is needed.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-48_8.qasm

- Static band: `light or moderate`
- Difficulty group: `very_easy`
- Features: q=48, ops=227, depth~47, entanglers=84, density=0.0293, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 90/100

- 48 qubits is inside the practical range for MPS trials.
- 227 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

**Tensor Network Operator midpoint contraction**: strong fit, score 77/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 6, which can indicate inverse blocks.

**MPO iterative cancellation with unswapping**: poor fit, score 23/100

- Exact statevector is not a safe default, so a structure-aware method is needed.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-56_9.qasm

- Static band: `light or moderate`
- Difficulty group: `very_easy`
- Features: q=56, ops=317, depth~76, entanglers=100, density=0.0247, swaps=6
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 86/100

- 56 qubits is inside the practical range for MPS trials.
- 317 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

- Caveat: 6 explicit swaps can scramble bit positions; track bit order carefully.

**Tensor Network Operator midpoint contraction**: usable fit, score 67/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 7, which can indicate inverse blocks.

- Caveat: 6 swaps is low, but still weakens the no-permutation assumption.

**MPO iterative cancellation with unswapping**: poor fit, score 27/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 6 explicit swaps give the unswapping path concrete permutation evidence.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-64_10.qasm

- Static band: `light or moderate`
- Difficulty group: `very_easy`
- Features: q=64, ops=313, depth~34, entanglers=95, density=0.0193, swaps=4
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: Low-bond MPS with bitstring distillation

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 86/100

- 64 qubits is inside the practical range for MPS trials.
- 313 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is light or moderate, so a heuristic sampler is worth trying.

- Caveat: 4 explicit swaps can scramble bit positions; track bit order carefully.

**Tensor Network Operator midpoint contraction**: usable fit, score 66/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 6, which can indicate inverse blocks.

- Caveat: 4 swaps is low, but still weakens the no-permutation assumption.

**MPO iterative cancellation with unswapping**: poor fit, score 27/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 4 explicit swaps give the unswapping path concrete permutation evidence.

- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-8_1.qasm

- Static band: `exact-friendly`
- Difficulty group: `very_easy`
- Features: q=8, ops=46, depth~21, entanglers=15, density=0.2143, swaps=1
- Exact baseline: `recommended` because Exact statevector should be the first solve and the verification baseline.
- First action: Exact statevector baseline

Suggested next steps for `low_bond_mps_distillation`:

- Run Qiskit Aer MPS with a small bond-dimension ladder such as 16, 32, 64.
- Aggregate samples by per-bit majority vote, then verify the full bitstring if possible.
- Increase shots before increasing bond dimension when top candidates are unstable.

**Low-bond MPS with bitstring distillation**: strong fit, score 76/100

- 8 qubits is inside the practical range for MPS trials.
- 46 operations is a reasonable first-pass simulation size.
- The entangling graph is not too dense, so low bond dimensions are more plausible.
- The static size band is exact-friendly, so a heuristic sampler is worth trying.

- Caveat: 1 explicit swaps can scramble bit positions; track bit order carefully.
- Caveat: Exact statevector is simpler for this size; use MPS only as a cross-check.

**Tensor Network Operator midpoint contraction**: usable fit, score 64/100

- Sparse or structured entangling connectivity favors midpoint TNO contraction.
- Repeated two-qubit pairs exist; max repetition is 4, which can indicate inverse blocks.

- Caveat: 1 swaps is low, but still weakens the no-permutation assumption.

**MPO iterative cancellation with unswapping**: poor fit, score 0/100

- 1 explicit swaps give the unswapping path concrete permutation evidence.

- Caveat: This is small enough that MPO unswapping is likely overkill.
- Caveat: The circuit is small enough that simpler simulation should come first.

### challenge-104_49.qasm

- Static band: `hard or very-hard`
- Difficulty group: `very_hard`
- Features: q=104, ops=26361, depth~1095, entanglers=5406, density=0.4240, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: MPO iterative cancellation with unswapping

Suggested next steps for `mpo_unswapping`:

- Split the circuit near the midpoint and absorb left/right layers into a central MPO.
- When bond growth spikes, greedily test nearest-neighbor swaps and keep swaps that reduce MPO size.
- Use the resulting MPO/MPS to sample or extract per-qubit marginals for candidate bitstrings.

**MPO iterative cancellation with unswapping**: strong fit, score 100/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 26361 operations is large enough to justify cancellation plus unswapping.
- Moderate-to-dense connectivity could still benefit from adaptive rewiring.
- A full-width leading one-qubit prefix is a strong obfuscation signal.

**Tensor Network Operator midpoint contraction**: poor fit, score 29/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Moderate graph density keeps TNO plausible if bond growth stays bounded.
- Repeated two-qubit pairs exist; max repetition is 6, which can indicate inverse blocks.

- Caveat: A full-width leading one-qubit dressing layer looks like heavier obfuscation.
- Caveat: The circuit is large enough that TNO compression needs careful cutoff/bond tuning.
- Caveat: Very-hard instances usually need permutation-aware cancellation, not plain TNO alone.

**Low-bond MPS with bitstring distillation**: poor fit, score 0/100

- The entangling graph is not too dense, so low bond dimensions are more plausible.

- Caveat: 104 qubits may still be possible, but shot-based MPS gets expensive.
- Caveat: 26361 operations makes repeated MPS shots slow.
- Caveat: The problem is labeled very-hard; low-bond MPS is unlikely to resolve the peak by itself.

### challenge-48_42.qasm

- Static band: `obfuscation-heavy`
- Difficulty group: `very_hard`
- Features: q=48, ops=20733, depth~1682, entanglers=4221, density=0.9504, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: MPO iterative cancellation with unswapping

Suggested next steps for `mpo_unswapping`:

- Split the circuit near the midpoint and absorb left/right layers into a central MPO.
- When bond growth spikes, greedily test nearest-neighbor swaps and keep swaps that reduce MPO size.
- Use the resulting MPO/MPS to sample or extract per-qubit marginals for candidate bitstrings.

**MPO iterative cancellation with unswapping**: strong fit, score 100/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 20733 operations is large enough to justify cancellation plus unswapping.
- Dense entangling connectivity suggests hidden permutation/ordering trouble.
- A full-width leading one-qubit prefix is a strong obfuscation signal.

**Tensor Network Operator midpoint contraction**: poor fit, score 4/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Repeated two-qubit pairs exist; max repetition is 7, which can indicate inverse blocks.

- Caveat: Dense all-to-all-like connectivity is a bad sign for plain TNO contraction.
- Caveat: A full-width leading one-qubit dressing layer looks like heavier obfuscation.
- Caveat: The circuit is large enough that TNO compression needs careful cutoff/bond tuning.

**Low-bond MPS with bitstring distillation**: poor fit, score 0/100

- 48 qubits is inside the practical range for MPS trials.

- Caveat: 20733 operations makes repeated MPS shots slow.
- Caveat: Dense entangling connectivity can inflate MPS bond dimension.
- Caveat: The problem is labeled very-hard; low-bond MPS is unlikely to resolve the peak by itself.

### challenge-56_43.qasm

- Static band: `obfuscation-heavy`
- Difficulty group: `very_hard`
- Features: q=56, ops=23004, depth~1582, entanglers=4684, density=0.8792, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: MPO iterative cancellation with unswapping

Suggested next steps for `mpo_unswapping`:

- Split the circuit near the midpoint and absorb left/right layers into a central MPO.
- When bond growth spikes, greedily test nearest-neighbor swaps and keep swaps that reduce MPO size.
- Use the resulting MPO/MPS to sample or extract per-qubit marginals for candidate bitstrings.

**MPO iterative cancellation with unswapping**: strong fit, score 100/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 23004 operations is large enough to justify cancellation plus unswapping.
- Dense entangling connectivity suggests hidden permutation/ordering trouble.
- A full-width leading one-qubit prefix is a strong obfuscation signal.

**Tensor Network Operator midpoint contraction**: poor fit, score 4/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Repeated two-qubit pairs exist; max repetition is 7, which can indicate inverse blocks.

- Caveat: Dense all-to-all-like connectivity is a bad sign for plain TNO contraction.
- Caveat: A full-width leading one-qubit dressing layer looks like heavier obfuscation.
- Caveat: The circuit is large enough that TNO compression needs careful cutoff/bond tuning.

**Low-bond MPS with bitstring distillation**: poor fit, score 0/100

- 56 qubits is inside the practical range for MPS trials.

- Caveat: 23004 operations makes repeated MPS shots slow.
- Caveat: Dense entangling connectivity can inflate MPS bond dimension.
- Caveat: The problem is labeled very-hard; low-bond MPS is unlikely to resolve the peak by itself.

### challenge-64_44.qasm

- Static band: `obfuscation-heavy`
- Difficulty group: `very_hard`
- Features: q=64, ops=28787, depth~1782, entanglers=5844, density=0.8646, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: MPO iterative cancellation with unswapping

Suggested next steps for `mpo_unswapping`:

- Split the circuit near the midpoint and absorb left/right layers into a central MPO.
- When bond growth spikes, greedily test nearest-neighbor swaps and keep swaps that reduce MPO size.
- Use the resulting MPO/MPS to sample or extract per-qubit marginals for candidate bitstrings.

**MPO iterative cancellation with unswapping**: strong fit, score 100/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 28787 operations is large enough to justify cancellation plus unswapping.
- Dense entangling connectivity suggests hidden permutation/ordering trouble.
- A full-width leading one-qubit prefix is a strong obfuscation signal.

**Tensor Network Operator midpoint contraction**: poor fit, score 4/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Repeated two-qubit pairs exist; max repetition is 7, which can indicate inverse blocks.

- Caveat: Dense all-to-all-like connectivity is a bad sign for plain TNO contraction.
- Caveat: A full-width leading one-qubit dressing layer looks like heavier obfuscation.
- Caveat: The circuit is large enough that TNO compression needs careful cutoff/bond tuning.

**Low-bond MPS with bitstring distillation**: poor fit, score 0/100

- 64 qubits is inside the practical range for MPS trials.

- Caveat: 28787 operations makes repeated MPS shots slow.
- Caveat: Dense entangling connectivity can inflate MPS bond dimension.
- Caveat: The problem is labeled very-hard; low-bond MPS is unlikely to resolve the peak by itself.

### challenge-72_45.qasm

- Static band: `obfuscation-heavy`
- Difficulty group: `very_hard`
- Features: q=72, ops=28777, depth~1636, entanglers=5852, density=0.7559, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: MPO iterative cancellation with unswapping

Suggested next steps for `mpo_unswapping`:

- Split the circuit near the midpoint and absorb left/right layers into a central MPO.
- When bond growth spikes, greedily test nearest-neighbor swaps and keep swaps that reduce MPO size.
- Use the resulting MPO/MPS to sample or extract per-qubit marginals for candidate bitstrings.

**MPO iterative cancellation with unswapping**: strong fit, score 100/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 28777 operations is large enough to justify cancellation plus unswapping.
- Dense entangling connectivity suggests hidden permutation/ordering trouble.
- A full-width leading one-qubit prefix is a strong obfuscation signal.

**Tensor Network Operator midpoint contraction**: poor fit, score 5/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Repeated two-qubit pairs exist; max repetition is 8, which can indicate inverse blocks.

- Caveat: Dense all-to-all-like connectivity is a bad sign for plain TNO contraction.
- Caveat: A full-width leading one-qubit dressing layer looks like heavier obfuscation.
- Caveat: The circuit is large enough that TNO compression needs careful cutoff/bond tuning.

**Low-bond MPS with bitstring distillation**: poor fit, score 0/100

- Caveat: 72 qubits may still be possible, but shot-based MPS gets expensive.
- Caveat: 28777 operations makes repeated MPS shots slow.
- Caveat: Dense entangling connectivity can inflate MPS bond dimension.

### challenge-80_46.qasm

- Static band: `obfuscation-heavy`
- Difficulty group: `very_hard`
- Features: q=80, ops=34586, depth~1702, entanglers=7030, density=0.7475, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: MPO iterative cancellation with unswapping

Suggested next steps for `mpo_unswapping`:

- Split the circuit near the midpoint and absorb left/right layers into a central MPO.
- When bond growth spikes, greedily test nearest-neighbor swaps and keep swaps that reduce MPO size.
- Use the resulting MPO/MPS to sample or extract per-qubit marginals for candidate bitstrings.

**MPO iterative cancellation with unswapping**: strong fit, score 100/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 34586 operations is large enough to justify cancellation plus unswapping.
- Dense entangling connectivity suggests hidden permutation/ordering trouble.
- A full-width leading one-qubit prefix is a strong obfuscation signal.

**Tensor Network Operator midpoint contraction**: poor fit, score 5/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Repeated two-qubit pairs exist; max repetition is 8, which can indicate inverse blocks.

- Caveat: Dense all-to-all-like connectivity is a bad sign for plain TNO contraction.
- Caveat: A full-width leading one-qubit dressing layer looks like heavier obfuscation.
- Caveat: The circuit is large enough that TNO compression needs careful cutoff/bond tuning.

**Low-bond MPS with bitstring distillation**: poor fit, score 0/100

- Caveat: 80 qubits may still be possible, but shot-based MPS gets expensive.
- Caveat: 34586 operations makes repeated MPS shots slow.
- Caveat: Dense entangling connectivity can inflate MPS bond dimension.

### challenge-88_47.qasm

- Static band: `obfuscation-heavy`
- Difficulty group: `very_hard`
- Features: q=88, ops=37660, depth~1708, entanglers=7654, density=0.6975, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: MPO iterative cancellation with unswapping

Suggested next steps for `mpo_unswapping`:

- Split the circuit near the midpoint and absorb left/right layers into a central MPO.
- When bond growth spikes, greedily test nearest-neighbor swaps and keep swaps that reduce MPO size.
- Use the resulting MPO/MPS to sample or extract per-qubit marginals for candidate bitstrings.

**MPO iterative cancellation with unswapping**: strong fit, score 100/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 37660 operations is large enough to justify cancellation plus unswapping.
- Dense entangling connectivity suggests hidden permutation/ordering trouble.
- A full-width leading one-qubit prefix is a strong obfuscation signal.

**Tensor Network Operator midpoint contraction**: poor fit, score 3/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Repeated two-qubit pairs exist; max repetition is 6, which can indicate inverse blocks.

- Caveat: Dense all-to-all-like connectivity is a bad sign for plain TNO contraction.
- Caveat: A full-width leading one-qubit dressing layer looks like heavier obfuscation.
- Caveat: The circuit is large enough that TNO compression needs careful cutoff/bond tuning.

**Low-bond MPS with bitstring distillation**: poor fit, score 0/100

- Caveat: 88 qubits may still be possible, but shot-based MPS gets expensive.
- Caveat: 37660 operations makes repeated MPS shots slow.
- Caveat: Dense entangling connectivity can inflate MPS bond dimension.

### challenge-96_48.qasm

- Static band: `hard or very-hard`
- Difficulty group: `very_hard`
- Features: q=96, ops=28703, depth~1215, entanglers=5866, density=0.5164, swaps=0
- Exact baseline: `not-first-choice` because Statevector memory scales as 2^n, so use it only for reduced circuits or validation.
- First action: MPO iterative cancellation with unswapping

Suggested next steps for `mpo_unswapping`:

- Split the circuit near the midpoint and absorb left/right layers into a central MPO.
- When bond growth spikes, greedily test nearest-neighbor swaps and keep swaps that reduce MPO size.
- Use the resulting MPO/MPS to sample or extract per-qubit marginals for candidate bitstrings.

**MPO iterative cancellation with unswapping**: strong fit, score 100/100

- Exact statevector is not a safe default, so a structure-aware method is needed.
- 28703 operations is large enough to justify cancellation plus unswapping.
- Moderate-to-dense connectivity could still benefit from adaptive rewiring.
- A full-width leading one-qubit prefix is a strong obfuscation signal.

**Tensor Network Operator midpoint contraction**: poor fit, score 29/100

- No explicit swaps were found, matching the cleaner TNO target case.
- Moderate graph density keeps TNO plausible if bond growth stays bounded.
- Repeated two-qubit pairs exist; max repetition is 6, which can indicate inverse blocks.

- Caveat: A full-width leading one-qubit dressing layer looks like heavier obfuscation.
- Caveat: The circuit is large enough that TNO compression needs careful cutoff/bond tuning.
- Caveat: Very-hard instances usually need permutation-aware cancellation, not plain TNO alone.

**Low-bond MPS with bitstring distillation**: poor fit, score 0/100

- Caveat: 96 qubits may still be possible, but shot-based MPS gets expensive.
- Caveat: 28703 operations makes repeated MPS shots slow.
- Caveat: Dense entangling connectivity can inflate MPS bond dimension.
