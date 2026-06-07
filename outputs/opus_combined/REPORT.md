# Opus Combined Cracker — Results Report

Method: **snap angles (tol 1e-2) → consolidate 2q blocks → MPO unswap-to-convergence (Kremer–Dupuis + robust RCM graph reordering + force-absorb/time-budget) → sample + per-qubit Z-sign readout** (bit order `perm_rev`).

Trust: a candidate is believable when it matches a known answer, OR multiple cutoffs/seeds agree with high top-fraction, OR natural low-bond convergence (forced_absorptions=0) with sample==marginal agreement. `converged=True` reached via force-absorb under a loose cutoff is NOT trusted (it truncates real amplitude).

| challenge | q | best candidate (`perm_rev`) | top frac | conv | forced | bond | confidence | dist |
| --- | ---: | --- | ---: | :-: | ---: | ---: | --- | --- |
| challenge-48_37 | 48 | `101001010110101100001110100101001011010100011010` | 0.0001 | N | 0 | 220 | untrusted (noise floor) | — |
| challenge-64_40 | 64 | `0010000011100010111101100101100110000101110011110111100100001110` | 0.0001 | N | 0 | 82 | untrusted (noise floor) | — |
| challenge-64_41 | 64 | `1011001100010011000111010001110111001000000011001001100011110011` | 0.0003 | N | 0 | 10 | untrusted (noise floor) | — |
| challenge-24_13 | 24 | `110100000111110111010111` | 0.7073 | Y | 0 | 64 | INCORRECT vs known answer (best persisted run is wrong; see runs) | — |
| challenge-28_4 | 28 | `1111111000101010110110011111` | 0.1537 | N | 0 | 110 | VALIDATED (matches known answer) | — |
| challenge-40_7 | 40 | `0110111011010001010011111110010011000111` | 0.8745 | Y | 0 | 4 | medium (natural convergence, top=0.87, sample==marginal) | — |
| challenge-48_8 | 48 | `000100100110111001001111111100101011001110010100` | 0.713 | Y | 0 | 16 | medium (natural convergence, top=0.71, sample==marginal) | — |

## Per-challenge detail

### challenge-48_37  (q=48)
- best candidate (`perm_rev`): `101001010110101100001110100101001011010100011010`
- confidence: untrusted (noise floor)
- runs (1):
    - `cpu_c2e-03_snap_s123`: cutoff=0.002 conv=False forced=0 bond=220 top=0.000125 sample==marg=False

### challenge-64_40  (q=64)
- best candidate (`perm_rev`): `0010000011100010111101100101100110000101110011110111100100001110`
- confidence: untrusted (noise floor)
- runs (1):
    - `cpu_c2e-03_snap_s123`: cutoff=0.002 conv=False forced=0 bond=82 top=0.000125 sample==marg=False

### challenge-64_41  (q=64)
- best candidate (`perm_rev`): `1011001100010011000111010001110111001000000011001001100011110011`
- confidence: untrusted (noise floor)
- runs (1):
    - `cpu_c2e-03_snap_s123`: cutoff=0.002 conv=False forced=0 bond=10 top=0.00025 sample==marg=False

### challenge-24_13  (q=24)
- known answer: `111110011111001011010001`
- best candidate (`perm_rev`): `110100000111110111010111`
- confidence: INCORRECT vs known answer (best persisted run is wrong; see runs)
- runs (7):
    - `c1e-03_snap`: cutoff=0.001 conv=True forced=0 bond=64 top=0.70725 sample==marg=True
    - `c2e-3_nosnap`: cutoff=0.002 conv=True forced=0 bond=64 top=0.68725 sample==marg=True
    - `val_b4096_c0.002_snap`: cutoff=0.002 conv=True forced=0 bond=64 top=0.687 sample==marg=True
    - `c1e-4_nosnap`: cutoff=0.0001 conv=True forced=0 bond=64 top=0.59925 sample==marg=True
    - `c1e-04_snap`: cutoff=0.0001 conv=True forced=0 bond=64 top=0.593 sample==marg=True
    - `c1e-05_snap`: cutoff=1e-05 conv=True forced=0 bond=56 top=0.5925 sample==marg=True
    - `gpu_c1e-5_snap_b8192`: cutoff=1e-05 conv=True forced=0 bond=128 top=0.58375 sample==marg=False

### challenge-28_4  (q=28)
- known answer: `1111111000101010110110011111`
- best candidate (`perm_rev`): `1111111000101010110110011111`
- confidence: VALIDATED (matches known answer)
- runs (1):
    - `val_b4096_c0.002_snap`: cutoff=0.002 conv=False forced=0 bond=110 top=0.15375 sample==marg=True

### challenge-40_7  (q=40)
- best candidate (`perm_rev`): `0110111011010001010011111110010011000111`
- confidence: medium (natural convergence, top=0.87, sample==marginal)
- runs (1):
    - `val_b4096_c0.002_snap`: cutoff=0.002 conv=True forced=0 bond=4 top=0.8745 sample==marg=True

### challenge-48_8  (q=48)
- best candidate (`perm_rev`): `000100100110111001001111111100101011001110010100`
- confidence: medium (natural convergence, top=0.71, sample==marginal)
- runs (1):
    - `val_b4096_c0.002_snap`: cutoff=0.002 conv=True forced=0 bond=16 top=0.713 sample==marg=True

