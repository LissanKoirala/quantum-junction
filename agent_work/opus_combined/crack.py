"""
Combined peaked-circuit cracker:  Snap -> Consolidate -> MPO unswap-to-convergence
-> Z-sign / sample readout.

Fuses the validated Kremer-Dupuis MPO-unswap engine (peaked-circuit-simulation/)
with the angle-snapping preconditioner (agent_work/algebraic_simplify) and a
convergence-aware driver that reports remaining (unabsorbed) layers as the trust
gate -- the metric prior runs ignored.

Bit order: challenge convention is counts-order, right-most bit = qubit 0.
We emit candidates in all 4 orderings {raw, reversed, permuted, permuted-reversed}
and let validation against known answers pick the right one.
"""
import sys, os, json, math, time, argparse, re
from fractions import Fraction
from collections import Counter
import numpy as np

REPO = "/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"
PCS = os.path.join(REPO, "peaked-circuit-simulation")
if PCS not in sys.path:
    sys.path.insert(0, PCS)

# --- self-contained angle-snapping preconditioner ---
# Snap any rotation angle within `tol` of a denom<=max_den multiple of pi to that
# exact multiple; leave genuine off-grid angles (the real U/P rotations) untouched.
_ANGLE_RE = re.compile(r'\b(rx|ry|rz|rxx|ryy|rzz|rzx|p|u1|crx|cry|crz|cp)\(([^()]*)\)')

def _eval_angle(expr):
    try:
        return float(eval(expr, {"pi": math.pi, "__builtins__": {}}, {}))
    except Exception:
        return None

def snap_qasm_text(text, tol=1e-2, max_den=16):
    cnt = {"n": 0}
    def repl(m):
        gate, expr = m.group(1), m.group(2)
        v = _eval_angle(expr)
        if v is None:
            return m.group(0)
        frac = Fraction(v / math.pi).limit_denominator(max_den)
        approx = float(frac) * math.pi
        if abs(v - approx) <= tol:
            cnt["n"] += 1
            return f"{gate}({approx!r})"
        return m.group(0)
    return _ANGLE_RE.sub(repl, text), cnt["n"]

from qiskit import QuantumCircuit
from qiskit.transpiler.passes import Collect2qBlocks, ConsolidateBlocks
from qiskit.transpiler import PassManager

import unswap as U
import unswap_graph as UG
from utils import extract_bitstring, to_backend_cuda
import crack_engine


def load_circuit(qasm_path, snap_tol=1e-2, max_den=16, consolidate=True):
    text = open(qasm_path).read()
    snapped = 0
    if snap_tol and snap_tol > 0:
        text, snapped = snap_qasm_text(text, tol=snap_tol, max_den=max_den)
    qc = QuantumCircuit.from_qasm_str(text)
    qc = qc.remove_final_measurements(inplace=False)
    n = qc.num_qubits
    if consolidate:
        pm = PassManager([Collect2qBlocks(), ConsolidateBlocks(force_consolidate=True)])
        qc = pm.run(qc)
    return qc, snapped, n


def _orderings(bits, perm):
    """Return the 4 candidate orderings for a site-order bitstring `bits`."""
    perm_bits = "".join(bits[i] for i in perm)
    return {
        "raw": bits,
        "raw_rev": bits[::-1],
        "perm": perm_bits,
        "perm_rev": perm_bits[::-1],
    }


