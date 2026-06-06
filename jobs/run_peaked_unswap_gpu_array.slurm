#!/bin/bash
#SBATCH --job-name=peaked_unswap_gpu
#SBATCH --partition=interruptible_gpu
#SBATCH --constraint=a100_80g
#SBATCH --gres=gpu:1
#SBATCH --array=21,41-48%5
#SBATCH --cpus-per-task=16
#SBATCH --mem=80G
#SBATCH --time=02:00:00
#SBATCH --output=outputs/tree_tensor_sim/peaked_unswap_gpu/logs/%x-%A_%a.out
#SBATCH --error=outputs/tree_tensor_sim/peaked_unswap_gpu/logs/%x-%A_%a.err

set -euo pipefail

ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction-tree-tensor"
FALLBACK_ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
cd "$ROOT"

if [[ -d "$ROOT/.venv" ]]; then
  VENV="$ROOT/.venv"
else
  VENV="$FALLBACK_ROOT/.venv"
fi
source "$VENV/bin/activate"

export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MPLBACKEND=Agg
export PYTHONPATH="$ROOT/peaked-circuit-simulation:${PYTHONPATH:-}"

mkdir -p outputs/tree_tensor_sim/peaked_unswap_gpu/{json,stats,logs}

QASM_PATH="$(
  "$VENV/bin/python" - "$SLURM_ARRAY_TASK_ID" <<'PY'
import sys
from pathlib import Path

idx = int(sys.argv[1])
paths = sorted(Path("challenges").glob("*/*.qasm"), key=lambda p: (p.parent.name, p.name))
if idx < 0 or idx >= len(paths):
    raise SystemExit(f"array index {idx} out of range for {len(paths)} challenge files")
print(paths[idx])
PY
)"

srun "$VENV/bin/python" jobs/peaked_mpo_unswap_runner.py \
  --qasm "$QASM_PATH" \
  --out-dir outputs/tree_tensor_sim/peaked_unswap_gpu \
  --backend cuda \
  --max-bond "${PEAKED_UNSWAP_MAX_BOND:-8192}" \
  --mps-max-bond "${PEAKED_UNSWAP_MPS_MAX_BOND:-4096}" \
  --cutoff "${PEAKED_UNSWAP_CUTOFF:-0.002}" \
  --unswap-threshold "${PEAKED_UNSWAP_THRESHOLD:-1000000}" \
  --early-stopping-gates "${PEAKED_UNSWAP_EARLY_STOPPING_GATES:-0}" \
  --center-ratio "${PEAKED_UNSWAP_CENTER_RATIO:-0.5}" \
  --max-its "${PEAKED_UNSWAP_MAX_ITS:-20}" \
  --sabre-trials "${PEAKED_UNSWAP_SABRE_TRIALS:-512}" \
  --samples "${PEAKED_UNSWAP_SAMPLES:-1000}" \
  --seed "${PEAKED_UNSWAP_SEED:-20260612}"
