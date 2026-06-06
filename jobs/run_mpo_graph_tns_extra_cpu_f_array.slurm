#!/bin/bash
#SBATCH --job-name=mpo_graph_tns_extra_cpu_f
#SBATCH --partition=interruptible_cpu
#SBATCH --array=23-24,41-48%1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/mpo_graph_tns_extra_cpu_f/logs/%x-%A_%a.out
#SBATCH --error=outputs/mpo_graph_tns_extra_cpu_f/logs/%x-%A_%a.err

set -euo pipefail

export MPO_GRAPH_TNS_OUT_DIR="outputs/mpo_graph_tns_extra_cpu_f"
export MPO_GRAPH_TNS_SEED="${MPO_GRAPH_TNS_SEED:-20260616}"

bash jobs/run_mpo_graph_tns_extra_cpu_array.slurm
