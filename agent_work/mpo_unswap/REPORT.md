# Agent 5: MPO-unswapping feasibility

Date: 2026-06-05

## Environment

- Repo: `/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction`
- Python env: `.venv`
- Package versions from smoke jobs:
  - qiskit `2.4.1`
  - quimb `1.11.2`
  - qiskit-quimb `0.0.10`
  - torch `2.5.1+cu121`
  - numpy `2.2.6`
  - scipy `1.15.3`
- Slurm partition used: `interruptible_cpu`
- Shared source files were not modified.

## Challenge Size Snapshot

Stats are in `results/qasm_line_stats.txt`.

- Smallest smoke target: `challenges/very easy/challenge-8_1.qasm`
  - 8 qubits, 46 operation lines
  - ops: `rx=17`, `rz=14`, `cx=14`, `swap=1`
- Easy set:
  - 8 to 64 qubits
  - 117 to 1854 operation lines
  - 38 to 711 `cx/cz/swap` lines
- Hard set:
  - 40 to 64 qubits
  - 2783 to 5939 operation lines
  - 1145 to 2759 `cx/cz/swap` lines

## Smoke Tests

All jobs were submitted to `interruptible_cpu`.

| Job | Script | Result |
| --- | --- | --- |
| `34605743` | `scripts/smoke_raw.slurm` | Raw bundled code passed import, QASM load, layer iteration, rewiring, MPO creation, prefix absorption, direct `unswap`, and bounded `mpo_compress_unswap`. |
| `34605867` | `scripts/smoke_integrated_unswap_raw.slurm` | Raw bundled `mpo_compress_unswap` triggered integrated unswapping with `unswap_threshold=100`; max bond dropped from 4 to 2, but it returned early with many layers left. |
| `34605829` | `scripts/smoke_mps_raw.slurm` | Raw `mpo_to_mps` failed: `CircuitError: 'inverse() not implemented for measure.'` |
| `34605889` | `scripts/smoke_mps_compat.slurm` | Local-only compatibility patches passed compress -> MPO-to-MPS -> bitstring extraction. Predicted bitstring was `10101110`; this was a smoke result, not correctness validation. |

Representative resource use:

- Raw cold smoke: 51s elapsed, 4 CPUs, Slurm batch MaxRSS about 1.38 GB.
- Later warm-cache smoke jobs: 6s elapsed, 4 CPUs, Slurm batch MaxRSS about 305 MB.
- Importing bundled modules dominates cold startup because `utils.py` imports Torch unconditionally.

## Findings

The core MPO construction, MPO application, swap selection, and unswapping routines do run with Qiskit `2.4.1` and Quimb `1.11.2` on the smallest QASM. The bundled code is not end-to-end usable as-is for producing samples/bitstrings from these challenge QASM files because the downstream MPS conversion and bitstring extraction paths hit current API/logic issues.

Required fixes before larger runs:

1. Count challenge gates, not only Qiskit `unitary`.
   - In `peaked-circuit-simulation/unswap.py`, `T_U`, `T_UL`, `T_UR`, and per-layer `new_us` count only `count_ops()["unitary"]`.
   - These QASM files use `rx/rz/cx/swap`, so all progress counters are zero.
   - Consequence: integrated unswapping can immediately satisfy `(T_U - total_u_consumed) <= early_stopping_gates` and return with many layers left.
   - Fix: count all quantum operations except `barrier` and `measure`, or track consumed layers directly.

2. Strip measurement/barrier layers before inverting leftover left layers in `mpo_to_mps`.
   - Raw failure occurs at `merge_layers(layers_left).inverse()` because `layers_left` includes internally added `measure_all()` layers.
   - Fix: keep measurement layers only for final permutation extraction; do not include them in circuits passed to `.inverse()` or qiskit-quimb.

3. Update bitstring extraction for Quimb `1.11`.
   - `utils.extract_bitstring` calls `tne.local_expectation(...)`, which reaches the renamed `mps.partial_trace` path.
   - Fix for MPS: use `local_expectation_canonical(Pi0, where=i, normalized=True)` when available, or update to Quimb's current reduced-density API.

4. Remove private Qiskit bit-field usage.
   - `utils.merge_gates` and `unswap.mpo_to_mps` use `_index` / `_register`.
   - It happens to work with Qiskit `2.4.1`, but it is private API.
   - Fix: pass the source circuit into helpers and use `source_circuit.find_bit(bit).index`.

5. Make Torch optional for CPU MPO runs.
   - `utils.py` imports Torch at module import even when `to_backend=None`.
   - Fix: move Torch import inside CUDA-specific functions or guard it. This reduces CPU startup overhead and avoids CUDA-library surprises on CPU nodes.

6. Parameterize rewiring cost.
   - `rewire_layers` hardcodes `SabreSwap(..., trials=10000)`.
   - This is fine for the tiny smoke, but should be a parameter for CPU array runs. Use low trials for canaries and higher trials only after validating scaling.

## Resource Estimate

The smoke test is too small to extrapolate linearly because MPO cost scales mainly with bond dimension, not just operation count. Still, the challenge sizes and README hardware note are enough to set conservative job bounds.

Easy circuits:

- Small/easy canaries, 8 to 24 qubits: 4 to 8 CPUs, 12 to 24 GB, 30 to 60 minutes.
- Larger easy circuits, 40 to 64 qubits and up to 1854 ops: 8 to 16 CPUs, 24 to 60 GB, 2 to 8 hours per parameter point.
- Try `max_bond` ladder `128, 256, 512, 1024`, with cutoff ladder `1e-4, 1e-5, 1e-6`.

Hard circuits:

- Hard set is 40 to 64 qubits and up to 5939 ops / 2759 two-qubit-or-swap gates.
- CPU should be treated as triage only. A single hard parameter point can plausibly take 12 to 24 hours and hit the `interruptible_cpu` memory ceiling if `max_bond >= 2048`.
- The bundled README says the intended MPO-unswapping target was single A100 80 GB, about 1 hour for a 56-qubit, 1917-gate all-to-all circuit. The hard set includes circuits with materially more operations than that.
- Recommended hard path: use CPU only to find low-bond feasibility and parameter ranges, then move serious hard/very-hard runs to a high-memory GPU node if available.

## Recommended Slurm Strategy

1. Patch the source in a private branch/copy, or apply equivalent runtime shims in job scripts.
2. Run canaries first:
   - `very easy/challenge-8_1.qasm`
   - `easy/challenge-8_11.qasm`
   - `easy/challenge-16_12.qasm`
   - one 40+ qubit easy circuit
3. Use arrays, not one 1000-CPU job:
   - one circuit/configuration per task
   - 4 to 16 CPUs per easy task
   - cap array concurrency to stay within the allowed interruptible CPU budget
4. Save per-layer stats JSON and logs for every run; stop a task if `max_bond`, `total_elems`, or wall time grows faster than expected.
5. For hard circuits, start with:
   - `--cpus-per-task=32`
   - `--mem=60G`
   - `--time=1-00:00:00`
   - low-bond/cutoff triage first, then escalate only if easy circuits show stable bonds.
6. Prioritize hard circuits from smallest to largest observed size:
   - `challenge-48_36`, `challenge-56_39`, `challenge-40_35`, `challenge-64_41`, `challenge-48_37`, `challenge-64_40`, `challenge-56_38`.

## Artifacts

- Harness: `scripts/smoke_mpo_unswap.py`
- Slurm wrappers: `scripts/*.slurm`
- Logs: `logs/`
- JSON results: `results/*.json`
- QASM line stats: `results/qasm_line_stats.txt`
