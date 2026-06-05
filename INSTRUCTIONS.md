Quantum Peak Challenge
Each circuit C, when given the zero state |0> as input, outputs a secret bitstring x with much higher probability than any other possible output.

In other words, the circuits are peaked. Your task is to find the location of that peak: the secret bitstring associated with each circuit C.

Note that these circuits were previously compressed using our compression engine.

Circuit Creation
Each challenge circuit is built in three stages:

Define the target peak pattern.
Hide it inside larger composed blocks.
Utilize our obfuscation engine to obfuscate the entire circuit.
1) Target peak pattern with RX(π)
We start from a desired peak bitstring x. An RX layer is constructed so that each qubit receives either:

RX(π), to flip that qubit relative to |0⟩
RX(0), to leave it unchanged
This gives a column of RX gates that encodes the target bit pattern.

2) Random blocks + inverse composition
Three random circuits are sampled: U₁, U₂, U₃. For each one, we explicitly compose it with its inverse:

Uᵢ Uᵢ† = I

So each pair is an identity. Between these identity pairs, we insert two RX-only layers, P₁ and P₂. The full circuit layout is:

C = U₁ U₁† P₁ U₂ U₂† P₂ U₃ U₃†

After this construction, C is passed through our obfuscation engine.

The layers P₁ and P₂ are chosen so that after rotation merging, their combined effect matches the target RX(π/0) column from step 1.

3) Obfuscation engine
The obfuscation engine is designed to conceal structural clues in the circuit by applying mostly unitary-preserving transformations, plus a small number of non-unitary-preserving ones*. Its purpose is to prevent compression pipelines from trivially collapsing the circuit into a single RX layer that reveals the peak bitstring, or reducing it to a low-entanglement stage that is easy to simulate.

* "Unitary-preserving" means rewrites that keep the same quantum evolution (same output probabilities up to global phase). "Non-unitary-preserving" means edits that may change the exact unitary but are used sparingly.

Circuit Organization
The levels range from very easy to very hard. As difficulty increases, peak probability is reduced, and the circuit structure becomes larger and more complex.

Rules
Submissions are accepted only when the bitstring matches the secret bitstring exactly.

Pay attention to bit order: the right-most bit corresponds to qubit 0.

Bit-Order Example

For a 4-qubit circuit, the bitstring 0101 means:

q0 = 1
q1 = 0
q2 = 1
q3 = 0
You may submit at most 10 files per problem per hour.

Each submission must include a short explanation (2-3 sentences) describing your approach.

All previous attempts are available under "My submissions".

Judging Criteria
The team that cracks the most circuits will not necessarily be the winner.

Final ranking will also consider how original and effective your cracking strategy is, including how well it generalizes to other peaked circuits, not just how many circuits you solved. This is intended to make the competition fairer, since a team with significantly more compute power could win primarily by brute-force resources.

Each problem is worth a certain number of points, which increases with both the difficulty and qubit number. You must also submit a Summary of your methods by email to david.karpuk@qmill.com, by the end of the hackathon, with the subject line "Quantum Hack Challenge Summary". The Summary should be 2-3 paragraphs broadly explaining the methods you used to solve the problems. These summaries will be worth a maximum of 1600 points, with more points awarded for originality and computational efficiency of your cracking strategies, how well the methods generalize across different problems, and potential for your methods to apply to de-obfuscating other types of obfuscated circuits. Your final score is the sum of the number of points you achieved on the problems plus the number of points awarded for the Summary.

Quick Tutorial (Qiskit)
You can solve easier instances by loading the QASM circuit, computing its statevector, and selecting the most likely output bitstring.

Important: this approach only works for a low number of qubits, because statevector simulation scales as 2^n in memory and runtime.

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

# 1) Load circuit from OpenQASM file
qasm_path = "path/to/circuit.qasm"
qc = QuantumCircuit.from_qasm_file(qasm_path)

# 2) Remove measurements (required for Statevector simulation)
qc_no_meas = qc.remove_final_measurements(inplace=False)

# 3) Compute statevector from the circuit acting on |0...0>
sv = Statevector.from_instruction(qc_no_meas)

# 4) Convert amplitudes to probabilities and get the peak bitstring
probs = sv.probabilities_dict()          # dict: bitstring -> probability
peak_bitstring = max(probs, key=probs.get)
peak_prob = probs[peak_bitstring]

print("Most likely bitstring:", peak_bitstring)
print("Peak probability:", peak_prob)
In Qiskit, bitstrings are reported with qubits ordered from high index to low index, so the right-most bit is qubit 0.

Larger Circuits: MPS Simulator (Qiskit Aer)
For circuits with a larger number of qubits, you can use the MPS (Matrix Product State) simulator.

With MPS, you typically choose:

Number of shots: more shots give a more stable estimate of the peak bitstring.
Bond dimension: controls approximation quality and memory/runtime cost.
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

# 1) Load QASM circuit
qasm_path = "path/to/circuit.qasm"
qc = QuantumCircuit.from_qasm_file(qasm_path)

# 2) Ensure we have measurements for shot-based sampling
qc.measure_all()

# 3) Configure MPS simulator
shots = 4096
bond_dim = 64  # try 32, 64, 128, ... (higher is usually more accurate)

sim = AerSimulator(
  method="matrix_product_state",
  matrix_product_state_max_bond_dimension=bond_dim,
)

# 4) Transpile + run
qc_t = transpile(qc, sim)
result = sim.run(qc_t, shots=shots).result()
counts = result.get_counts()

# 5) Most frequent bitstring as peak estimate
peak_bitstring = max(counts, key=counts.get)
peak_count = counts[peak_bitstring]
peak_prob_est = peak_count / shots

print("Estimated peak bitstring:", peak_bitstring)
print("Estimated peak probability:", peak_prob_est)
Practical tip: if results are unstable, increase shots first, then increase bond_dim.

For harder difficulty levels and larger qubit counts, simulation cost can grow quickly, to the point where brute force simulation becomes impractical within hackathon time limits. At that stage, you should rely on smarter cracking strategies that exploit circuit structure instead of only increasing compute. Please consult the references for more advanced techniques.

References
Gharibyan et al. Heuristic Quantum Advantage with Peaked Circuits, 2025: https://arxiv.org/abs/2510.25838
Kremer and Dupuis. Efficient Classical Simulation of Heuristic Peaked Quantum Circuits, 2025: https://arxiv.org/abs/2604.21908
Repo: https://github.com/d-kremer/peaked-circuit-simulation
Rudolph and Tindall. Simulating and Sampling from Quantum Circuits with 2D Tensor Networks, 2025: https://arxiv.org/abs/2507.11424
Repo: https://github.com/JoeyT1994/TensorNetworkQuantumSimulator.jl?tab=readme-ov-file
