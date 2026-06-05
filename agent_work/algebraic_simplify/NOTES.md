# Algebraic Simplification Findings

Scope: 49 challenge QASM files. All compute-heavy Qiskit work ran as Slurm array jobs on `interruptible_cpu`; generated files stayed under `agent_work/algebraic_simplify`.

## Artifacts

- `algebraic_simplify.py`: parser, local reducer, Qiskit transpiler probe, candidate extractor, summarizer.
- `run_algebraic_array.slurm`: Slurm array wrapper.
- `challenge_files.txt`: ordered input list.
- `results/*.json`: per-circuit detailed metrics.
- `summary.csv` and `summary.json`: aggregate table and rollup.
- `layer_run_probe.json`: maximal RX/RX+SWAP/one-qubit run probe.
- `rx_angle_candidates.csv`: opening/trailing/all-RX angle-threshold candidate probe.
- `logs/qj-algebra-34605748_*.out`: authoritative fixed Slurm run logs. Job `34605688` was an earlier superseded run before the snapped-QASM Qiskit keyword fix.

## What Worked

- Qiskit `optimization_level=3` with no native basis constraint compresses many single-qubit RX/RZ chains into generic `u3`/`u2`/`unitary` gates. This is real syntax reduction but not a structural peak leak.
  - Very-hard average: `28576` original gates to `17288` auto-optimized gates.
  - Example `challenge-104_49`: `26361` gates to `15985`, with ops `cx=5406, rx=1213, rz=1235, u3=8131`.
- Native-basis Qiskit (`rx/rz/cx/swap`) is useful as a sanity check for exact cancellations, but it leaves almost everything intact.
  - Very-hard average: `28576` to `28574.5`.
  - Best raw native reduction observed: 12 gates on `easy/challenge-40_17.qasm`.
- Angle snapping to nearby pi fractions is safe for probing and sometimes helps auto-Qiskit slightly.
  - Best auto benefit: 37 gates on `very_hard/challenge-104_49.qasm`.
  - This is too small to expose `P1/P2`.

## What Failed

- Greedy adjacent/inverse cancellation is negligible.
  - Average snapped-at-`1e-3` reduction: very easy `0.47%`, easy `0.30%`, moderate `0.21%`, hard `0.07%`, very-hard `0.03%`.
  - Best case: `very easy/challenge-56_9.qasm` at `2.2%`.
- CNOT/SWAP linear-window tracking finds only small local structure.
  - Very-hard has no identity or pure-permutation entangler windows in this scan.
  - Largest entangler-only window overall was length 21; very-hard max was length 9.
- Exact or near `RX(pi)` extraction is not a reliable peak signal.
  - Very-hard has only 5 exact `rx(pi)` gates total across 8 circuits, and only 29 near-pi RX gates at `1e-3`.
  - The CX/SWAP-propagated and SWAP-only RX(pi) candidates missed all six statevector-checkable circuits (`n <= 16`).
- Simple RX angle thresholding also fails.
  - First-layer, trailing-layer, and total-RX angle candidates had random-looking Hamming distances on the six exact-validated small circuits.
- `P1/P2` do not survive as visible RX-only layers.
  - RX-only runs do not cover all qubits.
  - Very-hard circuits often start with a full-width one-qubit layer, but small-circuit validation shows this kind of layer is not a direct peak leak.

## Concrete Cracking Insight

The obfuscation defeats local algebraic simplification: the hidden RX layers are dispersed enough that native transpilation, pi snapping, adjacent cancellation, SWAP tracking, and Clifford-ish scans do not recover the target bitstring. Use the unconstrained Qiskit reduction only as a preconditioner for downstream simulation or tensor-network work, not as a decoder. For structural attacks, the next promising direction is global matching of approximate inverse blocks or tensor/MPS/unswapping methods; the direct RX(pi) and visible-layer heuristics should be deprioritized.
