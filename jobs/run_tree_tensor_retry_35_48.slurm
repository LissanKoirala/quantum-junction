#!/bin/bash
#SBATCH --job-name=tree_tensor_retry
#SBATCH --partition=interruptible_cpu
#SBATCH --array=35-48%6
#SBATCH --cpus-per-task=32
#SBATCH --mem=80G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/tree_tensor_sim/all/logs/%x-%A_%a.out
#SBATCH --error=outputs/tree_tensor_sim/all/logs/%x-%A_%a.err

set -euo pipefail

ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction-tree-tensor"
FALLBACK_ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
cd "$ROOT"

if [[ -d "$ROOT/.venv" ]]; then
  VENV="$ROOT/.venv"
else
  VENV="$FALLBACK_ROOT/.venv"
fi
source "$VENV/bin/activate"

export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-32}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-32}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-32}"
export MPLBACKEND=Agg

mkdir -p outputs/tree_tensor_sim/all/{json,images,stats,logs}

srun "$VENV/bin/python" jobs/tree_tensor_runner.py \
  --array-index "$SLURM_ARRAY_TASK_ID" \
  --out-dir outputs/tree_tensor_sim/all \
  --order-methods rcm spectral mincut greedy \
  --bond-dims 64 128 \
  --shots 8192 \
  --seed 20260605 \
  --mps-truncation-threshold 1e-10 \
  --exact-max-qubits 28 \
  --max-parallel-threads "${SLURM_CPUS_PER_TASK:-32}" \
  --figure-note "retry for indices 35-48 after runner CLI dispatch fix; graph/tree-order MPS fallback"
