#!/usr/bin/env bash
#SBATCH --job-name=qj-mps-pilot
#SBATCH --partition=interruptible_cpu
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --array=1-36%36
#SBATCH --output=agent_work/mps_distill/logs/%x-%A_%a.out

set -euo pipefail

cd /cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export NUMEXPR_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"

.venv/bin/python agent_work/mps_distill/scripts/run_mps_trial.py \
  --config-file agent_work/mps_distill/configs/pilot_easy_hard.jsonl \
  --task-id "${SLURM_ARRAY_TASK_ID}" \
  --out-dir agent_work/mps_distill/results \
  --max-top-counts 200
