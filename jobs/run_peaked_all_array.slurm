#!/bin/bash
#SBATCH --job-name=peaked_all
#SBATCH --partition=interruptible_gpu
#SBATCH --constraint=a100_80g
#SBATCH --gres=gpu:1
#SBATCH --array=0-48%49
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

QASM_PATH="$(
  .venv/bin/python - "$SLURM_ARRAY_TASK_ID" <<'PY'
import sys
from pathlib import Path

idx = int(sys.argv[1])
paths = sorted(Path("challenges").glob("*/*.qasm"), key=lambda p: (p.parent.name, p.name))
if idx < 0 or idx >= len(paths):
    raise SystemExit(f"array index {idx} out of range for {len(paths)} challenge files")
print(paths[idx])
PY
)"

srun .venv/bin/python jobs/peaked_sim_runner.py \
  --qasm "$QASM_PATH" \
  --out-dir outputs/peaked_circuit_sim_all \
  --backend auto \
  --max-bond 512 \
  --cutoff 0.002 \
  --unswap-threshold 1000000 \
  --early-stopping-gates -1 \
  --center-ratio 0.5 \
  --max-its 10 \
  --rewire-trials 64 \
  --seed 123 \
  --hows both left right \
  --figure-note "full 49-circuit sweep after 3-circuit pilot; A100 80GB Slurm array capped by total tasks only, 49*16=784 CPUs max; exact method/params/shims printed on this figure"
