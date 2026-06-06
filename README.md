# quantum-junction

The Summary should be 2-3 paragraphs broadly explaining the methods you used to solve the problems. These summaries will be worth a maximum of 1600 points, with more points awarded for originality and computational efficiency of your cracking strategies, how well the methods generalize across different problems, and potential for your methods to apply to de-obfuscating other types of obfuscated circuits. Your final score is the sum of the number of points you achieved on the problems plus the number of points awarded for the Summary.
Workflow.

Summaries:

We first used Qiskit statevector simulation for smaller circuits. This worked across the lower-qubit challenges below 28 qubits, but could not scale further because the memory cost grows exponentially with qubit number.

For larger circuits, we moved to MPS simulation. MPS stores the quantum state in a compressed tensor-network form, scaling roughly as O(nχ2) in memory for n qubits and bond dimension χ, rather than O(2n). We started with 4096 shots and bond dimension 32, then increased to 64 when needed. This worked for moderate circuits, but failed once the circuits required a larger bond dimension.

We then used ideas from the Kremer–Dupuis paper, which exploit structure in the circuit rather than simply evolving the state from the beginning. The obfuscation circuit C creates apparent or “fake” entanglement, but this structure can sometimes be simplified using MPO/TNO-based methods. Our pipeline inspected the failed circuits and selected the best of the 3 papers presented in the paper: Low-Bond MPS with Bitstring Distillation, Tensor Network Operator (TNO) Contraction and MPO Iterative Cancellation with Unswapping. We did this before any simulation rather than trial and error for computational efficiency.

When these methods also failed on harder instances, we tried a 2D tensor-network approach. This worked well on moderate cases and appeared more general, but it still did not fully solve the hardest circuits. For the hardest cases, we then moved to a new approach developed by Kameron.







