#!/usr/bin/env bash
#SBATCH --job-name=qj-env-gpu
#SBATCH --partition=interruptible_gpu
#SBATCH --time=00:20:00
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --output=slurm/%x-%j.out

set -euo pipefail

cd /cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction
export PYTHONPATH="$PWD/peaked-circuit-simulation:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

nvidia-smi || true

.venv/bin/python - <<'PY'
print("starting GPU env check", flush=True)
import torch
print("imported torch", flush=True)
import numpy, qiskit, qiskit_aer, quimb, qiskit_quimb
print("imported dependency stack", flush=True)
import unswap, circuit_mpo, utils
print("imported local modules", flush=True)

print("host GPU env ok")
print("qiskit", qiskit.__version__)
print("qiskit_aer", qiskit_aer.__version__)
print("numpy", numpy.__version__)
print("quimb", quimb.__version__)
print("torch", torch.__version__)
print("torch cuda available", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu count", torch.cuda.device_count())
    print("gpu name", torch.cuda.get_device_name(0))
    x = torch.ones((256, 256), device="cuda")
    y = x @ x
    torch.cuda.synchronize()
    print("cuda matmul checksum", float(y[0, 0].item()))
PY
