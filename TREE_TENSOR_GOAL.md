# Tree Tensor / Graph-Aware TN Goal Handoff

Use this file to start a fresh Codex thread for the next line of attack.

## Working Directory

Repository:

`/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction`

Environment:

- Use `.venv`.
- We are on a login node by default, so do not run heavy simulations directly.
- Submit work through Slurm.
- Prefer interruptible partitions.
- Keep large outputs under `outputs/`.

## Objective

Implement a separate tree tensor / graph-aware tensor-network simulation path for the challenge circuits.

The goal is to test whether a graph/tree ordering helps with the suspected nonlocal pairings and dense long-range CX structure that make plain MPS unstable on harder circuits.

Required workflow:

1. Inspect the installed Quimb/Qiskit APIs and choose the most practical tree/graph-aware implementation.
2. Keep this separate from the existing statevector, Aer MPS, and `peaked-circuit-simulation` MPO outputs.
3. Test on a small pilot set first.
4. Save JSON, logs, stats, and annotated figures.
5. If the pilot works, submit a full 49-circuit Slurm sweep.
6. Keep improving overnight if jobs finish/fail, but do not run heavy compute on the login node.

## Suggested Output Folder

Use a new folder:

`outputs/tree_tensor_sim/`

Suggested structure:

- `outputs/tree_tensor_sim/pilot/json/`
- `outputs/tree_tensor_sim/pilot/images/`
- `outputs/tree_tensor_sim/pilot/stats/`
- `outputs/tree_tensor_sim/pilot/logs/`
- `outputs/tree_tensor_sim/all/json/`
- `outputs/tree_tensor_sim/all/images/`
- `outputs/tree_tensor_sim/all/stats/`
- `outputs/tree_tensor_sim/all/logs/`

## Existing Context

The challenge QASM files are under:

`challenges/*/*.qasm`

There are 49 files.

Known exact/safe reference answers from earlier exact/statevector work:

| Challenge | Answer |
| --- | --- |
| `8_1` | `10101101` |
| `16_2` | `1010101011001000` |
| `24_3` | `011110010000101010001000` |
| `28_4` | `1111111000101010110110011111` |
| `8_11` | `01001110` |
| `16_12` | `1111000101101011` |
| `24_13` | `111110011111001011010001` |
| `8_27` | `11001001` |
| `16_28` | `1101001111011100` |
| `24_29` | `110100010111100001001001` |

Use these for pilot validation.

## Existing Analyses

Read these first:

- `agent_work/static_forensics/static_forensics_report.md`
- `agent_work/mps_distill/summaries/pilot_summary.md`
- `agent_work/mpo_unswap/REPORT.md`
- `agent_work/algebraic_simplify/NOTES.md`
- `outputs/peaked_circuit_sim_pilot/SUMMARY.md`
- `outputs/peaked_circuit_sim_all/SUMMARY.md`

Important observations:

- All QASM files use only `rx`, `rz`, `cx`, and sparse `swap`.
- Moderate/hard/very_hard circuits have dense and repeated long-range CX pairs.
- Very hard has no explicit swaps, very dense CX graphs, and large dense RX/RZ prefixes.
- Local algebraic simplification failed to expose the answer.
- Plain Aer MPS was stable on easy circuits but unstable on hard circuits.
- MPO/unswapping pilot recovered `8_1`, `8_11`, and `8_27`.

## Current Running Job To Be Aware Of

A separate full `peaked-circuit-simulation` MPO/MPS sweep was submitted as:

`34607501`

Script:

`jobs/run_peaked_all_array.slurm`

Outputs:

`outputs/peaked_circuit_sim_all/`

This is not the tree-tensor job. Do not overwrite it. It may still be running.

## Existing Runner Worth Reusing Patterns From

Look at:

`jobs/peaked_sim_runner.py`

It already implements useful reusable patterns:

- Challenge path resolution.
- JSON-safe output writing.
- Annotated figure generation with method and parameters printed directly on the PNG.
- CUDA architecture sanity checks.
- Slurm-friendly output layout.

Do not modify the existing `peaked-circuit-simulation` package unless truly necessary.

## Proposed Technical Approach

Start conservative. The first practical implementation does not need a full custom TTN state class if Quimb does not expose a convenient one.

Recommended path:

1. Build a weighted interaction graph from each circuit:
   - nodes = qubits
   - edge weights = repeated `cx`/`swap` interactions
   - optionally weight by recency or gate count
2. Derive a graph-aware qubit order or hierarchy:
   - try spectral ordering / reverse Cuthill-McKee / hierarchical clustering / greedy min-cut
   - save the chosen permutation/tree in JSON
3. Pilot a graph-aware tensor-network contraction strategy:
   - Either use Quimb circuit tensor network contraction with a contraction tree optimized for the graph.
   - Or use graph-derived qubit ordering as an improved MPS ordering if Quimb TTN APIs are not practical.
   - Prefer a real tree/graph contraction if possible, but do not block forever if the installed Quimb version does not support a clean TTN state workflow.
4. Extract per-qubit marginals or candidate bitstrings.
5. Compare pilot outputs against known answers.

Useful pilot circuits:

- `8_1`
- `8_11`
- `8_27`
- `16_12`
- `16_28`
- optionally `24_13`

## Figure Requirements

Every figure should include, directly on the image:

- method name
- whether it is a true TTN/tree contraction or graph-ordered MPS fallback
- graph/tree construction method
- all important parameters
- challenge path and difficulty
- raw candidate bitstring
- Qiskit/counts-order candidate bitstring
- validation result if known
- runtime/resource notes

## Slurm Requirements

Pilot first.

Suggested pilot:

- Partition: `interruptible_gpu` if using GPU; otherwise `interruptible_cpu`
- GPU cap: small pilot can use `%3`
- Full sweep cap: at most `%5` GPU tasks total, matching the previous resource cap
- Use A100-compatible GPUs when using PyTorch CUDA, ideally `--constraint=a100_80g`
- Avoid unsupported Blackwell MIG GPUs unless the installed PyTorch supports them

If full sweep is submitted, use a new script name such as:

`jobs/run_tree_tensor_all_array.slurm`

Do not reuse `jobs/run_peaked_all_array.slurm`.

## Deliverables

Create:

- `jobs/tree_tensor_runner.py`
- `jobs/run_tree_tensor_pilot_array.slurm`
- `jobs/run_tree_tensor_all_array.slurm` if pilot works
- `outputs/tree_tensor_sim/pilot/SUMMARY.md`
- `outputs/tree_tensor_sim/all/SUMMARY.md` if full sweep is submitted

The final summary should report:

- exact files changed
- exact Slurm job IDs
- exact parameters
- pilot validation results
- output paths
- whether the full sweep was submitted or held back

## Caution

The repo has unrelated unstaged deletions under `papers/sqd/`. Do not revert or stage them unless explicitly asked.
