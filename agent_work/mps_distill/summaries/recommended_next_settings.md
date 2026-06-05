# Recommended next MPS settings

## Stable easy circuits

The pilot was already stable for the three easy circuits across all tested
settings. For similar easy circuits, start with:

- `shots=2048`, `bond_dim=32`, `seeds=2`
- escalate to `shots=4096`, `bond_dim=64` only if the two seeds disagree

## Hard circuits

The tested hard circuits were not stable at `shots<=4096` and
`bond_dim<=64`. Their top candidates changed across every seed/setting, and
the aggregate count gap was `1.00`, so the current candidates should not be
submitted as secrets.

Recommended next pass:

- `hard/challenge-40_35.qasm`: `shots=32768`, `bond_dim=64`, `seeds=4`, then
  repeat the winning candidate at `bond_dim=128`, `shots=16384`.
- `hard/challenge-48_36.qasm`: `shots=65536`, `bond_dim=64`, `seeds=4`; if no
  repeated candidate appears, try `bond_dim=128`, `shots=32768`.
- `hard/challenge-64_41.qasm`: keep the no-transpile fallback. Start with
  `shots=65536`, `bond_dim=64`, `seeds=4`; only move to `bond_dim=128` after a
  candidate repeats, because the pilot `4096/bd64` tasks took about 201 seconds
  each and still looked like noise.

For all hard follow-ups, use array tasks on `interruptible_cpu` and distill by
requiring both seed agreement at the highest setting and an aggregate support
gap above `1.10`.
