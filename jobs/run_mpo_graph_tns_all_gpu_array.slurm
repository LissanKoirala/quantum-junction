#!/bin/bash
#SBATCH --job-name=mpo_graph_tns_all
#SBATCH --partition=interruptible_gpu
#SBATCH --constraint=a100_80g
#SBATCH --gres=gpu:1
#SBATCH --array=0-48%5
#SBATCH --cpus-per-task=16
#SBATCH --mem=80G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/mpo_graph_tns_all/logs/%x-%A_%a.out
#SBATCH --error=outputs/mpo_graph_tns_all/logs/%x-%A_%a.err

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
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MPLBACKEND=Agg
export PYTHONPATH="$ROOT/peaked-circuit-simulation:${PYTHONPATH:-}"

OUT_DIR="${MPO_GRAPH_TNS_OUT_DIR:-outputs/mpo_graph_tns_all}"
mkdir -p "$OUT_DIR"/{json,stats,logs}

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

srun "$VENV/bin/python" jobs/peaked_mpo_graph_tns_runner.py \
  --qasm "$QASM_PATH" \
  --out-dir "$OUT_DIR" \
  --backend cuda \
  --max-bond "${MPO_GRAPH_TNS_MAX_BOND:-8192}" \
  --mps-max-bond "${MPO_GRAPH_TNS_MPS_MAX_BOND:-4096}" \
  --cutoff "${MPO_GRAPH_TNS_CUTOFF:-0.002}" \
  --unswap-threshold "${MPO_GRAPH_TNS_UNSWAP_THRESHOLD:-1000000}" \
  --early-stopping-gates "${MPO_GRAPH_TNS_EARLY_STOPPING_GATES:-0}" \
  --center-ratio "${MPO_GRAPH_TNS_CENTER_RATIO:-0.5}" \
  --max-its "${MPO_GRAPH_TNS_MAX_ITS:-20}" \
  --sabre-trials "${MPO_GRAPH_TNS_SABRE_TRIALS:-512}" \
  --samples "${MPO_GRAPH_TNS_SAMPLES:-1000}" \
  --seed "${MPO_GRAPH_TNS_SEED:-20260612}" \
  --graph-ordering-min-improvement "${MPO_GRAPH_TNS_GRAPH_MIN_IMPROVEMENT:-0.02}" \
  --graph-ordering-max-calls "${MPO_GRAPH_TNS_GRAPH_MAX_CALLS:-10}"
