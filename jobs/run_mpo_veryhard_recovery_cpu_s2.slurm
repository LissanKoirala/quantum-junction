#!/bin/bash
#SBATCH --job-name=mpo_vhard_rec2
#SBATCH --partition=interruptible_cpu
#SBATCH --array=0-4%5
#SBATCH --cpus-per-task=32
#SBATCH --mem=80G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/mpo_veryhard_recovery_cpu_s2/logs/%x-%A_%a.out
#SBATCH --error=outputs/mpo_veryhard_recovery_cpu_s2/logs/%x-%A_%a.err

# Recovery run for very_hard circuits that hit NaN due to zero-norm MPS.
# Fix: --mps-cutoff 1e-8 keeps the norm during MPO->MPS conversion.
# Also applies the raw-tensor NaN fallback in extract_marginal_bitstring.
# Targets: 64_44 72_45 80_46 88_47 96_48

set -euo pipefail

ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/hard-problems"
FALLBACK_ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
cd "$ROOT"

if [[ -d "$ROOT/.venv" ]]; then VENV="$ROOT/.venv"; else VENV="$FALLBACK_ROOT/.venv"; fi
source "$VENV/bin/activate"

export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-32}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-32}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-32}"
export MPLBACKEND=Agg
export PYTHONPATH="$ROOT/peaked-circuit-simulation:${PYTHONPATH:-}"

TARGETS=("64_44" "72_45" "80_46" "88_47" "96_48")
TASK_ID="${SLURM_ARRAY_TASK_ID:-0}"
LABEL="${TARGETS[$TASK_ID]}"

QASM_PATH=$(python3 -c "
from pathlib import Path
label = '${LABEL}'
qasm = next(Path('challenges/very_hard').glob(f'challenge-{label}.qasm'))
print(qasm)")

OUT_DIR="outputs/mpo_veryhard_recovery_cpu_s2"
mkdir -p "$OUT_DIR"/{json,stats,logs}

echo "Task ${TASK_ID}: label=${LABEL}, qasm=${QASM_PATH}"
echo "Recovery: mps-cutoff=1e-8, cutoff=0.0125, max-bond=512"

srun "$VENV/bin/python" jobs/peaked_mpo_graph_tns_runner.py \
  --qasm "$QASM_PATH" \
  --out-dir "$OUT_DIR" \
  --backend numpy \
  --max-bond 512 \
  --mps-max-bond 256 \
  --cutoff 0.0125 \
  --mps-cutoff 1e-8 \
  --unswap-threshold 180000 \
  --early-stopping-gates 0 \
  --center-ratio 0.45 \
  --max-its 10 \
  --sabre-trials 96 \
  --samples 512 \
  --seed 20260799 \
  --graph-ordering-min-improvement 0.02 \
  --graph-ordering-max-calls 8
