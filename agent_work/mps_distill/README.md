# Qiskit Aer MPS sampling/distillation

Artifacts in this directory are isolated from shared source files.

## Pilot design

The first pass samples three easy circuits and three hard circuits with Qiskit Aer
`method="matrix_product_state"`.

- Circuits: `easy/challenge-8_11`, `easy/challenge-16_12`, `easy/challenge-40_16`,
  `hard/challenge-40_35`, `hard/challenge-48_36`, `hard/challenge-64_41`
- Settings: `(shots=512, bond_dim=16)`, `(shots=2048, bond_dim=32)`,
  `(shots=4096, bond_dim=64)`
- Seeds: `101`, `202`

The summarizer treats Qiskit count keys as submission-order bitstrings: the
right-most bit is `q0`.

## Commands

Generate configs:

```bash
.venv/bin/python agent_work/mps_distill/scripts/generate_configs.py
```

Submit the pilot array:

```bash
sbatch agent_work/mps_distill/jobs/mps_pilot_array.slurm
```

Summarize completed trials:

```bash
.venv/bin/python agent_work/mps_distill/scripts/summarize_mps_results.py
```
