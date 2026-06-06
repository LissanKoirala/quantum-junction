#!/bin/bash
#SBATCH --job-name=mpo_graph_tns_vhard_fast_h
#SBATCH --partition=interruptible_cpu
#SBATCH --array=2-7%6
#SBATCH --cpus-per-task=32
#SBATCH --mem=80G
#SBATCH --time=1-00:00:00
#SBATCH --output=outputs/mpo_graph_tns_veryhard_fast_cpu_h/logs/%x-%A_%a.out
#SBATCH --error=outputs/mpo_graph_tns_veryhard_fast_cpu_h/logs/%x-%A_%a.err

set -euo pipefail

mkdir -p outputs/mpo_graph_tns_veryhard_fast_cpu_h/logs

export MPO_GRAPH_TNS_OUT_DIR="${MPO_GRAPH_TNS_OUT_DIR:-outputs/mpo_graph_tns_veryhard_fast_cpu_h}"
export MPO_GRAPH_TNS_SEED="${MPO_GRAPH_TNS_SEED:-20260661}"
export MPO_GRAPH_TNS_CENTER_RATIO="${MPO_GRAPH_TNS_CENTER_RATIO:-0.35}"
export MPO_GRAPH_TNS_MAX_BOND="${MPO_GRAPH_TNS_MAX_BOND:-1024}"
export MPO_GRAPH_TNS_MPS_MAX_BOND="${MPO_GRAPH_TNS_MPS_MAX_BOND:-512}"
export MPO_GRAPH_TNS_CUTOFF="${MPO_GRAPH_TNS_CUTOFF:-0.02}"
export MPO_GRAPH_TNS_UNSWAP_THRESHOLD="${MPO_GRAPH_TNS_UNSWAP_THRESHOLD:-260000}"
export MPO_GRAPH_TNS_MAX_ITS="${MPO_GRAPH_TNS_MAX_ITS:-14}"
export MPO_GRAPH_TNS_SABRE_TRIALS="${MPO_GRAPH_TNS_SABRE_TRIALS:-160}"
export MPO_GRAPH_TNS_SAMPLES="${MPO_GRAPH_TNS_SAMPLES:-768}"
export MPO_GRAPH_TNS_GRAPH_MAX_CALLS="${MPO_GRAPH_TNS_GRAPH_MAX_CALLS:-12}"

bash jobs/run_mpo_graph_tns_veryhard_fast_cpu_array.slurm
