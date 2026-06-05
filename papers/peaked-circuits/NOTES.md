# Peaked-Circuit Paper Notes

Downloaded from the references in `INSTRUCTIONS.md`.

## Files

- `2510.25838-heuristic-quantum-advantage-peaked-circuits.pdf`
  - arXiv: https://arxiv.org/abs/2510.25838
  - Main construction paper for HQAP-style peaked circuits.
- `2604.21908-efficient-classical-simulation-peaked-quantum-circuits.pdf`
  - arXiv: https://arxiv.org/abs/2604.21908
  - Directly relevant classical attack paper. The local `peaked-circuit-simulation/` repo matches this method.
- `2507.11424-simulating-sampling-2d-tensor-networks.pdf`
  - arXiv: https://arxiv.org/abs/2507.11424
  - General 2D tensor-network simulation/sampling reference.

Each PDF also has a `.txt` file extracted with `pdftotext -layout` for local search.

## Solver-Relevant Takeaways

The challenge instructions describe circuits built from identity blocks plus RX-only peak layers. This is not exactly the same as the full HQAP construction in the first paper, but the useful shared structure is the mirrored identity content: the circuit is peaked because large parts are designed to cancel.

The basic attacks from the first paper are:

- exact statevector for small qubit counts;
- MPS or tensor-network simulation followed by samples or one-qubit marginals;
- marginal/majority vote recovery, where each bit is inferred from the sign of an estimated `Z_i` expectation or from sample counts;
- structure attacks that try to undo hidden mirror/permutation structure rather than simulate the full circuit naively.

The most actionable paper is Kremer-Dupuis. Their method splits the circuit near the midpoint, initializes an identity Matrix Product Operator, and absorbs layers from both sides so mirrored structure cancels inside the MPO. When swap/permutation structure inflates bonds, they greedily apply "unswapping" operations that reduce MPO bond dimensions, then rewire the remaining circuit and continue.

Important implementation details from that paper:

- transpile or otherwise arrange the circuit into a 1D/linear connectivity form before MPO contraction;
- absorb left and right layers adaptively, choosing the side that keeps the MPO smaller;
- trigger unswapping when MPO tensor size exceeds a threshold;
- test nearest-neighbor swaps on left, right, or both sides of the MPO;
- parallelize swap tests by even/odd non-overlapping bonds;
- typical reported parameters were cutoff about `2e-3`, max bond `8192`, unswap threshold `1e6`, max unswap iterations `20`;
- after full contraction, apply the MPO to `|0...0>` and sample the resulting MPS to recover the peak.

For this repo, the likely plan is:

1. Use exact statevector only for the smallest easy circuits if dependencies are available.
2. Use MPS sampling/marginal voting as a fast first pass for easy/moderate circuits.
3. For hard circuits, prioritize the local `peaked-circuit-simulation/unswap.py` MPO cancellation approach once `qiskit`, `quimb`, `qiskit-quimb`, and `torch` are installed.
4. Treat bit order carefully: Qiskit-style output strings have `q[0]` as the right-most bit.

The Rudolph-Tindall paper is less directly targeted at these all-to-all QASM challenges, but it is useful background for controllable tensor-network sampling. Its key point is to match the tensor-network geometry to the circuit/processor geometry and use boundary-MPS contraction to sample and verify sample quality with probability-ratio or KL-style checks.
