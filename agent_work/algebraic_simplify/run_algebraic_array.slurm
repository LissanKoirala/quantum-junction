#!/usr/bin/env bash
#SBATCH --job-name=qj-algebra
#SBATCH --partition=interruptible_cpu
#SBATCH --time=00:45:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --array=1-49%49
#SBATCH --output=agent_work/algebraic_simplify/logs/%x-%A_%a.out

set -euo pipefail

cd /cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-2}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-2}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-2}"

LIST="agent_work/algebraic_simplify/challenge_files.txt"
PATH_TO_RUN="$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$LIST")"
if [[ -z "${PATH_TO_RUN}" ]]; then
  echo "empty path for task ${SLURM_ARRAY_TASK_ID}" >&2
  exit 2
fi

echo "task=${SLURM_ARRAY_TASK_ID} path=${PATH_TO_RUN} host=$(hostname) start=$(date -Is)"
.venv/bin/python agent_work/algebraic_simplify/algebraic_simplify.py one "$PATH_TO_RUN" --statevector
echo "done $(date -Is)"
