#!/bin/bash
#SBATCH --job-name=opus-dbg
#SBATCH --partition=interruptible_cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=agent_work/opus_combined/logs/%x-%j.out
#SBATCH --error=agent_work/opus_combined/logs/%x-%j.err
set -euo pipefail
ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
cd "$ROOT"; source .venv/bin/activate
export OMP_NUM_THREADS=16 OPENBLAS_NUM_THREADS=16 MKL_NUM_THREADS=16 PYTHONUNBUFFERED=1
srun .venv/bin/python agent_work/opus_combined/dbg_full.py
