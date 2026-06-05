#!/bin/bash
#SBATCH --job-name=mpo-smoke-compat
#SBATCH --partition=interruptible_cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=00:20:00
#SBATCH --output=agent_work/mpo_unswap/logs/smoke_compat_%j.out
#SBATCH --error=agent_work/mpo_unswap/logs/smoke_compat_%j.err

set -euo pipefail

cd /cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction
source .venv/bin/activate

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export NUMBA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"

python agent_work/mpo_unswap/scripts/smoke_mpo_unswap.py \
  --root "$PWD" \
  --qasm "challenges/very easy/challenge-8_1.qasm" \
  --out "agent_work/mpo_unswap/results/smoke_compat.json" \
  --mode compat \
  --max-bond 32 \
  --cutoff 1e-8 \
  --rewire-trials 8 \
  --run-compress
