# peaked-circuit-simulation pilot

Pilot run only. I did not submit the full 49-circuit sweep after this pilot.

## Code changes

- Added `jobs/peaked_sim_runner.py`.
  - Uses the bundled `peaked-circuit-simulation/unswap.py`, `circuit_mpo.py`, and `utils.py`.
  - Does not edit the bundled simulation source files.
  - Applies runtime compatibility shims for Qiskit 2 bit indexing, bounded SabreSwap routing, measure-safe `mpo_to_mps`, and canonical one-site marginal extraction.
  - Writes per-circuit JSON, stats JSONL, and annotated PNG figures.
  - Figures include the exact method, parameters, shims, and candidate bitstrings directly on the image.
- Added `jobs/run_peaked_pilot_array.slurm`.
  - Pilot Slurm array for challenge IDs `1`, `11`, and `27` on `interruptible_gpu`.
- Added `jobs/run_peaked_pilot_retry27_cpu.slurm`.
  - CPU retry for challenge `27`, because the first GPU attempt landed on an unsupported Blackwell MIG GPU for the installed PyTorch CUDA build.

## Simulation

Method: bundled `peaked-circuit-simulation` MPO compression plus unswapping, followed by MPO-to-MPS conversion and one-qubit marginal extraction.

Parameters:

- `backend=auto`
- `max_bond=512`
- `cutoff=0.002`
- `unswap_threshold=1000000`
- `early_stopping_gates=-1`
- `center_ratio=0.5`
- `max_its=10`
- `rewire_trials=64`
- `seed=123`
- `hows=(both, left, right)`

## Pilot Results

| Challenge | Backend | Status | Candidate in Qiskit/counts order | Image |
| --- | --- | --- | --- | --- |
| `8_1` | `auto->cuda` on A100 | ok | `10101101` | `outputs/peaked_circuit_sim_pilot/images/challenge-8_1.peaked_mpo_mps.png` |
| `8_11` | `auto->cuda` on A100 | ok | `01001110` | `outputs/peaked_circuit_sim_pilot/images/challenge-8_11.peaked_mpo_mps.png` |
| `8_27` | `auto->numpy` on CPU retry | ok | `11001001` | `outputs/peaked_circuit_sim_pilot/images/challenge-8_27.peaked_mpo_mps.png` |

## Output Files

- JSON: `outputs/peaked_circuit_sim_pilot/json/`
- Images: `outputs/peaked_circuit_sim_pilot/images/`
- MPO stats JSONL: `outputs/peaked_circuit_sim_pilot/stats/`
- Slurm logs: `outputs/peaked_circuit_sim_pilot/logs/`
