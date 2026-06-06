#!/bin/bash
#SBATCH --job-name=mpo_graph_tns_combined_rollup
#SBATCH --partition=interruptible_cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=outputs/mpo_graph_tns_combined/logs/%x-%j.out
#SBATCH --error=outputs/mpo_graph_tns_combined/logs/%x-%j.err

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

OUT_DIR="outputs/mpo_graph_tns_combined"
mkdir -p "$OUT_DIR"/logs

HARD_ROOT="/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/hard-problems"
for SOURCE_NAME in mpo_graph_tns_all mpo_graph_tns_param_probe mpo_graph_tns_veryhard_fast_cpu mpo_graph_tns_veryhard_fast_cpu_b mpo_graph_tns_veryhard_fast_cpu_c mpo_graph_tns_veryhard_fast_cpu_d mpo_graph_tns_veryhard_fast_cpu_e mpo_graph_tns_veryhard_fast_cpu_f mpo_graph_tns_veryhard_fast_cpu_g mpo_graph_tns_veryhard_fast_cpu_h mpo_graph_tns_gpu_retry mpo_graph_tns_marginal_fallback_cpu; do
  mkdir -p "outputs/$SOURCE_NAME"/{json,stats}
  cp -a "$HARD_ROOT/outputs/$SOURCE_NAME/json/." "outputs/$SOURCE_NAME/json/" 2>/dev/null || true
  cp -a "$HARD_ROOT/outputs/$SOURCE_NAME/stats/." "outputs/$SOURCE_NAME/stats/" 2>/dev/null || true
done

ROLLUP_MSG="$(
  "$VENV/bin/python" - "$OUT_DIR" <<'PY'
import collections
import json
import time
from pathlib import Path
import sys

out_dir = Path(sys.argv[1])
sources = {
    "cpu": Path("outputs/mpo_graph_tns_all_cpu/json"),
    "gpu": Path("outputs/mpo_graph_tns_all/json"),
    "gpu_retry": Path("outputs/mpo_graph_tns_gpu_retry/json"),
    "cpu_missing_retry": Path("outputs/mpo_graph_tns_missing_cpu/json"),
    "cpu_extra_retry": Path("outputs/mpo_graph_tns_extra_cpu/json"),
    "cpu_extra_retry_b": Path("outputs/mpo_graph_tns_extra_cpu_b/json"),
    "cpu_extra_retry_c": Path("outputs/mpo_graph_tns_extra_cpu_c/json"),
    "cpu_extra_retry_d": Path("outputs/mpo_graph_tns_extra_cpu_d/json"),
    "cpu_extra_retry_e": Path("outputs/mpo_graph_tns_extra_cpu_e/json"),
    "cpu_extra_retry_f": Path("outputs/mpo_graph_tns_extra_cpu_f/json"),
    "cpu_extra_retry_g": Path("outputs/mpo_graph_tns_extra_cpu_g/json"),
    "cpu_moderate_retry_h": Path("outputs/mpo_graph_tns_moderate_retry_h/json"),
    "cpu_moderate_retry_i": Path("outputs/mpo_graph_tns_moderate_retry_i/json"),
    "cpu_moderate_retry_j": Path("outputs/mpo_graph_tns_moderate_retry_j/json"),
    "cpu_moderate_retry_k": Path("outputs/mpo_graph_tns_moderate_retry_k/json"),
    "cpu_sample_top_postprocess": Path("outputs/mpo_graph_tns_sample_top_postprocess/json"),
    "cpu_marginal_fallback": Path("outputs/mpo_graph_tns_marginal_fallback_cpu/json"),
    "cpu_veryhard_fast": Path("outputs/mpo_graph_tns_veryhard_fast_cpu/json"),
    "cpu_veryhard_fast_b": Path("outputs/mpo_graph_tns_veryhard_fast_cpu_b/json"),
    "cpu_veryhard_fast_c": Path("outputs/mpo_graph_tns_veryhard_fast_cpu_c/json"),
    "cpu_veryhard_fast_d": Path("outputs/mpo_graph_tns_veryhard_fast_cpu_d/json"),
    "cpu_veryhard_fast_e": Path("outputs/mpo_graph_tns_veryhard_fast_cpu_e/json"),
    "cpu_veryhard_fast_f": Path("outputs/mpo_graph_tns_veryhard_fast_cpu_f/json"),
    "cpu_veryhard_fast_g": Path("outputs/mpo_graph_tns_veryhard_fast_cpu_g/json"),
    "cpu_veryhard_fast_h": Path("outputs/mpo_graph_tns_veryhard_fast_cpu_h/json"),
}
expected_paths = sorted(Path("challenges").glob("*/*.qasm"), key=lambda p: (p.parent.name, p.name))
expected = []
for path in expected_paths:
    stem = path.stem
    label = stem.removeprefix("challenge-")
    expected.append({"label": label, "qasm": str(path), "difficulty": path.parent.name})

