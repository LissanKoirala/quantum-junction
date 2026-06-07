#!/bin/bash
# Regenerate REPORT.md + distributions from current results, then commit & push.
# Safe to run repeatedly ("as you go along"). Commits only opus_combined work.
set -uo pipefail
ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
cd "$ROOT"
timeout 240 .venv/bin/python agent_work/opus_combined/make_report.py 2>&1 | tail -20
timeout 200 .venv/bin/python agent_work/opus_combined/collect.py >/dev/null 2>&1 || true
git add agent_work/opus_combined/ outputs/opus_combined/ 2>/dev/null
if git diff --cached --quiet; then
  echo "no changes to commit"
else
  git commit -q -m "Update opus cracker results + bitstring distributions ($(date -u +%Y-%m-%dT%H:%MZ))

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" && echo "committed"
  git pull --rebase -q origin opus-combined-cracker 2>/dev/null || true
  git push -q origin opus-combined-cracker 2>&1 | tail -3 && echo "pushed"
fi
