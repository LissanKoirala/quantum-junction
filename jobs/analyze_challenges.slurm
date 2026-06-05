#!/usr/bin/env bash
#SBATCH --job-name=qj-analyze-qasm
#SBATCH --partition=interruptible_cpu
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --output=slurm/%x-%j.out

set -euo pipefail

cd /cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction
export PYTHONUNBUFFERED=1

.venv/bin/python - <<'PY'
from __future__ import annotations

from collections import Counter, defaultdict
from math import gcd, pi
from pathlib import Path
import json
import re
import statistics as stats

root = Path("challenges")
out_dir = Path("analysis")
out_dir.mkdir(exist_ok=True)

gate_re = re.compile(r"^([a-zA-Z][a-zA-Z0-9_]*)\s*(?:\(([^)]*)\))?\s+(.*);$")
q_re = re.compile(r"q\[(\d+)\]")
qreg_re = re.compile(r"qreg\s+q\[(\d+)\];")
name_re = re.compile(r"challenge-(\d+)_(\d+)\.qasm$")

def parse_angle(expr: str | None):
    if not expr:
        return None
    expr = expr.replace(" ", "")
    allowed = {"pi": pi}
    try:
        return float(eval(expr, {"__builtins__": {}}, allowed))
    except Exception:
        return None

def nearest_pi_fraction(x: float, max_den: int = 16):
    if x is None:
        return None
    y = x / pi
    best = None
    for den in range(1, max_den + 1):
        num = round(y * den)
        err = abs(y - num / den)
        if best is None or err < best[0]:
            best = (err, num, den)
    err, num, den = best
    g = gcd(abs(num), den)
    return err, num // g, den // g

rows = []
global_angles = Counter()
global_ops = Counter()
pair_counts_by_file = {}
opseq_by_file = {}
angle_errors_by_file = {}
per_diff = defaultdict(list)

for p in sorted(root.glob("*/*.qasm")):
    text = p.read_text()
    qreg = qreg_re.search(text)
    n = int(qreg.group(1))
    m = name_re.search(p.name)
    challenge_n = int(m.group(1)) if m else n
    challenge_id = int(m.group(2)) if m else -1
    ops = Counter()
    pairs = Counter()
    per_qubit_1q = [0] * n
    per_qubit_cx_touch = [0] * n
    per_qubit_swap_touch = [0] * n
    first_entangling_at = None
    last_entangling_at = None
    swap_positions = []
    angle_exactish = 0
    angle_noisy = 0
    angle_values = []
    pi_fracs = Counter()
    opseq = []
    gates = 0

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("OPENQASM", "include", "qreg", "creg", "measure", "barrier")):
            continue
        mm = gate_re.match(line)
        if not mm:
            continue
        op, angle_expr, args = mm.groups()
        qs = list(map(int, q_re.findall(args)))
        gates += 1
        ops[op] += 1
        global_ops[op] += 1
        opseq.append(op)
        ang = parse_angle(angle_expr)
        if ang is not None:
            frac = nearest_pi_fraction(ang, 16)
            if frac:
                err, num, den = frac
                if err < 1e-7:
                    angle_exactish += 1
                    pi_fracs[f"{num}/{den}"] += 1
                    global_angles[f"{num}/{den}"] += 1
                else:
                    angle_noisy += 1
                angle_values.append(ang)
        if op in {"cx", "swap"} and len(qs) == 2:
            a, b = qs
            if a > b:
                a, b = b, a
            pairs[(a, b)] += 1
            if first_entangling_at is None:
                first_entangling_at = gates
            last_entangling_at = gates
            if op == "swap":
                swap_positions.append(gates)
                per_qubit_swap_touch[qs[0]] += 1
                per_qubit_swap_touch[qs[1]] += 1
            else:
                per_qubit_cx_touch[qs[0]] += 1
                per_qubit_cx_touch[qs[1]] += 1
        elif len(qs) == 1:
            per_qubit_1q[qs[0]] += 1

    repeated_pairs = sum(1 for c in pairs.values() if c > 1)
    rows.append({
        "path": str(p),
        "difficulty": p.parent.name,
        "file": p.name,
        "challenge_n": challenge_n,
        "challenge_id": challenge_id,
        "qreg": n,
        "gates": gates,
        **{f"op_{k}": ops[k] for k in sorted(set(global_ops) | {"rx", "rz", "cx", "swap"})},
        "first_entangling_gate_index": first_entangling_at,
        "last_entangling_gate_index": last_entangling_at,
        "leading_1q_gates": (first_entangling_at - 1) if first_entangling_at else gates,
        "trailing_after_last_entangling": (gates - last_entangling_at) if last_entangling_at else 0,
        "unique_entangling_pairs": len(pairs),
        "repeated_entangling_pairs": repeated_pairs,
        "max_pair_repetitions": max(pairs.values()) if pairs else 0,
        "swap_count": ops["swap"],
        "swap_positions": swap_positions,
        "qubits_touched_by_cx": sum(1 for c in per_qubit_cx_touch if c),
        "qubits_touched_by_swap": sum(1 for c in per_qubit_swap_touch if c),
        "angle_exactish_pi_fraction": angle_exactish,
        "angle_noisy": angle_noisy,
        "top_pi_fractions": pi_fracs.most_common(8),
        "oneq_min": min(per_qubit_1q),
        "oneq_max": max(per_qubit_1q),
        "cx_touch_min": min(per_qubit_cx_touch),
        "cx_touch_max": max(per_qubit_cx_touch),
    })
    per_diff[p.parent.name].append(rows[-1])
    pair_counts_by_file[str(p)] = {f"{a}-{b}": c for (a, b), c in pairs.most_common()}
    opseq_by_file[str(p)] = opseq
    angle_errors_by_file[str(p)] = {
        "exactish": angle_exactish,
        "noisy": angle_noisy,
        "top_pi_fractions": pi_fracs.most_common(20),
    }

