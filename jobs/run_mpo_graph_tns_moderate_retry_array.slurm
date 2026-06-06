#!/bin/bash
#SBATCH --job-name=mpo_graph_tns_mod_retry
#SBATCH --partition=interruptible_cpu
#SBATCH --array=0-7%4
#SBATCH --cpus-per-task=16
#SBATCH --mem=80G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/mpo_graph_tns_moderate_retry/logs/%x-%A_%a.out
#SBATCH --error=outputs/mpo_graph_tns_moderate_retry/logs/%x-%A_%a.err

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
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MPLBACKEND=Agg
export PYTHONPATH="$ROOT/peaked-circuit-simulation:${PYTHONPATH:-}"

mkdir -p outputs/mpo_graph_tns_moderate_retry/logs

mapfile -t TASK_INFO < <(
  "$VENV/bin/python" - "$SLURM_ARRAY_TASK_ID" <<'PY'
import json
import sys
from pathlib import Path

task_id = int(sys.argv[1])
variants = [
    {
        "suffix": "h",
        "seed": "20260613",
        "sabre_trials": "500",
        "graph_calls": "5",
        "center_ratio": "0.5",
        "cutoff": "0.002",
        "samples": "4000",
    },
    {
        "suffix": "i",
        "seed": "20260618",
        "sabre_trials": "500",
        "graph_calls": "5",
        "center_ratio": "0.5",
        "cutoff": "0.002",
        "samples": "4000",
    },
    {
        "suffix": "j",
        "seed": "20260619",
        "sabre_trials": "300",
        "graph_calls": "3",
        "center_ratio": "0.35",
        "cutoff": "0.002",
        "samples": "4000",
    },
    {
        "suffix": "k",
        "seed": "20260620",
        "sabre_trials": "300",
        "graph_calls": "3",
        "center_ratio": "0.65",
        "cutoff": "0.001",
        "samples": "4000",
    },
]
labels = ["16_28", "24_29"]
if task_id < 0 or task_id >= len(variants) * len(labels):
    raise SystemExit(f"array index {task_id} out of range")

variant = variants[task_id // len(labels)]
label = labels[task_id % len(labels)]
qasm_matches = list(Path("challenges").glob(f"*/challenge-{label}.qasm"))
if len(qasm_matches) != 1:
    raise SystemExit(f"expected one qasm for {label}, found {qasm_matches}")

json_name = f"challenge-{label}.peaked_mpo_graph_tns.json"
coverage_dirs = [
    Path("outputs/mpo_graph_tns_all_cpu/json"),
    Path("outputs/mpo_graph_tns_all/json"),
    Path("outputs/mpo_graph_tns_gpu_retry/json"),
    Path("outputs/mpo_graph_tns_param_probe/json"),
    Path("outputs/mpo_graph_tns_missing_cpu/json"),
    Path("outputs/mpo_graph_tns_extra_cpu/json"),
    Path("outputs/mpo_graph_tns_extra_cpu_b/json"),
    Path("outputs/mpo_graph_tns_extra_cpu_c/json"),
    Path("outputs/mpo_graph_tns_extra_cpu_d/json"),
    Path("outputs/mpo_graph_tns_extra_cpu_e/json"),
    Path("outputs/mpo_graph_tns_extra_cpu_f/json"),
    Path("outputs/mpo_graph_tns_extra_cpu_g/json"),
    Path("outputs/mpo_graph_tns_moderate_retry_h/json"),
    Path("outputs/mpo_graph_tns_moderate_retry_i/json"),
    Path("outputs/mpo_graph_tns_moderate_retry_j/json"),
    Path("outputs/mpo_graph_tns_moderate_retry_k/json"),
    Path("outputs/mpo_graph_tns_sample_top_postprocess/json"),
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

out_dir = f"outputs/mpo_graph_tns_moderate_retry_{variant['suffix']}"
print(qasm_matches[0])
print(label)
print(out_dir)
print(variant["seed"])
print(variant["sabre_trials"])
print(variant["graph_calls"])
print(variant["center_ratio"])
print(variant["cutoff"])
print(variant["samples"])
print("1" if covered else "0")
PY
)

QASM_PATH="${TASK_INFO[0]}"
CHALLENGE_LABEL="${TASK_INFO[1]}"
OUT_DIR="${TASK_INFO[2]}"
SEED="${TASK_INFO[3]}"
SABRE_TRIALS="${TASK_INFO[4]}"
GRAPH_CALLS="${TASK_INFO[5]}"
CENTER_RATIO="${TASK_INFO[6]}"
CUTOFF="${TASK_INFO[7]}"
SAMPLES="${TASK_INFO[8]}"
COVERED="${TASK_INFO[9]}"

mkdir -p "$OUT_DIR"/{json,stats,logs}

if [[ "$COVERED" == "1" ]]; then
  echo "challenge $CHALLENGE_LABEL already has an ok candidate; skipping"
  exit 0
fi

echo "running moderate retry for $CHALLENGE_LABEL into $OUT_DIR seed=$SEED center=$CENTER_RATIO cutoff=$CUTOFF"
srun "$VENV/bin/python" jobs/peaked_mpo_graph_tns_runner.py \
  --qasm "$QASM_PATH" \
  --out-dir "$OUT_DIR" \
  --backend numpy \
  --max-bond "${MPO_GRAPH_TNS_MAX_BOND:-8192}" \
  --mps-max-bond "${MPO_GRAPH_TNS_MPS_MAX_BOND:-4096}" \
  --cutoff "$CUTOFF" \
  --unswap-threshold "${MPO_GRAPH_TNS_UNSWAP_THRESHOLD:-1000000}" \
  --early-stopping-gates "${MPO_GRAPH_TNS_EARLY_STOPPING_GATES:-0}" \
  --center-ratio "$CENTER_RATIO" \
  --max-its "${MPO_GRAPH_TNS_MAX_ITS:-20}" \
  --sabre-trials "$SABRE_TRIALS" \
  --samples "$SAMPLES" \
  --seed "$SEED" \
  --graph-ordering-min-improvement "${MPO_GRAPH_TNS_GRAPH_MIN_IMPROVEMENT:-0.02}" \
  --graph-ordering-max-calls "$GRAPH_CALLS"
