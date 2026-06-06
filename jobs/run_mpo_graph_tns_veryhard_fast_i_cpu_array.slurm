#!/bin/bash
#SBATCH --job-name=mpo_graph_tns_vhard_fast_i
#SBATCH --partition=interruptible_cpu
#SBATCH --array=2-6%5
#SBATCH --cpus-per-task=32
#SBATCH --mem=96G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/mpo_graph_tns_veryhard_fast_cpu_i/logs/%x-%A_%a.out
#SBATCH --error=outputs/mpo_graph_tns_veryhard_fast_cpu_i/logs/%x-%A_%a.err

set -euo pipefail

mkdir -p outputs/mpo_graph_tns_veryhard_fast_cpu_i/logs

export MPO_GRAPH_TNS_OUT_DIR="${MPO_GRAPH_TNS_OUT_DIR:-outputs/mpo_graph_tns_veryhard_fast_cpu_i}"
export MPO_GRAPH_TNS_SEED="${MPO_GRAPH_TNS_SEED:-20260673}"
export MPO_GRAPH_TNS_CENTER_RATIO="${MPO_GRAPH_TNS_CENTER_RATIO:-0.25}"
export MPO_GRAPH_TNS_MAX_BOND="${MPO_GRAPH_TNS_MAX_BOND:-1280}"
export MPO_GRAPH_TNS_MPS_MAX_BOND="${MPO_GRAPH_TNS_MPS_MAX_BOND:-640}"
export MPO_GRAPH_TNS_CUTOFF="${MPO_GRAPH_TNS_CUTOFF:-0.01}"
export MPO_GRAPH_TNS_UNSWAP_THRESHOLD="${MPO_GRAPH_TNS_UNSWAP_THRESHOLD:-260000}"
export MPO_GRAPH_TNS_MAX_ITS="${MPO_GRAPH_TNS_MAX_ITS:-14}"
export MPO_GRAPH_TNS_SABRE_TRIALS="${MPO_GRAPH_TNS_SABRE_TRIALS:-192}"
export MPO_GRAPH_TNS_SAMPLES="${MPO_GRAPH_TNS_SAMPLES:-1024}"
export MPO_GRAPH_TNS_GRAPH_MAX_CALLS="${MPO_GRAPH_TNS_GRAPH_MAX_CALLS:-14}"

bash jobs/run_mpo_graph_tns_veryhard_fast_cpu_array.slurm