summary = {}
for diff, rs in sorted(per_diff.items()):
    def mean(key):
        return sum(r[key] for r in rs) / len(rs)
    summary[diff] = {
        "files": len(rs),
        "qubits": [min(r["qreg"] for r in rs), max(r["qreg"] for r in rs)],
        "gates_mean": mean("gates"),
        "gates_min_max": [min(r["gates"] for r in rs), max(r["gates"] for r in rs)],
        "cx_mean": mean("op_cx"),
        "rx_mean": mean("op_rx"),
        "rz_mean": mean("op_rz"),
        "swap_total": sum(r["swap_count"] for r in rs),
        "leading_1q_mean": mean("leading_1q_gates"),
        "trailing_after_last_entangling_mean": mean("trailing_after_last_entangling"),
        "unique_pairs_mean": mean("unique_entangling_pairs"),
        "exactish_angle_fraction": (
            sum(r["angle_exactish_pi_fraction"] for r in rs)
            / max(1, sum(r["angle_exactish_pi_fraction"] + r["angle_noisy"] for r in rs))
        ),
    }

with (out_dir / "challenge_static_summary.json").open("w") as f:
    json.dump({"summary": summary, "rows": rows, "global_ops": global_ops, "global_pi_fractions": global_angles.most_common(30)}, f, indent=2)

print("DIFFICULTY SUMMARY")
for diff, s in summary.items():
    print(diff, s)

print("\nALL FILES")
for r in sorted(rows, key=lambda x: (x["difficulty"], x["challenge_id"])):
    print(
        f"{r['difficulty']:12s} {r['file']:24s} q={r['qreg']:3d} gates={r['gates']:5d} "
        f"cx={r['op_cx']:4d} rx={r['op_rx']:4d} rz={r['op_rz']:4d} sw={r['swap_count']:2d} "
        f"lead1q={r['leading_1q_gates']:3d} trail={r['trailing_after_last_entangling']:3d} "
        f"pairs={r['unique_entangling_pairs']:4d} exact_angles={r['angle_exactish_pi_fraction']:4d} noisy_angles={r['angle_noisy']:4d}"
    )

print("\nGLOBAL OPS", dict(global_ops))
print("GLOBAL TOP PI FRACTIONS", global_angles.most_common(20))

print("\nSWAPS")
for r in rows:
    if r["swap_count"]:
        norm = [round(x / r["gates"], 3) for x in r["swap_positions"][:12]]
        extra = "..." if len(r["swap_positions"]) > 12 else ""
        print(f"{r['path']}: swaps={r['swap_count']} positions_frac={norm}{extra}")
PY
