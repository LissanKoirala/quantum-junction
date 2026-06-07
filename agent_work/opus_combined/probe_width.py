"""Feasibility probe: how hard is it to *exactly contract* the amplitude TN <x|C|0>
for the unsolved targets?  We don't contract — we only optimize the contraction
path (cheap) and report the contraction width W (=log2 of largest intermediate
tensor) and estimated FLOPs.  W<=~30 => exact amplitude eval is GPU-feasible, which
unlocks amplitude-guided peak search.  Login-node safe (path search only)."""
import os, sys, json, time
os.environ.setdefault("OMP_NUM_THREADS", "8")
import quimb.tensor as qtn
import cotengra as ctg

REPO = "/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
TARGETS = sys.argv[1:] or [
    "challenges/hard/challenge-48_37.qasm",
    "challenges/hard/challenge-64_41.qasm",
    "challenges/very_hard/challenge-48_42.qasm",
]

def probe(relpath, max_time=90):
    path = os.path.join(REPO, relpath)
    t0 = time.time()
    circ = qtn.Circuit.from_openqasm2_file(path)
    n = circ.N
    ngate = len(circ.gates)
    x = "0" * n  # amplitude <0..0|C|0..0>; structure-independent of which x for width
    opt = ctg.HyperOptimizer(
        methods=["greedy", "kahypar"],
        max_repeats=64,
        max_time=max_time,
        parallel=False,
        progbar=False,
        minimize="flops",
    )
    info = circ.amplitude_rehearse(b=x, optimize=opt, simplify_sequence="ADCRS")
    tree = info["tree"]
    W = float(tree.contraction_width())   # log2 of largest intermediate
    C = float(tree.contraction_cost())    # number of scalar mults
    res = {
        "challenge": os.path.basename(relpath),
        "n_qubits": n,
        "n_gates_quimb": ngate,
        "contraction_width_log2": round(W, 2),
        "largest_tensor_bytes_est": 16 * (2 ** W),
        "contraction_cost_flops_log10": round(__import__("math").log10(C + 1), 2),
        "path_search_seconds": round(time.time() - t0, 1),
    }
    return res

if __name__ == "__main__":
    out = []
    for t in TARGETS:
        try:
            r = probe(t)
        except Exception as e:
            r = {"challenge": os.path.basename(t), "error": repr(e)[:300]}
        print(json.dumps(r))
        sys.stdout.flush()
        out.append(r)
    os.makedirs(os.path.join(REPO, "agent_work/opus_combined"), exist_ok=True)
    with open(os.path.join(REPO, "agent_work/opus_combined/probe_width.json"), "w") as f:
        json.dump(out, f, indent=2)
