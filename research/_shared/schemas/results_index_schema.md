# Results Index Schema

The `results_index` folder is the normalized, human-readable layer for challenge results.
It is intentionally separate from raw Slurm outputs and method-specific JSON files.

Each research package should keep its own index:

- `research/tree_tensor_sim_session/results_index/`
- `research/quantum_peak_session/results_index/`

Do not merge package indexes together. The top-level `research/README.md` explains which
package belongs to which workstream.

## Files

### `challenges.tsv`

One row per challenge in the package snapshot.

Columns:

- `challenge`: label such as `64_41`.
- `difficulty`: challenge difficulty.
- `qubits`: number of qubits.
- `qasm`: source QASM path.
- `selected_bitstring`: selected answer if any.
- `selected_method`: method/source that selected the answer.
- `validation`: collector validation label.
- `top_fraction`: selected candidate top probability or sample fraction when known.
- `evidence_count`: number of evidence rows in the collector.

### `selected_answers.tsv`

Submission-oriented selected answer table. Blank rows remain explicit.

Columns:

- `challenge`
- `difficulty`
- `qubits`
- `selected_bitstring`
- `selected_method`
- `validation`
- `top_fraction`
- `evidence_count`
- `status`: `selected` or `blank`.

### `method_runs.tsv`

One row per observed method run, including failed or started runs when they were found.

Columns:

- `session`: research package name.
- `challenge`
- `difficulty`
- `qubits`
- `method`: normalized method key.
- `method_family`: coarse category such as `exact`, `quimb`, `mps`, `mpo`, `sparse`, or `collector`.
- `run_id`: stable local run identifier.
- `status`: `ok`, `started`, `error`, or collector status.
- `source_path`: path to the source artifact that produced the run row.
- `worktree`: local raw-root directory name used when generating the index.
- `commit`: git commit of that raw-root directory when available.
- `backend`
- `shots`
- `max_bond`
- `seed`
- `ordering`
- `seconds`
- `notes`

### `candidates.tsv`

One row per candidate bitstring, including alternate ranks.

Columns:

- `session`
- `challenge`
- `difficulty`
- `qubits`
- `method`
- `run_id`
- `rank_type`: source-specific ranking concept.
- `rank`: integer rank within that ranking concept.
- `bitstring_qiskit`: candidate bitstring in Qiskit count order.
- `score_type`: `probability`, `sample_fraction`, `aggregate_fraction`, `weight`, `margin`, or blank.
- `score`
- `count`
- `support`
- `fraction`
- `selected`: `1` when the row equals the package selected answer, otherwise `0`.
- `validation`
- `status`: method status when relevant.
- `source_path`
- `notes`

Common `rank_type` values:

- `collector_evidence`: candidate from the collector evidence rollup.
- `collector_selected`: selected candidate from `CANDIDATES.tsv`.
- `exact_top`: exact statevector rank.
- `sample_top`: sampled top bitstrings from MPS or Quimb runs.
- `aggregate_rank`: MPS distillation aggregate support ranking.
- `top1_vote_rank`: MPS distillation per-setting top-1 vote ranking.
- `marginal_candidate`: marginal-threshold candidate from peaked MPO/MPS.
- `sparse_beam`: sparse beam rank.
- `final_candidate`: final candidate field reported by a method JSON.

### `annotations.tsv`

Manual review notes. This file is meant to be edited as candidates are checked.

Columns:

- `challenge`
- `bitstring_qiskit`
- `status`: examples are `rejected`, `try_next`, `consider`, `accepted`.
- `note`
- `date`
- `source`

### `by_challenge/*.md`

Human-facing quick pages, one per challenge, sorted by difficulty and challenge number.
These pages include the selected answer, annotations, and all candidate rows for that challenge.

### `by_method/*.tsv`

Candidate rows split by normalized method key.

### `summary.json`

Small count summary for sanity checks and automation.
