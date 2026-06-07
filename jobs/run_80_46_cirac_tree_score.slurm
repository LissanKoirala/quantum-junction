#!/bin/bash
#SBATCH --job-name=cirac_tree_80_46
#SBATCH --partition=interruptible_gpu
#SBATCH --constraint=a100_80g
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=80G
#SBATCH --time=08:00:00
#SBATCH --output=outputs/tree_tensor_sim/cirac_tree_score/logs/%x-%j.out
#SBATCH --error=outputs/tree_tensor_sim/cirac_tree_score/logs/%x-%j.err

set -euo pipefail

ROOT="${ROOT:-$(pwd)}"
cd "$ROOT"

VENV="${VENV:-$ROOT/.venv}"
source "$VENV/bin/activate"

export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MPLBACKEND=Agg

mkdir -p outputs/tree_tensor_sim/cirac_tree_score/{json,logs}

ARGS=(
  --qasm challenges/very_hard/challenge-80_46.qasm
  --out outputs/tree_tensor_sim/cirac_tree_score/json/challenge-80_46.cirac_tree_score.json
  --backend cuda
  --optimizer tree-greedy
  --optimizer-repeats "${CIRAC_TREE_OPT_REPEATS:-64}"
  --candidate-limit "${CIRAC_TREE_CANDIDATE_LIMIT:-64}"
  --hamming-radius "${CIRAC_TREE_HAMMING_RADIUS:-1}"
  --max-neighbors-per-candidate "${CIRAC_TREE_MAX_NEIGHBORS:-256}"
)

if [[ -f outputs/tree_tensor_sim/solve_80_46_centers/SUBSPACE_COUNTS.csv ]]; then
  ARGS+=(--candidate-counts outputs/tree_tensor_sim/solve_80_46_centers/SUBSPACE_COUNTS.csv)
fi

if [[ -n "${QPU_COUNTS:-}" ]]; then
  ARGS+=(--candidate-counts "$QPU_COUNTS")
fi

if [[ -n "${CANDIDATE:-}" ]]; then
  ARGS+=(--candidate "$CANDIDATE")
fi

srun "$VENV/bin/python" jobs/cirac_tree_score_candidates.py "${ARGS[@]}"
