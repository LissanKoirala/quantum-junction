#!/usr/bin/env bash
#SBATCH --job-name=qj-torch-cu121
#SBATCH --partition=interruptible_cpu
#SBATCH --time=00:45:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --output=slurm/%x-%j.out

set -euo pipefail

cd /cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction
export PYTHONUNBUFFERED=1

echo "Replacing torch with CUDA 12.1 build"
.venv/bin/python -m pip install --force-reinstall --index-url https://download.pytorch.org/whl/cu121 torch
.venv/bin/python - <<'PY'
import torch
print("torch", torch.__version__)
print("cuda available on this node", torch.cuda.is_available())
PY
