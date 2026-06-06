#!/bin/bash
#SBATCH --job-name=mpo_graph_tns_vhard_fast_g
#SBATCH --partition=interruptible_cpu
#SBATCH --array=4-7%3
#SBATCH --cpus-per-task=32
#SBATCH --mem=80G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/mpo_graph_tns_veryhard_fast_cpu_g/logs/%x-%A_%a.out
#SBATCH --error=outputs/mpo_graph_tns_veryhard_fast_cpu_g/logs/%x-%A_%a.err

set -euo pipefail

mkdir -p outputs/mpo_graph_tns_veryhard_fast_cpu_g/logs

export MPO_GRAPH_TNS_OUT_DIR="${MPO_GRAPH_TNS_OUT_DIR:-outputs/mpo_graph_tns_veryhard_fast_cpu_g}"
export MPO_GRAPH_TNS_SEED="${MPO_GRAPH_TNS_SEED:-20260647}"
export MPO_GRAPH_TNS_CENTER_RATIO="${MPO_GRAPH_TNS_CENTER_RATIO:-0.55}"
export MPO_GRAPH_TNS_MAX_BOND="${MPO_GRAPH_TNS_MAX_BOND:-768}"
export MPO_GRAPH_TNS_MPS_MAX_BOND="${MPO_GRAPH_TNS_MPS_MAX_BOND:-384}"
export MPO_GRAPH_TNS_CUTOFF="${MPO_GRAPH_TNS_CUTOFF:-0.0125}"
export MPO_GRAPH_TNS_UNSWAP_THRESHOLD="${MPO_GRAPH_TNS_UNSWAP_THRESHOLD:-200000}"
export MPO_GRAPH_TNS_MAX_ITS="${MPO_GRAPH_TNS_MAX_ITS:-10}"
export MPO_GRAPH_TNS_SABRE_TRIALS="${MPO_GRAPH_TNS_SABRE_TRIALS:-96}"
export MPO_GRAPH_TNS_SAMPLES="${MPO_GRAPH_TNS_SAMPLES:-512}"
export MPO_GRAPH_TNS_GRAPH_MAX_CALLS="${MPO_GRAPH_TNS_GRAPH_MAX_CALLS:-8}"

bash jobs/run_mpo_graph_tns_veryhard_fast_cpu_array.slurm
