#!/bin/bash
#SBATCH --job-name=mpo_graph_tns_vhard_fast_b
#SBATCH --partition=interruptible_cpu
#SBATCH --array=0-7%8
#SBATCH --cpus-per-task=32
#SBATCH --mem=80G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/mpo_graph_tns_veryhard_fast_cpu_b/logs/%x-%A_%a.out
#SBATCH --error=outputs/mpo_graph_tns_veryhard_fast_cpu_b/logs/%x-%A_%a.err

set -euo pipefail

mkdir -p outputs/mpo_graph_tns_veryhard_fast_cpu_b/logs

export MPO_GRAPH_TNS_OUT_DIR="${MPO_GRAPH_TNS_OUT_DIR:-outputs/mpo_graph_tns_veryhard_fast_cpu_b}"
export MPO_GRAPH_TNS_SEED="${MPO_GRAPH_TNS_SEED:-20260617}"
export MPO_GRAPH_TNS_CENTER_RATIO="${MPO_GRAPH_TNS_CENTER_RATIO:-0.45}"
export MPO_GRAPH_TNS_MAX_BOND="${MPO_GRAPH_TNS_MAX_BOND:-768}"
export MPO_GRAPH_TNS_MPS_MAX_BOND="${MPO_GRAPH_TNS_MPS_MAX_BOND:-384}"
export MPO_GRAPH_TNS_CUTOFF="${MPO_GRAPH_TNS_CUTOFF:-0.0125}"
export MPO_GRAPH_TNS_UNSWAP_THRESHOLD="${MPO_GRAPH_TNS_UNSWAP_THRESHOLD:-180000}"
export MPO_GRAPH_TNS_MAX_ITS="${MPO_GRAPH_TNS_MAX_ITS:-10}"
export MPO_GRAPH_TNS_SABRE_TRIALS="${MPO_GRAPH_TNS_SABRE_TRIALS:-96}"
export MPO_GRAPH_TNS_SAMPLES="${MPO_GRAPH_TNS_SAMPLES:-384}"
export MPO_GRAPH_TNS_GRAPH_MAX_CALLS="${MPO_GRAPH_TNS_GRAPH_MAX_CALLS:-8}"

bash jobs/run_mpo_graph_tns_veryhard_fast_cpu_array.slurm
