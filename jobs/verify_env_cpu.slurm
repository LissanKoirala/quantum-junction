#!/usr/bin/env bash
#SBATCH --job-name=qj-env-cpu
#SBATCH --partition=interruptible_cpu
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --output=slurm/%x-%j.out

set -euo pipefail

cd /cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction
export PYTHONPATH="$PWD/peaked-circuit-simulation:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

.venv/bin/python - <<'PY'
print("starting CPU env check", flush=True)
from qiskit import QuantumCircuit
print("imported qiskit", flush=True)
from qiskit.quantum_info import Statevector
print("imported statevector", flush=True)
import numpy, qiskit, qiskit_aer, quimb, qiskit_quimb, torch
print("imported dependency stack", flush=True)
import unswap, circuit_mpo, utils
print("imported local modules", flush=True)

print("host CPU env ok")
print("qiskit", qiskit.__version__)
print("qiskit_aer", qiskit_aer.__version__)
print("numpy", numpy.__version__)
print("quimb", quimb.__version__)
print("torch", torch.__version__)
print("torch cuda available", torch.cuda.is_available())

qc = QuantumCircuit.from_qasm_file("challenges/easy/challenge-8_11.qasm")
print("loaded qasm", flush=True)
sv = Statevector.from_instruction(qc.remove_final_measurements(inplace=False))
probs = sv.probabilities_dict()
peak = max(probs, key=probs.get)
print("challenge-8_11 peak", peak, probs[peak])
PY
