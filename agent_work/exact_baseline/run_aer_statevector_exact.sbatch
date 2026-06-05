#!/bin/bash
#SBATCH --job-name=exact_aer_sv
#SBATCH --partition=interruptible_cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=60G
#SBATCH --time=02:00:00
#SBATCH --output=agent_work/exact_baseline/logs/%x-%j.out
#SBATCH --error=agent_work/exact_baseline/logs/%x-%j.err

set -euo pipefail

cd /cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction
source .venv/bin/activate

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export NUMEXPR_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export SV_CHUNK_ELEMS=1048576

python agent_work/exact_baseline/aer_statevector_peaks.py \
  --max-qubits 28 \
  --topk 8 \
  --output-dir agent_work/exact_baseline
