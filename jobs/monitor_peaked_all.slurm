#!/bin/bash
#SBATCH --job-name=monitor_peaked_all
#SBATCH --partition=interruptible_cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/peaked_circuit_sim_all/logs/%x-%j.out
#SBATCH --error=outputs/peaked_circuit_sim_all/logs/%x-%j.err

set -euo pipefail

ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
cd "$ROOT"

source .venv/bin/activate

srun .venv/bin/python jobs/monitor_peaked_all.py \
  --job-id 34607501 \
  --out-dir outputs/peaked_circuit_sim_all \
  --interval-seconds 1800 \
  --max-checks 96