def crack(qasm_path, use_gpu=False, max_bond=8192, cutoff=0.002,
          unswap_threshold=1e6, center_ratio=0.5, max_its=20, seed=123,
          snap_tol=1e-2, consolidate=True, use_graph=True, n_samples=2000,
          sabre_trials=10000, readout_max_bond=None, mps_cutoff=None,
          time_budget=None, stall_patience=2):
    t0 = time.perf_counter()
    to_backend = to_backend_cuda if use_gpu else None
    if readout_max_bond is None:
        readout_max_bond = max_bond
    if mps_cutoff is None:
        mps_cutoff = cutoff

    qc, snapped, n = load_circuit(qasm_path, snap_tol=snap_tol, consolidate=consolidate)
    n_ops_after = int(sum(v for k, v in qc.count_ops().items() if k not in ("barrier", "measure")))

    mpo, layers_left, layers_right, stats, info = crack_engine.compress_to_convergence(
        qc, max_bond=max_bond, cutoff=cutoff, soft_elems=unswap_threshold,
        center_ratio=center_ratio, max_its=max_its, seed=seed, to_backend=to_backend,
        sabre_trials=sabre_trials, hows=("both", "left", "right"),
        time_budget=time_budget, use_graph=use_graph, stall_patience=stall_patience)
    t_comp = info["compress_seconds"]

    rem_left = max(0, len(layers_left) - 2)
    rem_right = max(0, len(layers_right) - 2)
    remaining_layers = info["remaining_layers"]
    mpo_max_bond = int(mpo.max_bond())

    # --- readout: build final MPS ---
    t_read0 = time.perf_counter()
    mps, perm = U.mpo_to_mps(mpo, layers_left[:-2], layers_right,
                             max_bond=readout_max_bond, cutoff=mps_cutoff,
                             to_backend=to_backend)
    perm = list(perm)
    t_read = time.perf_counter() - t_read0

    out = {
        "challenge": os.path.basename(qasm_path),
        "n_qubits": n,
        "n_ops_after_precond": n_ops_after,
        "snapped_gates": snapped,
        "params": {"max_bond": max_bond, "cutoff": cutoff, "unswap_threshold": unswap_threshold,
                   "center_ratio": center_ratio, "max_its": max_its, "seed": seed,
                   "snap_tol": snap_tol, "consolidate": consolidate, "use_graph": use_graph,
                   "use_gpu": use_gpu, "sabre_trials": sabre_trials},
        "converged": info["converged"],
        "stopped_reason": info["stopped_reason"],
        "remaining_layers": remaining_layers,
        "remaining_left": rem_left, "remaining_right": rem_right,
        "forced_absorptions": info["forced_absorptions"],
        "graph_ordering_calls": info["graph_calls"],
        "max_bond_seen": info["max_bond_seen"],
        "mpo_max_bond": mpo_max_bond,
        "compress_seconds": round(t_comp, 1),
        "readout_seconds": round(t_read, 1),
    }

    # --- sampling readout ---
    def to_perm_rev(bits):
        return ("".join(bits[i] for i in perm))[::-1]
    try:
        raw = [p for p, _ in list(mps.sample(n_samples))]
        samples = ["".join(str(int(b)) for b in bs) for bs in raw]
        c = Counter(samples)
        top, topcount = c.most_common(1)[0]
        out["sample_top_fraction"] = topcount / len(samples)
        out["sample_distinct"] = len(c)
        out["sample_orderings"] = _orderings(top, perm)
        out["n_samples"] = len(samples)
        # full bitstring probability distribution (top-K), in challenge perm_rev order
        out["sample_distribution"] = [
            {"bitstring": to_perm_rev(s), "count": int(n_), "prob": n_ / len(samples)}
            for s, n_ in c.most_common(64)
        ]
    except Exception as e:
        out["sample_error"] = repr(e)[:300]

    # --- marginal (Z-sign) readout ---
    try:
        pred_bs, p0s = extract_bitstring(mps)
        margins = [abs(float(p) - 0.5) for p in p0s]
        out["marginal_orderings"] = _orderings(pred_bs, perm)
        out["marginal_min_margin"] = float(min(margins))
        out["marginal_mean_margin"] = float(np.mean(margins))
        out["marginal_undecided"] = int(sum(1 for m in margins if m < 0.05))
        out["marginal_p0s"] = [round(float(p), 4) for p in p0s]
        # per-qubit P(bit=1) in challenge order (qubit n-1 .. qubit 0), i.e. perm_rev order
        p1_site = [1.0 - float(p) for p in p0s]
        out["marginal_p1_challenge_order"] = [round(p1_site[perm[i]], 4)
                                              for i in range(len(perm))][::-1]
    except Exception as e:
        out["marginal_error"] = repr(e)[:300]

    out["total_seconds"] = round(time.perf_counter() - t0, 1)
    return out


KNOWN = {
    "challenge-8_1.qasm": "10101101",
    "challenge-8_11.qasm": "01001110",
    "challenge-8_27.qasm": "11001001",
    "challenge-16_2.qasm": "1010101011001000",
    "challenge-16_12.qasm": "1111000101101011",
    "challenge-16_28.qasm": "1101001111011100",
    "challenge-24_3.qasm": "011110010000101010001000",
    "challenge-24_13.qasm": "111110011111001011010001",
    "challenge-24_29.qasm": "110100010111100001001001",
    "challenge-28_4.qasm": "1111111000101010110110011111",
}


def check_known(out):
    name = out["challenge"]
    if name not in KNOWN:
        return None
    ans = KNOWN[name]
    hits = {}
    for kind in ("sample_orderings", "marginal_orderings"):
        for ordname, bits in out.get(kind, {}).items():
            if bits == ans:
                hits[f"{kind}:{ordname}"] = True
    return {"known_answer": ans, "matches": hits, "solved": len(hits) > 0}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("qasm")
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--max-bond", type=int, default=8192)
    ap.add_argument("--cutoff", type=float, default=0.002)
    ap.add_argument("--unswap-threshold", type=float, default=1e6)
    ap.add_argument("--center-ratio", type=float, default=0.5)
    ap.add_argument("--max-its", type=int, default=20)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--snap-tol", type=float, default=1e-2)
    ap.add_argument("--no-consolidate", action="store_true")
    ap.add_argument("--no-graph", action="store_true")
    ap.add_argument("--n-samples", type=int, default=2000)
    ap.add_argument("--sabre-trials", type=int, default=10000)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    res = crack(a.qasm, use_gpu=a.gpu, max_bond=a.max_bond, cutoff=a.cutoff,
                unswap_threshold=a.unswap_threshold, center_ratio=a.center_ratio,
                max_its=a.max_its, seed=a.seed, snap_tol=a.snap_tol,
                consolidate=not a.no_consolidate, use_graph=not a.no_graph,
                n_samples=a.n_samples, sabre_trials=a.sabre_trials)
    chk = check_known(res)
    if chk:
        res["validation"] = chk
    print(json.dumps(res, indent=2))
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        with open(a.out, "w") as f:
            json.dump(res, f, indent=2)
