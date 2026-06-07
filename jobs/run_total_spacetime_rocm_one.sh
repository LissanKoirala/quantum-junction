#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <qasm-path> <output-json>" >&2
  exit 2
fi

QASM_PATH="$1"
OUTPUT_JSON="$2"

ROOT="${QJ_ROOT:-/pfs/lustrep3/users/laleekam/quantum-junction}"
cd "$ROOT"

module load rocm cray-python >/dev/null 2>&1 || true

export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export MPLBACKEND=Agg

if [[ -n "${QJ_ROCM_VENV:-}" ]]; then
  VENV="$QJ_ROCM_VENV"
elif [[ -d /scratch/project_465003017 && -w /scratch/project_465003017 ]]; then
  VENV="/scratch/project_465003017/${USER:-laleekam}/qj-rocm-venv"
else
  VENV="${TMPDIR:-/tmp}/laleekam-qj-rocm-venv"
fi
READY="$VENV/.qj-rocm-ready-v3"

if [[ ! -f "$READY" || ! -x "$VENV/bin/python" ]]; then
  mkdir -p "$(dirname "$VENV")"
  exec 9>"$VENV.lock"
  flock 9
  if [[ ! -f "$READY" || ! -x "$VENV/bin/python" ]]; then
    rm -rf "$VENV"
    python -m venv "$VENV"
    "$VENV/bin/python" -m pip install --upgrade pip setuptools wheel --no-cache-dir
    "$VENV/bin/python" -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/rocm6.3 torch
    "$VENV/bin/python" -m pip install --no-cache-dir \
      numpy scipy qiskit quimb cotengra autoray tqdm networkx rustworkx opt_einsum qiskit-quimb
    touch "$READY"
  fi
fi

source "$VENV/bin/activate"

python - <<'PY'
import torch
print(
    "rocm_probe",
    "torch", torch.__version__,
    "hip", getattr(torch.version, "hip", None),
    "cuda_available", torch.cuda.is_available(),
    flush=True,
)
if not torch.cuda.is_available():
    raise SystemExit("GPU backend requested but torch.cuda.is_available() is False")
print("rocm_probe_device", torch.cuda.get_device_name(0), flush=True)
x = torch.ones((16, 16), device="cuda")
print("rocm_probe_matmul", float((x @ x)[0, 0].item()), flush=True)
PY

mkdir -p "$(dirname "$OUTPUT_JSON")" outputs/total_spacetime/logs

python total_spacetime_pipeline/run_total_spacetime_pipeline.py \
  --qasm "$QASM_PATH" \
  --backend cuda \
  --track "${TOTAL_ST_TRACK:-both}" \
  --executor-mode "${TOTAL_ST_EXECUTOR_MODE:-explicit_rewire}" \
  --num-spawn-centers "${TOTAL_ST_NUM_SPAWN_CENTERS:-3}" \
  --top-k-centers "${TOTAL_ST_TOP_K_CENTERS:-5}" \
  --min-center-separation "${TOTAL_ST_MIN_CENTER_SEPARATION:-3}" \
  --graph-method "${TOTAL_ST_GRAPH_METHOD:-spectral_local}" \
  --graph-local-passes "${TOTAL_ST_GRAPH_LOCAL_PASSES:-40}" \
  --trial-absorb-layers "${TOTAL_ST_TRIAL_ABSORB_LAYERS:-6}" \
  --max-bond "${TOTAL_ST_MAX_BOND:-256}" \
  --cutoff-window "${TOTAL_ST_CUTOFF_WINDOW:-1e-6}" \
  --cutoff-final "${TOTAL_ST_CUTOFF_FINAL:-1e-4}" \
  --max-global-unswap-its "${TOTAL_ST_MAX_GLOBAL_UNSWAP_ITS:-20}" \
  --early-stopping-gates "${TOTAL_ST_EARLY_STOPPING_GATES:-50}" \
  --sabre-trials "${TOTAL_ST_SABRE_TRIALS:-20000}" \
  --window-size "${TOTAL_ST_WINDOW_SIZE:-8}" \
  --max-segments "${TOTAL_ST_MAX_SEGMENTS:-4}" \
  --identity-error-threshold "${TOTAL_ST_IDENTITY_ERROR_THRESHOLD:-0.05}" \
  --peak-num-samples "${TOTAL_ST_PEAK_NUM_SAMPLES:-500}" \
  --bitflip-rounds "${TOTAL_ST_BITFLIP_ROUNDS:-5}" \
  --output "$OUTPUT_JSON"
