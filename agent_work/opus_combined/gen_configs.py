"""Generate JSONL config sweeps for the combined cracker Slurm arrays."""
import os, json

HERE = os.path.dirname(os.path.abspath(__file__))
CFGDIR = os.path.join(HERE, "configs")
os.makedirs(CFGDIR, exist_ok=True)


def write(name, rows):
    p = os.path.join(CFGDIR, name)
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"{p}: {len(rows)} configs")
    return p


# ---- GPU smoke: tiny known-answer circuit to confirm the A100 path runs e2e ----
write("smoke_gpu.jsonl", [
    {"challenge": "challenge-8_1.qasm", "label": "smoke_gpu",
     "use_gpu": True, "max_bond": 4096, "cutoff": 0.002, "snap_tol": 1e-2,
     "use_graph": True, "center_ratio": 0.5, "max_its": 12, "seed": 123,
     "sabre_trials": 200, "n_samples": 4000, "time_budget": 600},
])

# ---- VALIDATION (CPU): exact-confirmed <=28q + high-confidence easy 40-48q ----
# Confirms the pipeline converges and recovers/agrees at scale before spending GPU.
val_targets = [
    "challenge-24_13.qasm",   # exact: 111110011111001011010001
    "challenge-28_4.qasm",    # exact: 1111111000101010110110011111
    "challenge-40_7.qasm",    # quimb top 0.88
    "challenge-48_8.qasm",    # quimb top 0.70
]
val = []
for ch in val_targets:
    val.append({"challenge": ch, "label": "val_b4096_c0.002_snap",
                "use_gpu": False, "max_bond": 4096, "cutoff": 0.002,
                "snap_tol": 1e-2, "use_graph": True, "center_ratio": 0.5,
                "max_its": 12, "seed": 123, "sabre_trials": 1000, "n_samples": 4000,
                "time_budget": 7200})
write("validate_cpu.jsonl", val)


# ---- HARD TARGETS (GPU a100_80g): 37, 38, 40, 41 ----
hard = ["challenge-48_37.qasm", "challenge-56_38.qasm",
        "challenge-64_40.qasm", "challenge-64_41.qasm"]
rows = []
for ch in hard:
    # primary: snap on, bond 8192, cutoff 0.002, graph on
    rows.append({"challenge": ch, "label": "gpu_b8192_c0.002_snap_s123",
                 "use_gpu": True, "max_bond": 8192, "cutoff": 0.002,
                 "snap_tol": 1e-2, "use_graph": True, "center_ratio": 0.5,
                 "max_its": 16, "seed": 123, "sabre_trials": 1000, "n_samples": 8000,
                 "time_budget": 64800})
    # variant: no snap (isolate snapping's effect), same else
    rows.append({"challenge": ch, "label": "gpu_b8192_c0.002_nosnap_s123",
                 "use_gpu": True, "max_bond": 8192, "cutoff": 0.002,
                 "snap_tol": 0.0, "use_graph": True, "center_ratio": 0.5,
                 "max_its": 16, "seed": 123, "sabre_trials": 1000, "n_samples": 8000,
                 "time_budget": 64800})
    # variant: second seed for stability cross-check
    rows.append({"challenge": ch, "label": "gpu_b8192_c0.002_snap_s7",
                 "use_gpu": True, "max_bond": 8192, "cutoff": 0.002,
                 "snap_tol": 1e-2, "use_graph": True, "center_ratio": 0.5,
                 "max_its": 16, "seed": 7, "sabre_trials": 1000, "n_samples": 8000,
                 "time_budget": 64800})
write("hard_gpu.jsonl", rows)


# ---- VERY HARD (GPU): start with smallest (48_42); template transfers to rest ----
vhard = ["challenge-48_42.qasm", "challenge-56_43.qasm", "challenge-64_44.qasm",
         "challenge-72_45.qasm", "challenge-80_46.qasm", "challenge-88_47.qasm",
         "challenge-96_48.qasm", "challenge-104_49.qasm"]
vrows = []
for ch in vhard:
    # very_hard are 20k-37k gates: tighter cutoff to force completion, more graph calls
    vrows.append({"challenge": ch, "label": "gpu_b8192_c0.0125_snap_s123",
                  "use_gpu": True, "max_bond": 8192, "cutoff": 0.0125,
                  "snap_tol": 1e-2, "use_graph": True, "center_ratio": 0.5,
                  "max_its": 16, "seed": 123, "sabre_trials": 600, "n_samples": 8000,
                  "time_budget": 79200})
write("veryhard_gpu.jsonl", vrows)
