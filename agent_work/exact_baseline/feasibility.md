# Exact Baseline Feasibility

Statevector memory assumes complex128 amplitudes only: `16 * 2^n` bytes.
Actual simulator memory is higher, so this baseline caps exact statevector runs at 28 qubits.

## Summary By Difficulty

| difficulty | circuits | qubits | gate range | two-qubit gate range | safe exact SV |
|---|---:|---|---:|---:|---:|
| very easy | 10 | 8-64 | 46-1220 | 15-314 | 4 |
| easy | 16 | 8-64 | 117-1854 | 38-711 | 3 |
| moderate | 8 | 8-64 | 459-3086 | 173-1270 | 3 |
| hard | 7 | 40-64 | 2783-5939 | 1145-2759 | 0 |
| very_hard | 8 | 48-104 | 20733-37660 | 4221-7654 | 0 |

## Safe Exact Statevector Targets

| challenge | difficulty | qubits | gates | two-qubit gates | statevector GiB |
|---|---|---:|---:|---:|---:|
| 8_11 | easy | 8 | 117 | 38 | 3.8147e-06 |
| 8_27 | moderate | 8 | 459 | 173 | 3.8147e-06 |
| 8_1 | very easy | 8 | 46 | 15 | 3.8147e-06 |
| 16_12 | easy | 16 | 291 | 137 | 0.000976562 |
| 16_28 | moderate | 16 | 1670 | 693 | 0.000976562 |
| 16_2 | very easy | 16 | 308 | 125 | 0.000976562 |
| 24_13 | easy | 24 | 550 | 211 | 0.25 |
| 24_29 | moderate | 24 | 3086 | 1270 | 0.25 |
| 24_3 | very easy | 24 | 363 | 131 | 0.25 |
| 28_4 | very easy | 28 | 1220 | 278 | 4 |

## 32+ Qubit Exact Statevector Limit

A 32-qubit complex128 statevector alone is 64 GiB before simulator overhead. The `interruptible_cpu` partition reports roughly 62 GB or higher nodes, so 32-qubit statevector is not a safe default target here. Larger sizes grow by a factor of two per added qubit.

| qubits | statevector GiB |
|---:|---:|
| 28 | 4 |
| 29 | 8 |
| 30 | 16 |
| 31 | 32 |
| 32 | 64 |
| 36 | 1024 |
| 40 | 16384 |
| 48 | 4.1943e+06 |
| 56 | 1.07374e+09 |
| 64 | 2.74878e+11 |
| 72 | 7.03687e+13 |
| 80 | 1.80144e+16 |
| 88 | 4.61169e+18 |
| 96 | 1.18059e+21 |
| 104 | 3.02231e+23 |
