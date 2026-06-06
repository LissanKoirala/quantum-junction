#!/bin/bash
#SBATCH --job-name=monitor_peaked_retry
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

: "${MONITOR_JOB_ID:?set MONITOR_JOB_ID to the Slurm array job id to monitor}"

srun .venv/bin/python jobs/monitor_peaked_all.py \
  --job-id "$MONITOR_JOB_ID" \
  --out-dir outputs/peaked_circuit_sim_all \
  --interval-seconds 1800 \
  --max-checks 96 \
  --array-throttle "${MONITOR_ARRAY_THROTTLE:-31}"
