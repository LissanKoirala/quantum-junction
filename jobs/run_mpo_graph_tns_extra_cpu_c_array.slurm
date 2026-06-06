#!/bin/bash
#SBATCH --job-name=mpo_graph_tns_extra_cpu_c
#SBATCH --partition=interruptible_cpu
#SBATCH --array=0-48%3
#SBATCH --cpus-per-task=32
#SBATCH --mem=80G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/mpo_graph_tns_extra_cpu_c/logs/%x-%A_%a.out
#SBATCH --error=outputs/mpo_graph_tns_extra_cpu_c/logs/%x-%A_%a.err

set -euo pipefail

export MPO_GRAPH_TNS_OUT_DIR="outputs/mpo_graph_tns_extra_cpu_c"
export MPO_GRAPH_TNS_SEED="${MPO_GRAPH_TNS_SEED:-20260615}"

bash jobs/run_mpo_graph_tns_extra_cpu_array.slurm
