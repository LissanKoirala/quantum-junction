#!/usr/bin/env bash
#SBATCH --job-name=qj-static-forensics
#SBATCH --partition=interruptible_cpu
#SBATCH --time=00:05:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --output=agent_work/static_forensics/%x-%j.out

set -euo pipefail

cd /cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction
export PYTHONUNBUFFERED=1

.venv/bin/python agent_work/static_forensics/static_qasm_forensics.py
