#!/bin/bash
#SBATCH --job-name=opus-crack-gpu
#SBATCH --partition=interruptible_gpu
#SBATCH --constraint=a100_80g
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=120G
#SBATCH --time=1-00:00:00
#SBATCH --output=agent_work/opus_combined/logs/%x-%A_%a.out
#SBATCH --error=agent_work/opus_combined/logs/%x-%A_%a.err

# Combined cracker (Snap -> Consolidate -> MPO unswap-to-convergence -> Z-sign readout)
# GPU path on A100-80GB (NOT Blackwell sm_120, which the installed torch cannot use).
# Usage: sbatch --array=0-N%K agent_work/opus_combined/jobs/crack_gpu.slurm <config.jsonl>

set -euo pipefail
ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
cd "$ROOT"
mkdir -p agent_work/opus_combined/logs
source .venv/bin/activate

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export PYTHONUNBUFFERED=1

CFG="${1:?usage: sbatch ... crack_gpu.slurm <config.jsonl>}"
echo "host=$(hostname) gpu=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo none)"
echo "config=$CFG index=${SLURM_ARRAY_TASK_ID}"

srun .venv/bin/python agent_work/opus_combined/run_one.py "$CFG" "${SLURM_ARRAY_TASK_ID}"
