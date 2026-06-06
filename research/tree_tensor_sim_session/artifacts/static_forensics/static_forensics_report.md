# Static QASM Forensics

Generated: 2026-06-05T20:29:22.597300+00:00
Files analyzed: 49
Total gates parsed: 288696
Operation sets observed: cx,rx,rz, cx,rx,rz,swap
Total operations: {'rx': 101833, 'rz': 116235, 'cx': 70521, 'swap': 107}

## Difficulty summary

| difficulty | files | qubits | gates mean | rx mean | rz mean | cx mean | swaps total | noisy angle frac | graph density mean | leading 1q gates mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| very easy | 10 | 8.000000-64.000000 | 420.4 | 141.2 | 149.7 | 127.1 | 24 | 0.095 | 0.149 | 19.3 |
| easy | 16 | 8.000000-64.000000 | 1063.0 | 315.7 | 347.2 | 397.3 | 44 | 0.064 | 0.203 | 16.9 |
| moderate | 8 | 8.000000-64.000000 | 1713.1 | 447.2 | 560.1 | 701.8 | 32 | 0.034 | 0.495 | 8.5 |
| hard | 7 | 40.000000-64.000000 | 3595.4 | 813.7 | 1249.0 | 1531.7 | 7 | 0.045 | 0.369 | 22.0 |
| very_hard | 8 | 48.000000-104.000000 | 28576.4 | 10762.0 | 11994.8 | 5819.6 | 0 | 0.096 | 0.729 | 159.0 |

## Structural observations

- Every file uses only `cx, rx, rz, swap` gates; there are no measurements, barriers, H/S/T, or parameterized two-qubit rotations.
- `swap` is sparse: 25 files contain swaps and 24 contain none. Total swaps across the full set: 107.
- The entangling graph is connected in 32/49 files. Very small files can be disconnected or weakly connected, but moderate through very_hard are generally fully connected.
- The non-fraction angle bucket, defined as farther than 1e-2 from the nearest pi fraction with denominator <= 16, is {'very easy': '0.09453420', 'easy': '0.06354294', 'moderate': '0.03375109', 'hard': '0.04543251', 'very_hard': '0.09588364'} by difficulty.
- Strict pi remnants, counting symbolic pi plus numeric exact/very-close pi fractions, are much rarer in very_hard: very easy 32.2%, easy 56.3%, moderate 70.1%, hard 65.7%, very_hard 1.1%.
- Very_hard is dominated by loose near-grid numeric angles: 87.7% are within 1e-2 of a denominator <= 16 pi fraction, but only 1.1% are strict symbolic/exact/very-close pi fractions.
- The very_hard files have large dense RX/RZ prefixes before the first entangler; this looks like a distinct obfuscation pass rather than just scaled-up easy circuits.
- Repeated undirected CX pairs are common, supporting an inverse-composition/cancellation family rather than arbitrary one-pass random circuits.

## Leading single-qubit prefixes

- challenges/very_hard/challenge-104_49.qasm: q=104, leading one-qubit gates=211, greedy leading layers=2, first ops=RRRRRRRRRRRRRRRRRRRR
- challenges/very_hard/challenge-96_48.qasm: q=96, leading one-qubit gates=197, greedy leading layers=2, first ops=RRRRRRRRRRRRRRRRRRRR
- challenges/very_hard/challenge-80_46.qasm: q=80, leading one-qubit gates=176, greedy leading layers=2, first ops=RRRRRRRRRRRRRRRRRRRR
- challenges/very_hard/challenge-72_45.qasm: q=72, leading one-qubit gates=166, greedy leading layers=2, first ops=RRRRRRRRRRRRRRRRRRRR
- challenges/very_hard/challenge-88_47.qasm: q=88, leading one-qubit gates=142, greedy leading layers=1, first ops=RRRRRRRRRRRRRRRRRRRR
- challenges/very_hard/challenge-64_44.qasm: q=64, leading one-qubit gates=140, greedy leading layers=2, first ops=RRRRRRRRRRRRRRRRRRRR
- challenges/very_hard/challenge-48_42.qasm: q=48, leading one-qubit gates=125, greedy leading layers=2, first ops=RRRRRRRRRRRRRRRRRRRR
- challenges/very_hard/challenge-56_43.qasm: q=56, leading one-qubit gates=115, greedy leading layers=2, first ops=RRRRRRRRRRRRRRRRRRRR

## Highest pair repetitions

