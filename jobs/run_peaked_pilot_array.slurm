#!/bin/bash
#SBATCH --job-name=peaked_pilot
#SBATCH --partition=interruptible_gpu
#SBATCH --gres=gpu:1
#SBATCH --array=0-2%3
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --output=outputs/peaked_circuit_sim_pilot/logs/%x-%A_%a.out
#SBATCH --error=outputs/peaked_circuit_sim_pilot/logs/%x-%A_%a.err

set -euo pipefail

ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
cd "$ROOT"

source .venv/bin/activate

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export MPLBACKEND=Agg

IDS=(1 11 27)
CHALLENGE_ID="${IDS[$SLURM_ARRAY_TASK_ID]}"

srun .venv/bin/python jobs/peaked_sim_runner.py \
  --challenge-id "$CHALLENGE_ID" \
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
  --figure-note "pilot small set before full 49-circuit sweep; exact method/params/shims printed on this figure"
