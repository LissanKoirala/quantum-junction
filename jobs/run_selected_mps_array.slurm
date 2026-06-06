#!/usr/bin/env bash
#SBATCH --job-name=qj-mps-ids
#SBATCH --partition=interruptible_cpu
#SBATCH --time=1-00:00:00
#SBATCH --cpus-per-task=32
#SBATCH --mem=80G
#SBATCH --array=0-4
#SBATCH --output=outputs/sim_11_26_34_41_49/logs/%x-%A_%a.out
#SBATCH --error=outputs/sim_11_26_34_41_49/logs/%x-%A_%a.err

set -euo pipefail

cd /cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction
mkdir -p outputs/sim_11_26_34_41_49/logs
export PYTHONUNBUFFERED=1

IDS=(11 26 34 41 49)
ID="${IDS[$SLURM_ARRAY_TASK_ID]}"

SHOTS="${MPS_SHOTS:-4096}"
BOND_DIM="${MPS_BOND_DIM:-64}"
SEED="${MPS_SEED:-12345}"

# Very hard 104q/26k-gate challenge is a canary at lower settings by default.
if [[ "$ID" == "49" ]]; then
  SHOTS="${MPS_SHOTS_49:-1024}"
  BOND_DIM="${MPS_BOND_DIM_49:-32}"
fi

.venv/bin/python jobs/sim_selected.py \
  --method mps \
  --id "$ID" \
  --shots "$SHOTS" \
  --bond-dim "$BOND_DIM" \
  --seed "$SEED" \
  --out-dir outputs/sim_11_26_34_41_49
