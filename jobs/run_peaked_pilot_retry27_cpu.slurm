#!/bin/bash
#SBATCH --job-name=peaked_retry27
#SBATCH --partition=interruptible_cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --output=outputs/peaked_circuit_sim_pilot/logs/%x-%j.out
#SBATCH --error=outputs/peaked_circuit_sim_pilot/logs/%x-%j.err

set -euo pipefail

ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
cd "$ROOT"

source .venv/bin/activate

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MPLBACKEND=Agg

srun .venv/bin/python jobs/peaked_sim_runner.py \
  --challenge-id 27 \
  --out-dir outputs/peaked_circuit_sim_pilot \
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
  --figure-note "pilot retry for challenge 8_27 on interruptible CPU after unsupported Blackwell CUDA arch; exact method/params/shims printed on this figure"