- challenges/moderate/challenge-8_27.qasm: max pair repetitions=19, repeated pairs=25, top pairs=1-2:19;3-4:13;2-5:11;0-4:11;3-7:11;4-5:10;2-7:10;3-5:9
- challenges/moderate/challenge-16_28.qasm: max pair repetitions=18, repeated pairs=106, top pairs=8-11:18;7-12:16;5-12:16;11-14:15;9-14:14;2-5:13;6-9:12;11-12:12
- challenges/moderate/challenge-24_29.qasm: max pair repetitions=17, repeated pairs=232, top pairs=9-14:17;1-10:15;17-22:14;5-22:14;3-8:13;21-22:12;8-19:12;0-21:12
- challenges/easy/challenge-24_13.qasm: max pair repetitions=13, repeated pairs=57, top pairs=2-22:13;7-20:10;13-19:10;1-2:8;0-12:6;15-20:6;12-16:6;8-11:5
- challenges/moderate/challenge-32_30.qasm: max pair repetitions=13, repeated pairs=206, top pairs=5-8:13;2-4:10;11-21:10;7-16:10;15-20:10;3-28:9;0-21:9;7-31:9
- challenges/moderate/challenge-48_31.qasm: max pair repetitions=12, repeated pairs=154, top pairs=2-42:12;5-11:8;9-11:8;26-47:7;2-9:7;2-19:7;3-41:6;3-42:6
- challenges/moderate/challenge-48_32.qasm: max pair repetitions=12, repeated pairs=195, top pairs=2-38:12;24-36:8;11-21:8;8-41:8;13-32:8;17-33:7;39-41:7;10-16:6
- challenges/hard/challenge-56_38.qasm: max pair repetitions=12, repeated pairs=717, top pairs=18-23:12;3-32:12;7-39:11;37-50:11;5-32:11;8-55:11;45-51:10;46-53:10

## Operation-sequence similarity

The table below is based only on operation 5-gram cosine similarity, not qubit indices or angles.

| diff A | diff B | pairs | mean | median | max |
|---|---|---:|---:|---:|---:|
| very easy | very easy | 45 | 0.564 | 0.568 | 0.843 |
| very easy | easy | 160 | 0.614 | 0.606 | 0.897 |
| very easy | moderate | 80 | 0.616 | 0.612 | 0.875 |
| very easy | hard | 70 | 0.595 | 0.588 | 0.850 |
| very easy | very_hard | 80 | 0.542 | 0.531 | 0.907 |
| easy | easy | 120 | 0.736 | 0.782 | 0.921 |
| easy | moderate | 128 | 0.748 | 0.773 | 0.923 |
| easy | hard | 112 | 0.730 | 0.754 | 0.890 |
| easy | very_hard | 128 | 0.504 | 0.496 | 0.928 |
| moderate | moderate | 28 | 0.799 | 0.817 | 0.955 |
| moderate | hard | 56 | 0.836 | 0.842 | 0.959 |
| moderate | very_hard | 64 | 0.454 | 0.459 | 0.540 |
| hard | hard | 21 | 0.895 | 0.904 | 0.957 |
| hard | very_hard | 56 | 0.453 | 0.477 | 0.516 |
| very_hard | very_hard | 28 | 0.970 | 0.991 | 0.996 |

## Cracking hints from static structure

- Treat symbolic and near-pi RX angles as high-value clues, especially on very easy/easy files where many RX(pi) remnants survive.
- Track swaps explicitly before reading candidate bits; final Qiskit bitstrings are high-index to low-index, so q0 is the right-most bit.
- Repeated opposite-direction CX pairs and repeated undirected pairs are plausible cancellation targets. A symbolic pass that merges adjacent RX/RZ and cancels CX pairs after commuting one-qubit gates should be cheap before simulation.
- For very_hard, start by peeling complete leading/trailing RX/RZ layers and looking for inverse blocks or pair-repetition symmetry. The dense all-qubit prefixes are not random measurements; they are static unitary dressing.
- RZ-only layers on computational basis states are invisible until conjugated by RX/CX structure; for peak extraction, prioritize RX parity after reducing identity-like blocks.

## Output files

- `per_file_metrics.csv`
- `difficulty_summary.csv`
- `angle_bucket_summary.csv`
- `angle_precision_summary.csv`
- `pair_repetitions.csv`
- `operation_similarity.csv`
- `operation_similarity_by_difficulty.csv`
- `qasm_static_features.json`
