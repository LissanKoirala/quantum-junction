"""Definitive bug-isolation for the 24_13 failure. Run on Slurm (login node is saturated).

For 24_13 (fail) and 8_1 (control), compare to the EXACT peak:
  A. plain high-bond CircuitMPS of the RAW circuit (tests readout + bit ordering, no unswap)
  B. my engine on the RAW circuit (no snap, no consolidate)         (tests the unswap engine)
  C. my engine with snap+consolidate (the failing config)           (reproduces failure)
Each candidate is checked in all 4 orderings {raw, raw_rev, perm, perm_rev}.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction/peaked-circuit-simulation")
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
import crack
import quimb.tensor as qtn
from collections import Counter

KNOWN = {"24_13": "111110011111001011010001", "8_1": "10101101"}
PATHS = {"24_13": "challenges/easy/challenge-24_13.qasm",
         "8_1": "challenges/very easy/challenge-8_1.qasm"}
REPO = "/cephfs/volumes/hpc_data_usr/k23067196/4b836cf6-c724-4582-b3ee-c8bf7092b2fd/JUNCTION-HACKATHON/quantum-junction"


def exact_peak(path):
    qc = QuantumCircuit.from_qasm_file(path).remove_final_measurements(inplace=False)
    n = qc.num_qubits
    pr = Statevector.from_instruction(qc).probabilities()
    idx = int(np.argmax(pr))
    return format(idx, f"0{n}b"), float(pr[idx]), n


def orderings(bits, perm=None):
    o = {"raw": bits, "raw_rev": bits[::-1]}
    if perm is not None:
        pb = "".join(bits[i] for i in perm)
        o["perm"] = pb; o["perm_rev"] = pb[::-1]
    return o


def check(name, bits, known, perm=None):
    o = orderings(bits, perm)
    hits = [k for k, v in o.items() if v == known]
    print(f"    {name}: {'MATCH '+str(hits) if hits else 'no-match'}  ({o.get('perm_rev', o['raw'])})", flush=True)
    return bool(hits)


def plain_mps_peak(path, max_bond=4096):
    circ = qtn.Circuit.from_openqasm2_file(path)
    mps = circ.psi  # not an MPS necessarily; use sample on the circuit's TN state
    # Use quimb Circuit sampling
    samples = Counter("".join(str(b) for b in s) for s in circ.sample(2000))
    return samples.most_common(1)[0][0]


for tag in ["8_1", "24_13"]:
    path = os.path.join(REPO, PATHS[tag])
    known = KNOWN[tag]
    print(f"=== {tag} known={known} ===", flush=True)
    ep, epp, n = exact_peak(path)
    print(f"  EXACT peak={ep} p={epp:.3f} (sanity match_known={ep==known})", flush=True)

    try:
        pm = plain_mps_peak(path)
        check("A plain-MPS(raw)", pm, known)  # quimb sample order: check raw/rev
    except Exception as e:
        print(f"    A plain-MPS ERROR {e!r}", flush=True)

    try:
        rB = crack.crack(path, use_gpu=False, max_bond=4096, cutoff=1e-4, snap_tol=0.0,
                         consolidate=False, use_graph=True, sabre_trials=500, n_samples=2000,
                         time_budget=2400)
        sB = (rB.get("sample_orderings") or {}).get("raw")
        # reconstruct perm-based check from stored orderings
        print(f"    B engine(raw,nosnap,noconsol) conv={rB.get('converged')} bond={rB.get('mpo_max_bond')}", flush=True)
        for k, v in (rB.get("sample_orderings") or {}).items():
            if v == known:
                print(f"      B MATCH via {k}", flush=True)
        print(f"      B perm_rev={(rB.get('sample_orderings') or {}).get('perm_rev')}", flush=True)
    except Exception as e:
        print(f"    B engine ERROR {e!r}", flush=True)

    try:
        rC = crack.crack(path, use_gpu=False, max_bond=4096, cutoff=1e-4, snap_tol=1e-2,
                         consolidate=True, use_graph=True, sabre_trials=500, n_samples=2000,
                         time_budget=2400)
        print(f"    C engine(snap+consol) conv={rC.get('converged')} bond={rC.get('mpo_max_bond')} "
              f"perm_rev={(rC.get('sample_orderings') or {}).get('perm_rev')}", flush=True)
        for k, v in (rC.get("sample_orderings") or {}).items():
            if v == known:
                print(f"      C MATCH via {k}", flush=True)
    except Exception as e:
        print(f"    C engine ERROR {e!r}", flush=True)

print("DONE", flush=True)
