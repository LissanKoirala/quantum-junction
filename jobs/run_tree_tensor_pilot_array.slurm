#!/bin/bash
#SBATCH --job-name=tree_tensor_pilot
#SBATCH --partition=interruptible_gpu
#SBATCH --constraint=a100_80g
#SBATCH --gres=gpu:1
#SBATCH --array=0-4%3
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --output=outputs/tree_tensor_sim/pilot/logs/%x-%A_%a.out
#SBATCH --error=outputs/tree_tensor_sim/pilot/logs/%x-%A_%a.err

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
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export MPLBACKEND=Agg

mkdir -p outputs/tree_tensor_sim/pilot/{json,images,stats,logs}

IDS=(1 11 27 12 28)
CHALLENGE_ID="${IDS[$SLURM_ARRAY_TASK_ID]}"

srun "$VENV/bin/python" jobs/tree_tensor_runner.py \
  --challenge-id "$CHALLENGE_ID" \
  --out-dir outputs/tree_tensor_sim/pilot \
  --backend auto \
  --max-bond 512 \
  --cutoff 1e-7 \
  --gate-contract swap+split \
  --order-method weighted_spectral \
  --graph-ops cx swap \
  --recency-alpha 0.15 \
  --samples 2048 \
  --sample-top-k 12 \
  --seed 20260605 \
  --figure-note "canonical pilot: graph-derived weighted spectral qubit order plus maximum-spanning-tree metadata; Quimb CircuitMPS fallback, not Aer MPS or statevector"
