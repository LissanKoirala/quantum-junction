#!/bin/bash
#SBATCH --job-name=peaked_retry
#SBATCH --partition=interruptible_gpu
#SBATCH --constraint=a100_80g
#SBATCH --gres=gpu:1
#SBATCH --array=0-37%31
#SBATCH --cpus-per-task=16
#SBATCH --mem=80G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/peaked_circuit_sim_all/logs/%x-%A_%a.out
#SBATCH --error=outputs/peaked_circuit_sim_all/logs/%x-%A_%a.err

set -euo pipefail

ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
cd "$ROOT"

source .venv/bin/activate

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MPLBACKEND=Agg

ROW="$(
  .venv/bin/python - "$SLURM_ARRAY_TASK_ID" <<'PY'
import csv
import sys
from pathlib import Path

idx = int(sys.argv[1])
rows = list(csv.DictReader(Path("outputs/peaked_circuit_sim_all/retry_manifest.tsv").open(), delimiter="\t"))
if idx < 0 or idx >= len(rows):
    raise SystemExit(f"array index {idx} out of range for retry manifest with {len(rows)} rows")
row = rows[idx]
print("\t".join([row["qasm"], row["challenge"], row["reason"]]))
PY
)"

IFS=$'\t' read -r QASM_PATH CHALLENGE_LABEL RETRY_REASON <<< "$ROW"

MAX_BOND=512
CUTOFF=0.002
MAX_ITS=10
REWIRE_TRIALS=64
FIGURE_NOTE="resume retry for incomplete/cancelled full sweep; 31*16=496 retry CPUs, combined with live tree jobs stays under 1000 CPUs; exact method/params/shims printed on this figure"

if [[ "$RETRY_REASON" == *"strict"* ]]; then
  MAX_BOND=1024
  CUTOFF=0.001
  MAX_ITS=20
  REWIRE_TRIALS=128
  FIGURE_NOTE="strict rerun for known 1-bit miss ${CHALLENGE_LABEL}; max_bond=1024 cutoff=0.001 max_its=20 rewire_trials=128; exact method/params/shims printed on this figure"
fi

srun .venv/bin/python jobs/peaked_sim_runner.py \
  --qasm "$QASM_PATH" \
  --out-dir outputs/peaked_circuit_sim_all \
  --backend auto \
  --max-bond "$MAX_BOND" \
  --cutoff "$CUTOFF" \
  --unswap-threshold 1000000 \
  --early-stopping-gates -1 \
  --center-ratio 0.5 \
  --max-its "$MAX_ITS" \
  --rewire-trials "$REWIRE_TRIALS" \
  --seed 123 \
  --hows both left right \
  --figure-note "$FIGURE_NOTE"
