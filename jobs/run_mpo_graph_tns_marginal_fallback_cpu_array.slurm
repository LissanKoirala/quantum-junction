#!/bin/bash
#SBATCH --job-name=mpo_graph_tns_marginal
#SBATCH --partition=interruptible_cpu
#SBATCH --array=2-7%6
#SBATCH --cpus-per-task=32
#SBATCH --mem=80G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/mpo_graph_tns_marginal_fallback_cpu/logs/%x-%A_%a.out
#SBATCH --error=outputs/mpo_graph_tns_marginal_fallback_cpu/logs/%x-%A_%a.err

set -euo pipefail

mkdir -p outputs/mpo_graph_tns_marginal_fallback_cpu/logs

export MPO_GRAPH_TNS_OUT_DIR="${MPO_GRAPH_TNS_OUT_DIR:-outputs/mpo_graph_tns_marginal_fallback_cpu}"
export MPO_GRAPH_TNS_SEED="${MPO_GRAPH_TNS_SEED:-20260653}"
export MPO_GRAPH_TNS_CENTER_RATIO="${MPO_GRAPH_TNS_CENTER_RATIO:-0.5}"
export MPO_GRAPH_TNS_MAX_BOND="${MPO_GRAPH_TNS_MAX_BOND:-256}"
export MPO_GRAPH_TNS_MPS_MAX_BOND="${MPO_GRAPH_TNS_MPS_MAX_BOND:-128}"
export MPO_GRAPH_TNS_CUTOFF="${MPO_GRAPH_TNS_CUTOFF:-0.05}"
export MPO_GRAPH_TNS_UNSWAP_THRESHOLD="${MPO_GRAPH_TNS_UNSWAP_THRESHOLD:-120000}"
export MPO_GRAPH_TNS_MAX_ITS="${MPO_GRAPH_TNS_MAX_ITS:-6}"
export MPO_GRAPH_TNS_SABRE_TRIALS="${MPO_GRAPH_TNS_SABRE_TRIALS:-32}"
export MPO_GRAPH_TNS_SAMPLES="${MPO_GRAPH_TNS_SAMPLES:-0}"
export MPO_GRAPH_TNS_GRAPH_MAX_CALLS="${MPO_GRAPH_TNS_GRAPH_MAX_CALLS:-4}"

bash jobs/run_mpo_graph_tns_veryhard_fast_cpu_array.slurm
