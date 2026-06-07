#!/bin/bash
#SBATCH --job-name=solve_80_46_centers
#SBATCH --partition=interruptible_gpu
#SBATCH --constraint=a100_80g
#SBATCH --gres=gpu:1
#SBATCH --array=0-14%3
#SBATCH --cpus-per-task=16
#SBATCH --mem=80G
#SBATCH --time=08:00:00
#SBATCH --output=outputs/tree_tensor_sim/solve_80_46_centers/logs/%x-%A_%a.out
#SBATCH --error=outputs/tree_tensor_sim/solve_80_46_centers/logs/%x-%A_%a.err

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
export PYTHONPATH="$ROOT/peaked-circuit-simulation:${PYTHONPATH:-}"

mkdir -p outputs/tree_tensor_sim/solve_80_46_centers/{json,stats,logs}

read -r CENTER CORE_WINDOW CUTOFF MAX_BOND MPS_MAX_BOND MAX_ITS SABRE_TRIALS TAG <<EOF_CFG
$(
  python - "$SLURM_ARRAY_TASK_ID" <<'PY'
import sys

idx = int(sys.argv[1])

# Centers found by inverse-palindrome forensics. The core window inserts
# a real MPO slice around the chosen center before left/right absorption.
#   5917 / 34586  = 0.1711, first U U^dagger center
#   17402 / 34586 = 0.5031, middle U U^dagger center
#   28810 / 34586 = 0.8330, final U U^dagger center
# Boundary ratios are likely P-layer neighborhoods between identity pairs.
centers = [
    ("u1_center", 0.1711, 96),
    ("p1_boundary", 0.3370, 32),
    ("u2_center", 0.5031, 96),
    ("p2_boundary", 0.6680, 32),
    ("u3_center", 0.8330, 96),
]
cutoffs = [
    ("loose", 2e-3, 8192, 4096, 20, 512),
    ("medium", 5e-4, 12288, 6144, 25, 768),
    ("tight", 1e-4, 16384, 8192, 30, 1024),
]
tag_c, center, core_window = centers[idx // len(cutoffs)]
tag_k, cutoff, max_bond, mps_max_bond, max_its, sabre_trials = cutoffs[idx % len(cutoffs)]
tag = f"{tag_c}_{tag_k}"
print(center, core_window, cutoff, max_bond, mps_max_bond, max_its, sabre_trials, tag)
PY
)
EOF_CFG

echo "challenge=80_46 center_ratio=$CENTER core_window_gates=$CORE_WINDOW cutoff=$CUTOFF max_bond=$MAX_BOND mps_max_bond=$MPS_MAX_BOND max_its=$MAX_ITS sabre_trials=$SABRE_TRIALS tag=$TAG"

srun "$VENV/bin/python" jobs/peaked_mpo_unswap_runner.py \
  --qasm challenges/very_hard/challenge-80_46.qasm \
  --out-dir "outputs/tree_tensor_sim/solve_80_46_centers/$TAG" \
  --backend cuda \
  --max-bond "$MAX_BOND" \
  --mps-max-bond "$MPS_MAX_BOND" \
  --cutoff "$CUTOFF" \
  --unswap-threshold 1000000 \
  --early-stopping-gates 0 \
  --center-ratio "$CENTER" \
  --core-window-gates "$CORE_WINDOW" \
  --max-its "$MAX_ITS" \
  --sabre-trials "$SABRE_TRIALS" \
  --samples 4096 \
  --seed 20260612
