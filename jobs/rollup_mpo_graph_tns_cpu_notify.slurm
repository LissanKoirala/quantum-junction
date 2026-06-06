#!/bin/bash
#SBATCH --job-name=mpo_graph_tns_cpu_rollup
#SBATCH --partition=interruptible_cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=outputs/mpo_graph_tns_all_cpu/logs/%x-%j.out
#SBATCH --error=outputs/mpo_graph_tns_all_cpu/logs/%x-%j.err

set -euo pipefail

ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/klalee-graph"
FALLBACK_ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
cd "$ROOT"

if [[ -d "$ROOT/.venv" ]]; then
  VENV="$ROOT/.venv"
else
  VENV="$FALLBACK_ROOT/.venv"
fi
source "$VENV/bin/activate"

export PYTHONUNBUFFERED=1
export MPLBACKEND=Agg
export PYTHONPATH="$ROOT/peaked-circuit-simulation:${PYTHONPATH:-}"

OUT_DIR="outputs/mpo_graph_tns_all_cpu"
mkdir -p "$OUT_DIR"/{json,stats,logs}

"$VENV/bin/python" jobs/peaked_mpo_graph_tns_runner.py \
  --out-dir "$OUT_DIR" \
  --summarize \
  --summary-title "Peaked MPO graph+tree-TNS all challenges CPU"

ROLLUP_MSG="$(
  "$VENV/bin/python" - "$OUT_DIR" <<'PY'
import collections
import json
import time
from pathlib import Path
import sys

out_dir = Path(sys.argv[1])
expected = sorted(Path("challenges").glob("*/*.qasm"), key=lambda p: (p.parent.name, p.name))
rows = []
for path in sorted((out_dir / "json").glob("*.json")):
    try:
        rows.append(json.loads(path.read_text()))
    except Exception:
        pass

status = collections.Counter(str(r.get("status", "missing")) for r in rows)
validation = collections.Counter(str(r.get("validation", {}).get("status", "")) for r in rows)
graph_events = sum(len(r.get("graph_ordering_events", [])) for r in rows)
accepted_graph_events = sum(
    1
    for r in rows
    for event in r.get("graph_ordering_events", [])
    if event.get("accepted")
)
missing = max(0, len(expected) - len(rows))
completed = len(rows)
ok = status.get("ok", 0)
errors = status.get("error", 0)
no_candidate = status.get("no_candidate", 0)
known_correct = validation.get("correct", 0)
known_incorrect = validation.get("incorrect", 0)

rollup = {
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "expected_challenges": len(expected),
    "json_outputs": completed,
    "missing_outputs": missing,
    "status_counts": dict(status),
    "validation_counts": dict(validation),
    "graph_ordering_events": graph_events,
    "accepted_graph_ordering_events": accepted_graph_events,
    "summary_md": str(out_dir / "SUMMARY.md"),
}
(out_dir / "ROLLUP.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n")

print(
    "mpo_graph_tns CPU rollup: "
    f"{completed}/{len(expected)} outputs, ok={ok}, errors={errors}, "
    f"no_candidate={no_candidate}, missing={missing}, "
    f"known_correct={known_correct}, known_incorrect={known_incorrect}, "
    f"accepted_graph_ordering={accepted_graph_events}/{graph_events}. "
    f"Summary: {out_dir / 'SUMMARY.md'}"
)
PY
)"

echo "$ROLLUP_MSG"
if command -v curl >/dev/null 2>&1; then
  curl -fsS \
    -H "Title: Quantum Junction" \
    -H "Tags: checkered_flag" \
    -d "$ROLLUP_MSG" \
    https://ntfy.sh/junction-q-33 || true
fi
