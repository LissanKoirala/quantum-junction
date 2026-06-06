#!/bin/bash
#SBATCH --job-name=mpo_vhard_ultra
#SBATCH --partition=interruptible_cpu
#SBATCH --array=0-3%4
#SBATCH --cpus-per-task=32
#SBATCH --mem=80G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/mpo_veryhard_ultrafast_cpu/logs/%x-%A_%a.out
#SBATCH --error=outputs/mpo_veryhard_ultrafast_cpu/logs/%x-%A_%a.err

# Ultra-aggressive cutoff pass for hardest very_hard circuits (80_46, 88_47, 96_48, 104_49)
# Uses cutoff=0.05 (4x more aggressive than fast_b) and max_bond=128 to keep processing fast.
# Even with accuracy loss, peaked circuits should preserve dominant peak bitstring.

set -euo pipefail

ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/hard-problems"
FALLBACK_ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
cd "$ROOT"

if [[ -d "$ROOT/.venv" ]]; then
  VENV="$ROOT/.venv"
else
  VENV="$FALLBACK_ROOT/.venv"
fi
source "$VENV/bin/activate"

export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-32}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-32}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-32}"
export MPLBACKEND=Agg
export PYTHONPATH="$ROOT/peaked-circuit-simulation:${PYTHONPATH:-}"

# Targets: 80_46, 88_47, 96_48, 104_49
TARGETS=("80_46" "88_47" "96_48" "104_49")
TASK_ID="${SLURM_ARRAY_TASK_ID:-0}"
LABEL="${TARGETS[$TASK_ID]}"

QASM_PATH=$(python3 -c "
from pathlib import Path
label = '${LABEL}'
qasm = next(Path('challenges/very_hard').glob(f'challenge-{label}.qasm'))
print(qasm)")

OUT_DIR="outputs/mpo_veryhard_ultrafast_cpu"
mkdir -p "$OUT_DIR"/{json,stats,logs}

echo "Task ${TASK_ID}: label=${LABEL}, qasm=${QASM_PATH}"
echo "Ultra-aggressive cutoff=0.05, max_bond=128, sabre_trials=32"

srun "$VENV/bin/python" jobs/peaked_mpo_graph_tns_runner.py \
  --qasm "$QASM_PATH" \
  --out-dir "$OUT_DIR" \
  --backend numpy \
  --max-bond 128 \
  --mps-max-bond 64 \
  --cutoff 0.05 \
  --unswap-threshold 100000 \
  --early-stopping-gates 0 \
  --center-ratio 0.5 \
  --max-its 6 \
  --sabre-trials 32 \
  --samples 1024 \
  --seed 20260700 \
  --graph-ordering-min-improvement 0.02 \
  --graph-ordering-max-calls 4
