# Quantum Peak Codex Session Research Package

Snapshot date: 2026-06-06

This folder contains the condensed research artifacts from the Codex session on the Quantum Peak challenge circuits.

## Entry Points

- `reports/session_report/quantum_junction_session_report.pdf`: primary compiled LaTeX report.
- `reports/session_report/quantum_junction_session_report.tex`: primary report source.
- `reports/tree_tensor_report/tree_tensor_report.pdf`: narrower tree-tensor/MPO-unswapping report.
- `results/current_candidates/SUBMISSION_ANSWERS.tsv`: current candidate answer table.
- `results/current_candidates/CANDIDATE_EVIDENCE.json`: source evidence used by the collector.

## Snapshot Result

The report snapshot selected 40 answers out of 49 challenge circuits. The unresolved labels were:

`64_40, 104_49, 48_42, 56_43, 64_44, 72_45, 80_46, 88_47, 96_48`.

The selected set combines exact statevector baselines with graph-ordered Quimb MPS runs and fallback tensor-network evidence. The later MPO-unswapping work was calibrated on known circuit `16_28` and is documented in the tree-tensor report and logs.

## Contents

- `reports/session_report/`: compiled PDF, TeX source, build scripts, figures, and tables for the full session report.
- `reports/tree_tensor_report/`: compiled PDF, TeX source, report data, figure-generation script, and figures for the focused tensor-network report.
- `results/current_candidates/`: current selected candidates and evidence rollup.
- `logs/`: condensed run logs from the tree-tensor worktree.

Heavy raw Slurm output directories are intentionally not duplicated here.
