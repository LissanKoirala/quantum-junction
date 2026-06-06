#!/bin/bash
#SBATCH --job-name=tree_tensor_opt_u3_gpu
#SBATCH --partition=interruptible_gpu
#SBATCH --constraint=a100_80g
#SBATCH --gres=gpu:1
#SBATCH --array=0-8%5
#SBATCH --cpus-per-task=16
#SBATCH --mem=80G
#SBATCH --time=02:00:00
#SBATCH --output=outputs/tree_tensor_sim/opt_u3_gpu/logs/%x-%A_%a.out
#SBATCH --error=outputs/tree_tensor_sim/opt_u3_gpu/logs/%x-%A_%a.err

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

mkdir -p outputs/tree_tensor_sim/opt_u3_gpu/{json,images,stats,logs}

QASM_PATH="$(
  "$VENV/bin/python" - "$SLURM_ARRAY_TASK_ID" <<'PY'
import sys
from pathlib import Path

idx = int(sys.argv[1])
labels = ["64_40", "104_49", "48_42", "56_43", "64_44", "72_45", "80_46", "88_47", "96_48"]
if idx < 0 or idx >= len(labels):
    raise SystemExit(f"array index {idx} out of range for {len(labels)} optimized U3 files")
print(Path("outputs/tree_tensor_sim/optimized_qasm/qasm_u3") / f"challenge-{labels[idx]}.qasm")
PY
)"

srun "$VENV/bin/python" jobs/tree_tensor_runner.py \
  --qasm "$QASM_PATH" \
  --out-dir outputs/tree_tensor_sim/opt_u3_gpu \
  --backend auto \
  --max-bond 512 \
  --cutoff 1e-7 \
  --gate-contract swap+split \
  --order-method weighted_spectral \
  --graph-ops cx swap \
  --recency-alpha 0.15 \
  --samples 1024 \
  --sample-top-k 12 \
  --seed 20260612 \
  --figure-note "optimized-U3 GPU pass for remaining blanks: Qiskit optimization_level=3 merged one-qubit rotations; wall time capped at two hours"
