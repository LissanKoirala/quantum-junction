# peaked-circuit-simulation full sweep

Submitted Slurm array job: `34607501`

This is the full 49-circuit sweep using the same runner and algorithmic parameters verified in the pilot.

## Slurm Resources

- Partition: `interruptible_gpu`
- Constraint: `a100_80g`
- Array: `0-48%49`
- GPU: `1` per task
- CPU: `16` per task
- Memory: `80G` per task
- Wall time: `1-00:00:00`
- Max concurrent tasks: `49`
- Max possible CPU allocation: `49 * 16 = 784`, below the requested `1000` CPU cap

Note: the job was originally submitted with `%5`, then the live Slurm array throttle was raised to `49` with `scontrol`. Slurm shows `ArrayTaskThrottle=49` for the remaining tasks.

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

## Output Files

- Manifest: `outputs/peaked_circuit_sim_all/manifest.tsv`
- JSON: `outputs/peaked_circuit_sim_all/json/`
- Images: `outputs/peaked_circuit_sim_all/images/`
- MPO stats JSONL: `outputs/peaked_circuit_sim_all/stats/`
- Slurm logs: `outputs/peaked_circuit_sim_all/logs/`
- Running log: `outputs/peaked_circuit_sim_all/RUN_LOG.md`
- Monitor status: `outputs/peaked_circuit_sim_all/MONITOR_STATUS.json`
- Monitor final summary, once complete: `outputs/peaked_circuit_sim_all/MONITOR_FINAL.md`

Each figure has the method, parameters, runtime shims, and candidate bitstrings printed directly on the image.

## Monitor

- Monitor Slurm job: `34608329`
- Script: `jobs/monitor_peaked_all.slurm`
- Interval: `1800` seconds
- Resources: `1` CPU, `2G` RAM on `interruptible_cpu`
