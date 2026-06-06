# Exact Baseline Results

All exact statevector work was submitted to the `interruptible_cpu` Slurm partition. No 32+ qubit exact statevector simulations were run.

## Completed Exact Peaks

Bitstrings use Qiskit ordering: the right-most bit is `q0`.

| challenge | difficulty | qubits | peak bitstring | peak probability | second probability |
|---|---|---:|---|---:|---:|
| 8_1 | very easy | 8 | 10101101 | 0.912637847740 | 0.037911851288 |
| 16_2 | very easy | 16 | 1010101011001000 | 0.466969624218 | 0.097587044100 |
| 24_3 | very easy | 24 | 011110010000101010001000 | 0.723983742652 | 0.047092257354 |
| 28_4 | very easy | 28 | 1111111000101010110110011111 | 0.351111899387 | 0.073502765424 |
| 8_11 | easy | 8 | 01001110 | 0.545448075001 | 0.068683996816 |
| 16_12 | easy | 16 | 1111000101101011 | 0.466536732119 | 0.072964578998 |
| 24_13 | easy | 24 | 111110011111001011010001 | 0.591248286011 | 0.047168390082 |
| 8_27 | moderate | 8 | 11001001 | 0.287907338547 | 0.062694571104 |
| 16_28 | moderate | 16 | 1101001111011100 | 0.396205934803 | 0.023131119233 |
| 24_29 | moderate | 24 | 110100010111100001001001 | 0.390096637678 | 0.013436270065 |

## Slurm Jobs

| job id | script | status | purpose | logs |
|---:|---|---|---|---|
| 34605883 | `run_aer_statevector_exact.sbatch` | completed | exact Aer statevector for all <=28 qubit targets | `logs/exact_aer_sv-34605883.out`, `logs/exact_aer_sv-34605883.err` |
| 34605619 | `run_statevector_exact.sbatch` | canceled after Aer completed | slower Python `Statevector` cross-check; matched all overlapping results | `logs/exact_sv_baseline-34605619.out`, `logs/exact_sv_baseline-34605619.err` |

The complete result files are `peaks_exact.csv` and `peaks_exact.jsonl`. The Aer-specific originals are kept as `peaks_exact_aer.*`; the canceled cross-check output is kept as `peaks_exact_python_partial.*`.

## Feasibility

The exact statevector cutoff used here is 28 qubits. A complex128 statevector requires `16 * 2^n` bytes before simulator overhead: 28 qubits is 4 GiB, 31 qubits is 32 GiB, and 32 qubits is 64 GiB. Because `interruptible_cpu` nodes reported about 62 GB or higher, 32-qubit exact statevector is not a safe default target on this partition.

The gate set is arbitrary-angle `rx`, `rz`, plus `cx` and `swap`, so Clifford stabilizer simulation is not applicable. Exact MPS or tensor-network methods could be exact only if the induced bond dimensions stay modest; that was not assumed for this baseline.

## Peak Probability Pattern

Among the exactly solved circuits, peak probability generally drops with difficulty:

| difficulty | solved count | mean peak probability | min | max |
|---|---:|---:|---:|---:|
| very easy | 4 | 0.613675778499 | 0.351111899387 | 0.912637847740 |
| easy | 3 | 0.534411031043 | 0.466536732119 | 0.591248286011 |
| moderate | 3 | 0.358069970343 | 0.287907338547 | 0.396205934803 |

This matches the challenge description directionally: moderate instances have noticeably lower peaks than easy/very easy. Qubit count is not the only driver; for example, very easy 28 has a lower peak than very easy 24, while easy 24 has a higher peak than easy 16.
