# Tree Tensor Simulation Session Research

Snapshot generated during the Codex tree-tensor simulation work on 2026-06-06.

## Report

- `report/quantum_junction_session_report.pdf` - compiled 7-page concise report.
- `report/quantum_junction_session_report.tex` - LaTeX source.
- `report/build_session_report.py` - script used to generate the report and figures from the working artifacts.
- `report/figures/` - PDF plots included in the report.

## Result Snapshot

The collector snapshot included here selected candidates for `40/49` challenges.
The unsolved labels at report build time were:

`64_40`, `104_49`, `48_42`, `56_43`, `64_44`, `72_45`, `80_46`, `88_47`, `96_48`.

Important artifacts:

- `artifacts/collector/CANDIDATES.tsv` and `.md` - selected candidates and evidence summary.
- `artifacts/collector/SUBMISSION_ANSWERS.tsv` and `.md` - submission-oriented answer list.
- `artifacts/collector/CANDIDATE_EVIDENCE.json` - full evidence records used by the collector.
- `artifacts/RUN_LOG.md` - concise running log of attempts and decisions.
- `artifacts/exact_baseline/` - exact statevector baseline outputs for small calibrating circuits.
- `artifacts/static_forensics/` - QASM structural summaries used to guide method choice.
- `artifacts/optimized_qasm/remaining_transpile_stats.tsv` - U3 optimization statistics for remaining blanks.

The report is an as-of snapshot. Later Slurm jobs may have produced additional outputs after this folder was assembled.
