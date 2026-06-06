# Quantum Peak Method Selector

This workspace contains a small helper for the QMill/Junction peaked-circuit challenge.
It does not try to brute-force every circuit. Instead, it inspects `.qasm` files and
recommends which of the three methods from Kremer and Dupuis is most worth trying:

1. Low-bond MPS with bitstring distillation
2. Tensor Network Operator midpoint contraction
3. MPO iterative cancellation with unswapping

The goal is to help the team explain *why* a method was chosen for a circuit before
spending time or compute on it.

## What It Looks At

The script parses QASM directly, without Qiskit, and measures:

- number of qubits and operations
- `rx`, `rz`, `cx`, and `swap` counts
- approximate circuit depth
- entangling graph density
- repeated two-qubit pairs, which can hint at inverse/mirror blocks
- leading and trailing one-qubit layers, which can hint at obfuscation dressing
- angle-grid clues, such as angles close to simple fractions of `pi`

It also tells you whether exact statevector simulation should be used as a baseline.
That baseline is not one of the three paper methods, but it is still the right first
check for small circuits.

## Usage

Analyze one file:

```bash
python3 quantum_peak_method_selector.py examples/tiny_peak.qasm
```

Analyze a challenge directory and write a report:

```bash
python3 quantum_peak_method_selector.py /path/to/challenges --out method_report.md
```

Write machine-readable output:

```bash
python3 quantum_peak_method_selector.py /path/to/challenges --format json --out method_report.json
python3 quantum_peak_method_selector.py /path/to/challenges --format csv --out method_report.csv
```

## How To Read The Recommendation

Use the top method as the first serious path, not as a guarantee.

- If exact baseline is `recommended`, solve with statevector first.
- If MPS wins, run a fast bond-dimension ladder and majority-vote the sampled bits.
- If TNO wins, try midpoint contraction and watch bond growth carefully.
- If MPO unswapping wins, the circuit likely needs structural deobfuscation, not only
  more shots.

The output is also useful for the 2-3 sentence submission description because it gives
evidence like "sparse entangling graph", "dense hidden-permutation signal", or "repeated
two-qubit pairs suggesting inverse blocks."

## References

- Paper: https://arxiv.org/abs/2604.21908
- Method repo: https://github.com/d-kremer/peaked-circuit-simulation
- Junction challenge repo used by the team: https://github.com/LissanKoirala/quantum-junction
