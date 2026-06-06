#!/bin/bash
#SBATCH --job-name=mpo_graph_tns_missing_cpu
#SBATCH --partition=interruptible_cpu
#SBATCH --array=0-48%28
#SBATCH --cpus-per-task=32
#SBATCH --mem=80G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/mpo_graph_tns_missing_cpu/logs/%x-%A_%a.out
#SBATCH --error=outputs/mpo_graph_tns_missing_cpu/logs/%x-%A_%a.err

set -euo pipefail

ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/klalee-graph"
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

OUT_DIR="outputs/mpo_graph_tns_missing_cpu"
mkdir -p "$OUT_DIR"/{json,stats,logs}

mapfile -t CHALLENGE_INFO < <(
  "$VENV/bin/python" - "$SLURM_ARRAY_TASK_ID" "$OUT_DIR" <<'PY'
import json
import sys
from pathlib import Path

idx = int(sys.argv[1])
out_dir = Path(sys.argv[2])
paths = sorted(Path("challenges").glob("*/*.qasm"), key=lambda p: (p.parent.name, p.name))
if idx < 0 or idx >= len(paths):
    raise SystemExit(f"array index {idx} out of range for {len(paths)} challenge files")

qasm_path = paths[idx]
label = qasm_path.stem.removeprefix("challenge-")
json_name = f"challenge-{label}.peaked_mpo_graph_tns.json"
coverage_dirs = [
    Path("outputs/mpo_graph_tns_all_cpu/json"),
    Path("outputs/mpo_graph_tns_all/json"),
    Path("outputs/mpo_graph_tns_param_probe/json"),
    Path("outputs/mpo_graph_tns_extra_cpu/json"),
    Path("outputs/mpo_graph_tns_extra_cpu_b/json"),
    Path("outputs/mpo_graph_tns_extra_cpu_c/json"),
    Path("outputs/mpo_graph_tns_extra_cpu_d/json"),
    Path("outputs/mpo_graph_tns_extra_cpu_e/json"),
    out_dir / "json",
]

covered = False
for directory in coverage_dirs:
    path = directory / json_name
    if not path.exists():
        continue
    try:
        row = json.loads(path.read_text())
    except Exception:
        continue
    validation = (row.get("validation") or {}).get("status")
    if row.get("status") == "ok" and row.get("final_candidate_qiskit_order") and validation != "incorrect":
        covered = True
        break

print(qasm_path)
print(label)
print("1" if covered else "0")
PY
)

QASM_PATH="${CHALLENGE_INFO[0]}"
CHALLENGE_LABEL="${CHALLENGE_INFO[1]}"
COVERED="${CHALLENGE_INFO[2]}"

if [[ "$COVERED" == "1" ]]; then
  echo "challenge $CHALLENGE_LABEL already has an ok candidate; skipping"
  exit 0
fi

echo "challenge $CHALLENGE_LABEL has no ok candidate; running missing-coverage retry"
srun "$VENV/bin/python" jobs/peaked_mpo_graph_tns_runner.py \
  --qasm "$QASM_PATH" \
  --out-dir "$OUT_DIR" \
  --backend numpy \
  --max-bond "${MPO_GRAPH_TNS_MAX_BOND:-8192}" \
  --mps-max-bond "${MPO_GRAPH_TNS_MPS_MAX_BOND:-4096}" \
  --cutoff "${MPO_GRAPH_TNS_CUTOFF:-0.002}" \
  --unswap-threshold "${MPO_GRAPH_TNS_UNSWAP_THRESHOLD:-1000000}" \
  --early-stopping-gates "${MPO_GRAPH_TNS_EARLY_STOPPING_GATES:-0}" \
  --center-ratio "${MPO_GRAPH_TNS_CENTER_RATIO:-0.5}" \
  --max-its "${MPO_GRAPH_TNS_MAX_ITS:-20}" \
  --sabre-trials "${MPO_GRAPH_TNS_SABRE_TRIALS:-500}" \
  --samples "${MPO_GRAPH_TNS_SAMPLES:-1000}" \
  --seed "${MPO_GRAPH_TNS_SEED:-20260612}" \
  --graph-ordering-min-improvement "${MPO_GRAPH_TNS_GRAPH_MIN_IMPROVEMENT:-0.02}" \
  --graph-ordering-max-calls "${MPO_GRAPH_TNS_GRAPH_MAX_CALLS:-5}"
