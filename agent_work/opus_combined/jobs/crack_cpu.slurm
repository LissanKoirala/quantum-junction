#!/bin/bash
#SBATCH --job-name=opus-crack-cpu
#SBATCH --partition=interruptible_cpu
#SBATCH --cpus-per-task=64
#SBATCH --mem=480G
#SBATCH --time=1-00:00:00
#SBATCH --output=agent_work/opus_combined/logs/%x-%A_%a.out
#SBATCH --error=agent_work/opus_combined/logs/%x-%A_%a.err

# Combined cracker -- CPU fallback (no GPU; numpy backend).
# Usage: sbatch --array=0-N%K agent_work/opus_combined/jobs/crack_cpu.slurm <config.jsonl>

set -euo pipefail
ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
cd "$ROOT"
mkdir -p agent_work/opus_combined/logs
source .venv/bin/activate

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-64}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-64}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-64}"
export PYTHONUNBUFFERED=1

CFG="${1:?usage: sbatch ... crack_cpu.slurm <config.jsonl>}"
echo "host=$(hostname) index=${SLURM_ARRAY_TASK_ID}"

srun .venv/bin/python agent_work/opus_combined/run_one.py "$CFG" "${SLURM_ARRAY_TASK_ID}"