rows_by_label = collections.defaultdict(list)
source_counts = {}
for source, directory in sources.items():
    rows = []
    for path in sorted(directory.glob("*.json")):
        try:
            row = json.loads(path.read_text())
        except Exception as exc:
            row = {"status": "unreadable", "error": str(exc), "output_json": str(path)}
        row["_source"] = source
        row["_json_path"] = str(path)
        label = row.get("challenge_label")
        if label:
            rows_by_label[str(label)].append(row)
        rows.append(row)
    source_counts[source] = {
        "json_outputs": len(rows),
        "status_counts": dict(collections.Counter(str(r.get("status")) for r in rows)),
        "validation_counts": dict(collections.Counter(str(r.get("validation", {}).get("status")) for r in rows)),
    }

def rank(row):
    status = row.get("status")
    validation = row.get("validation", {}).get("status")
    if status == "ok" and validation == "correct":
        return 0
    if status == "ok" and row.get("final_candidate_qiskit_order") and validation != "incorrect":
        return 1
    if status == "ok" and validation == "incorrect":
        return 4
    if status == "no_candidate":
        return 2
    if status == "started":
        return 3
    if status == "error":
        return 4
    return 5

combined = []
for item in expected:
    label = item["label"]
    rows = rows_by_label.get(label, [])
    best = sorted(rows, key=rank)[0] if rows else None
    combined.append({
        **item,
        "covered": bool(best),
        "best_source": best.get("_source") if best else None,
        "best_json": best.get("_json_path") if best else None,
        "best_status": best.get("status") if best else "missing",
        "best_validation": best.get("validation", {}).get("status") if best else None,
        "candidate": best.get("final_candidate_qiskit_order") if best else None,
        "total_seconds": best.get("total_seconds") if best else None,
        "all_attempts": [
            {
                "source": r.get("_source"),
                "json": r.get("_json_path"),
                "status": r.get("status"),
                "validation": r.get("validation", {}).get("status"),
                "error_type": r.get("error_type"),
                "seconds": r.get("total_seconds"),
            }
            for r in rows
        ],
    })

missing = [r["label"] for r in combined if r["best_status"] == "missing"]
not_ok = [r["label"] for r in combined if r["best_status"] not in {"ok"}]
errors = [r["label"] for r in combined if any(a["status"] == "error" for a in r["all_attempts"])]
known_correct = [r["label"] for r in combined if r["best_validation"] == "correct"]
known_incorrect = [r["label"] for r in combined if r["best_validation"] == "incorrect"]
with_candidate = [r["label"] for r in combined if r["candidate"]]

rollup = {
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "expected_challenges": len(expected),
    "source_counts": source_counts,
    "combined_status_counts": dict(collections.Counter(str(r["best_status"]) for r in combined)),
    "combined_validation_counts": dict(collections.Counter(str(r["best_validation"]) for r in combined)),
    "missing": missing,
    "not_ok": not_ok,
    "errors": errors,
    "known_correct": known_correct,
    "known_incorrect": known_incorrect,
    "with_candidate": with_candidate,
    "combined": combined,
}
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "ROLLUP.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n")

lines = [
    "# Peaked MPO graph+tree-TNS combined rollup",
    "",
    f"Generated: {rollup['generated_at']}",
    "",
    "| challenge | status | validation | source | candidate | json |",
    "| --- | --- | --- | --- | --- | --- |",
]
for row in combined:
    candidate = row["candidate"] or ""
    if candidate:
        candidate = f"`{candidate}`"
    lines.append(
        "| " + " | ".join([
            row["label"],
            str(row["best_status"]),
            str(row["best_validation"] or ""),
            str(row["best_source"] or ""),
            candidate,
            f"`{row['best_json']}`" if row["best_json"] else "",
        ]) + " |"
    )
(out_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n")

msg = (
    "mpo_graph_tns combined rollup: "
    f"{len(with_candidate)}/{len(expected)} candidates, "
    f"status_counts={rollup['combined_status_counts']}, "
    f"known_correct={len(known_correct)}, known_incorrect={len(known_incorrect)}, "
    f"missing={len(missing)}, errors={len(errors)}. "
    f"Summary: {out_dir / 'SUMMARY.md'}"
)
if missing or errors or known_incorrect:
    msg += f" Attention labels: {','.join((missing + errors + known_incorrect)[:20])}"
print(msg)
PY
)"

echo "$ROLLUP_MSG"
if command -v curl >/dev/null 2>&1; then
  curl -fsS \
    -H "Title: Quantum Junction" \
    -H "Tags: clipboard" \
    -d "$ROLLUP_MSG" \
    https://ntfy.sh/junction-q-33 || true
fi
