#!/usr/bin/env zsh
set -u

cd /Users/ecemguvener/Desktop/quantum/quantum-junction

out="outputs/tree_tensor_sim/48_42_focus_unswap_bg_4242"
log="$out/logs/run.log"
donefile="$out/logs/done.exit"

mkdir -p "$out/logs"

MPLCONFIGDIR=/private/tmp/mplconfig \
  .venv/bin/python jobs/peaked_mpo_unswap_runner.py \
  --challenge-id 42 \
  --out-dir "$out" \
  --backend numpy \
  --max-bond 512 \
  --mps-max-bond 512 \
  --cutoff 0.002 \
  --unswap-threshold 1000000 \
  --early-stopping-gates 500 \
  --max-its 10 \
  --sabre-trials 64 \
  --samples 512 \
  --seed 4242 \
  > "$log" 2>&1

code=$?
printf "%s\n" "$code" > "$donefile"
exit "$code"
