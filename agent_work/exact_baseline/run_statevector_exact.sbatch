#!/bin/bash
#SBATCH --job-name=exact_sv_baseline
#SBATCH --partition=interruptible_cpu
#SBATCH --cpus-per-task=8
#SBATCH --mem=60G
#SBATCH --time=04:00:00
#SBATCH --output=agent_work/exact_baseline/logs/%x-%j.out
#SBATCH --error=agent_work/exact_baseline/logs/%x-%j.err

set -euo pipefail

cd /cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction
source .venv/bin/activate

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export NUMEXPR_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export SV_CHUNK_ELEMS=1048576

python agent_work/exact_baseline/analyze_challenges.py
python agent_work/exact_baseline/statevector_peaks.py \
  --max-qubits 28 \
  --topk 8 \
  --output-dir agent_work/exact_baseline
