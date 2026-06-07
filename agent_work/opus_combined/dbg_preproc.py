"""Does snap / consolidate preprocessing change the EXACT peak? (<=28q only)"""
import sys, re, math
from fractions import Fraction
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from qiskit.transpiler.passes import Collect2qBlocks, ConsolidateBlocks
from qiskit.transpiler import PassManager

_RE = re.compile(r'\b(rx|ry|rz|rxx|ryy|rzz|rzx|p|u1|crx|cry|crz|cp)\(([^()]*)\)')
def snap(text, tol=1e-2, md=16):
    n=[0]
    def repl(m):
        try: v=float(eval(m.group(2),{"pi":math.pi,"__builtins__":{}},{}))
        except Exception: return m.group(0)
        fr=Fraction(v/math.pi).limit_denominator(md); ap=float(fr)*math.pi
        if abs(v-ap)<=tol: n[0]+=1; return f"{m.group(1)}({ap!r})"
        return m.group(0)
    return _RE.sub(repl,text),n[0]

import numpy as np
def peak(qc):
    qc=qc.remove_final_measurements(inplace=False)
    n=qc.num_qubits
    pr=Statevector.from_instruction(qc).probabilities()  # array over 2^n, index = qubit0 LSB
    idx=int(np.argmax(pr))
    b=format(idx, f"0{n}b")  # MSB-first = q_{n-1}..q_0  => counts order (rightmost=q0)
    return b, float(pr[idx])

KNOWN={"24_13":"111110011111001011010001","8_1":"10101101"}
for tag,path in [("24_13","challenges/easy/challenge-24_13.qasm"),
                 ("8_1","challenges/very easy/challenge-8_1.qasm")]:
    k=KNOWN[tag]; print(f"=== {tag} known={k} ===",flush=True)
    raw=open(path).read()
    qc=QuantumCircuit.from_qasm_str(raw)
    b,p=peak(qc); print(f"  raw         {b} p={p:.3f} match={b==k}",flush=True)
    txt,ns=snap(raw)
    qcs=QuantumCircuit.from_qasm_str(txt)
    b,p=peak(qcs); print(f"  snap({ns:4d})  {b} p={p:.3f} match={b==k}",flush=True)
    pm=PassManager([Collect2qBlocks(),ConsolidateBlocks(force_consolidate=True)])
    qcc=pm.run(qcs.remove_final_measurements(inplace=False))
    b,p=peak(qcc); print(f"  snap+consol {b} p={p:.3f} match={b==k}",flush=True)
print("DONE",flush=True)
