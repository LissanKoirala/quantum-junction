#!/bin/bash
#SBATCH --job-name=tree_tensor_degree_cpu
#SBATCH --partition=interruptible_cpu
#SBATCH --array=0-48%20
#SBATCH --cpus-per-task=16
#SBATCH --mem=24G
#SBATCH --time=08:00:00
#SBATCH --output=outputs/tree_tensor_sim/degree_cpu/logs/%x-%A_%a.out
#SBATCH --error=outputs/tree_tensor_sim/degree_cpu/logs/%x-%A_%a.err

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

mkdir -p outputs/tree_tensor_sim/degree_cpu/{json,images,stats,logs}

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

SKIP_DONE="$(
  "$VENV/bin/python" - "$QASM_PATH" <<'PY'
import json
import re
import sys
from pathlib import Path

qasm = Path(sys.argv[1])
match = re.match(r"challenge-(\d+)_(\d+)\.qasm$", qasm.name)
if not match:
    print("0")
    raise SystemExit
label = f"{match.group(1)}_{match.group(2)}"
path = Path("outputs/tree_tensor_sim/all_cpu/json") / f"challenge-{label}.quimb_tree_graph_mps.json"
if path.exists():
    try:
        data = json.loads(path.read_text())
    except Exception:
        data = {}
    if data.get("status") == "ok":
        print("1")
        raise SystemExit
print("0")
PY
)"

if [[ "$SKIP_DONE" == "1" ]]; then
  echo "Skipping $QASM_PATH because canonical all_cpu result is already ok."
  exit 0
fi

srun "$VENV/bin/python" jobs/tree_tensor_runner.py \
  --qasm "$QASM_PATH" \
  --out-dir outputs/tree_tensor_sim/degree_cpu \
  --backend numpy \
  --max-bond 128 \
  --cutoff 1e-5 \
  --gate-contract swap+split \
  --order-method degree \
  --graph-ops cx swap \
  --recency-alpha 0.15 \
  --samples 512 \
  --sample-top-k 12 \
  --seed 20260609 \
  --figure-note "Degree-order exploratory CPU pass: skips canonical all_cpu ok results; separate output folder; lower bond/cutoff for alternate graph-aware ordering candidates"
