#!/usr/bin/env bash
#SBATCH --job-name=total_st_rocm
#SBATCH --account=project_465003017
#SBATCH --partition=standard-g
#SBATCH --gres=gpu:mi250:1
#SBATCH --array=0-0%2
#SBATCH --cpus-per-task=16
#SBATCH --mem=220G
#SBATCH --time=12:00:00
#SBATCH --output=outputs/total_spacetime/logs/%x-%A_%a.out
#SBATCH --error=outputs/total_spacetime/logs/%x-%A_%a.err

set -euo pipefail

ROOT="${QJ_ROOT:-/pfs/lustrep3/users/laleekam/quantum-junction}"
CATEGORY="${TOTAL_ST_CATEGORY:-hard}"
cd "$ROOT"

module load cray-python >/dev/null 2>&1 || true

QASM_PATH="$(
  python3 - "$CATEGORY" "$SLURM_ARRAY_TASK_ID" <<'PY'
import sys
from pathlib import Path

category = sys.argv[1]
idx = int(sys.argv[2])
paths = sorted((Path("challenges") / category).glob("*.qasm"))
if idx < 0 or idx >= len(paths):
    raise SystemExit(f"array index {idx} out of range for {len(paths)} {category} challenges")
print(paths[idx])
PY
)"

STEM="$(basename "$QASM_PATH" .qasm)"
OUT="outputs/total_spacetime/${CATEGORY}_rocm/${STEM}_b${TOTAL_ST_MAX_BOND:-256}.json"

exec jobs/run_total_spacetime_rocm_one.sh "$QASM_PATH" "$OUT"
