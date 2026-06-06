#!/usr/bin/env bash
#SBATCH --job-name=qj-sv-ids
#SBATCH --partition=interruptible_cpu
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --output=outputs/sim_11_26_34_41_49/logs/%x-%j.out
#SBATCH --error=outputs/sim_11_26_34_41_49/logs/%x-%j.err

set -euo pipefail

cd /cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction
mkdir -p outputs/sim_11_26_34_41_49/logs
export PYTHONUNBUFFERED=1

.venv/bin/python jobs/sim_selected.py \
  --method statevector \
  --ids 11 26 34 41 49 \
  --max-qubits 30 \
  --out-dir outputs/sim_11_26_34_41_49
