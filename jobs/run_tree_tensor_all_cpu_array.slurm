#!/bin/bash
#SBATCH --job-name=tree_tensor_cpu_all
#SBATCH --partition=interruptible_cpu
#SBATCH --array=0-48%50
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/tree_tensor_sim/all_cpu/logs/%x-%A_%a.out
#SBATCH --error=outputs/tree_tensor_sim/all_cpu/logs/%x-%A_%a.err

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

mkdir -p outputs/tree_tensor_sim/all_cpu/{json,images,stats,logs}

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

srun "$VENV/bin/python" jobs/tree_tensor_runner.py \
  --qasm "$QASM_PATH" \
  --out-dir outputs/tree_tensor_sim/all_cpu \
  --backend numpy \
  --max-bond 512 \
  --cutoff 1e-7 \
  --gate-contract swap+split \
  --order-method weighted_spectral \
  --graph-ops cx swap \
  --recency-alpha 0.15 \
  --samples 1024 \
  --sample-top-k 12 \
  --seed 20260605 \
  --figure-note "CPU full sweep: graph-derived weighted spectral qubit order plus maximum-spanning-tree metadata; Quimb CircuitMPS fallback, no Aer MPS or statevector"
