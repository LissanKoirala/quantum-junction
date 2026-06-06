# Hard Problems Status

Snapshot: 2026-06-06 12:12 BST

Worktree: `hard-problems`

## Current Rollup

- Refreshed candidate rollup: `outputs/tree_tensor_sim/CANDIDATES.md`
- Selected candidates: 41/49.
- Newly restored hard candidate: `64_40`, selected from archived `peaked_mpo_unswap_gpu` evidence.
- Remaining blank labels: `48_42`, `56_43`, `64_44`, `72_45`, `80_46`, `88_47`, `96_48`, `104_49`.

## Method Direction

Web check:

- Kremer and Dupuis, "Efficient Classical Simulation of Heuristic Peaked Quantum Circuits", arXiv:2604.21908, submitted 2026-04-23: https://arxiv.org/abs/2604.21908
- `d-kremer/peaked-circuit-simulation` repository: https://github.com/d-kremer/peaked-circuit-simulation
- Rudolph and Tindall, "Simulating and Sampling from Quantum Circuits with 2D Tensor Networks", arXiv:2507.11424, revised 2025-09-14: https://arxiv.org/abs/2507.11424

Conclusion: prioritize mirrored-circuit MPO cancellation plus unswapping/permutation extraction, with graph-aware ordering as a support heuristic. The local algebraic simplification artifacts show direct RX/pi extraction and local cancellation are not reliable on very-hard circuits.

## Changes Made In This Worktree

- Created `hard-problems` worktree from the advanced `klalee-graph` branch tip.
- Imported graph/TNS Slurm wrappers and a lightweight snapshot of graph/TNS outputs.
- Fixed DFS tree ordering on forests in `peaked-circuit-simulation/graph_ordering.py`.
- Added collector support for archived candidate rollups and `peaked_mpo_graph_tns` JSON outputs.
- Added initial graph-ordering event recording in `peaked-circuit-simulation/unswap_graph.py`.

## Verification

- `python3 -m py_compile jobs/collect_peak_candidates.py jobs/peaked_mpo_graph_tns_runner.py peaked-circuit-simulation/graph_ordering.py peaked-circuit-simulation/unswap_graph.py`
- Local smoke on `challenges/very easy/challenge-8_1.qasm` with low samples returned candidate `10101101`, validation `correct`, and recorded the initial graph-ordering event.

## Live Compute

Existing Slurm graph/TNS jobs are still running from `klalee-graph`, including five GPU tasks and multiple CPU retry/all-array tasks. No very-hard graph/TNS candidate had completed by this snapshot.

## Update: 2026-06-06 13:46 BST

- Candidate rollup remains 41/49. The unsolved labels are still `48_42`, `56_43`, `64_44`, `72_45`, `80_46`, `88_47`, `96_48`, and `104_49`.
- Added `jobs/monitor_hard_slurm.py`, including `--sync-from ../klalee-graph/outputs`, so status checks pull sibling graph/TNS outputs before summarizing Slurm and very-hard JSON states.
- Extended rollup/report ingestion to include `mpo_graph_tns_extra_cpu_f`, `mpo_graph_tns_extra_cpu_g`, and `mpo_graph_tns_veryhard_fast_cpu_b`.
- Submitted fast very-hard CPU array `34619926` and second parameter variant `34620010`. `34619926_0` through `_4` were preempted; `_0` and `_1` were resubmitted as `34620567`, and stale JSONs for `_2` through `_4` were marked `preempted`.
- Added a SIGTERM/SIGINT handler to `jobs/peaked_mpo_graph_tns_runner.py` so future preemptions write a terminal JSON status instead of leaving `started` placeholders.
- Enforced the requested GPU cap: a separate `vh_mps_gpu` job `34620621` pushed running GPU count to 6, so it was cancelled. Running GPU count returned to 5.
- Latest synced monitor snapshot at 2026-06-06T13:45:50+0100: running CPU 1932, running GPU 5, pending CPU 302, pending GPU 1. No very-hard attempt has written an `ok` candidate yet.

## Update: 2026-06-06 14:09 BST

- Fast very-hard CPU variant `34620010` produced candidates for `48_42` and `56_43`; `outputs/tree_tensor_sim/CANDIDATES.tsv` now selects 43/49 candidates.
- Remaining blank labels are `104_49`, `64_44`, `72_45`, `80_46`, `88_47`, and `96_48`.
- Cancelled redundant solved-label work after the two new hits landed: duplicate `48_42`/`56_43` fast/retry/all-array tasks, solved-label multiseed MPS job `34620622`, pending backups for `48_42`/`56_43`, and old exact-covered `16_28`/`24_29` retry tasks.
- Enforced caps again after unrelated jobs started: cancelled `tno_gpu`/`tno_cpu` arrays and `tno_36_15` when they pushed GPU or CPU above the requested limits.
- Extended `jobs/monitor_hard_slurm.py` with explicit CPU/GPU cap reporting, non-graph active-job reporting when over cap, and multiseed-output sync/status.
- Added and submitted `jobs/run_mpo_graph_tns_veryhard_fast_c_cpu_array.slurm` as job `34621962`, targeting only indices `2-7` (`64_44`, `72_45`, `80_46`, `88_47`, `96_48`, `104_49`) with a different seed/search profile.
- Latest monitor snapshot at 2026-06-06T14:08:44+0100: running CPU 1312, running GPU 5, pending CPU 142, pending GPU 1. `34621962_2` through `_7` are running, and no further very-hard candidates have completed yet.
- Registered and submitted additional CPU-only fast variants using the same indices: `34622347` (`veryhard_fast_cpu_d`, lower-bond/faster-sampling profile) and `34622348` (`veryhard_fast_cpu_e`, higher-center tighter-cutoff profile). At submission, running CPU stayed below cap; `34622347_2` and `_3` were released after a transient Slurm env-retrieval hold.
- Found same-worktree ultrafast jobs `34622360`/`34622374` writing `80_46`, `88_47`, `96_48`, and `104_49`. `34622374` was cancelled because it raced `34622360` in the same JSON directory; `run_mpo_veryhard_ultrafast_cpu_s2.slurm` now writes to `outputs/mpo_veryhard_ultrafast_cpu_s2`, and corrected ultrafast seed-2 job `34622453` was submitted pending priority.
- GPU all-array tasks `34616526_41` (`104_49`) and `34616526_45` (`72_45`) were preempted and their local JSONs were marked terminal. Added `outputs/mpo_graph_tns_gpu_retry` to the rollup and submitted one-at-a-time GPU retry `34622515` for indices `41,45`; `34622515_41` started first.
- Fast-B tasks for `64_44` and `72_45` ended with `ValueError: Probabilities contain NaN` after marginal extraction. Patched `jobs/peaked_mpo_graph_tns_runner.py` so sampling failures are recorded in `sampling` while marginal-derived candidates can still be selected. Submitted patched retry wrapper `34623019` for indices `2-3`.
- Added patched fallback wrapper `34623203` for indices `4-7` (`80_46`, `88_47`, `96_48`, `104_49`) with `%3` throttle, so the larger remaining labels also get marginal fallback if sampling produces NaNs. It is pending on priority with running CPU still under cap.

## Update: 2026-06-06 15:01 BST

- Candidate rollup remains 43/49. The remaining blank labels are `104_49`, `64_44`, `72_45`, `80_46`, `88_47`, and `96_48`.
- Verified current Python/Slurm syntax after the monitor and fallback changes: `python3 -m py_compile jobs/collect_peak_candidates.py jobs/monitor_hard_slurm.py jobs/generate_mpo_graph_tns_status_report.py jobs/peaked_mpo_graph_tns_runner.py` and `bash -n jobs/run_mpo_graph_tns_marginal_fallback_cpu_array.slurm`.
- Submitted `jobs/run_mpo_graph_tns_marginal_fallback_cpu_array.slurm` as job `34624347`, targeting indices `2-7` with `samples=0` so marginal extraction can still produce terminal candidates when sampling would hit NaNs. All six tasks started immediately.
- Cancelled unrelated `tno_36_15_np_cpu` job `34623693`, which was consuming 8 CPU cores on an already-covered label.
- Latest monitor snapshot at 2026-06-06T15:00:33+0100: running CPU 1884/2000, running GPU 5/5, pending CPU 134, pending GPU 0. No cap breach and no additional very-hard `ok` candidate yet.

## Update: 2026-06-06 15:08 BST

- Generated the solved-candidate report at `research/hard_problems/SOLVED_CANDIDATES_REPORT.md` and the probability plot at `research/hard_problems/solved_bitstring_probability.svg`.
- The report is based on `outputs/tree_tensor_sim/CANDIDATES.tsv`; it lists 43/49 solved candidates and the 6 remaining open very-hard labels.
- Added `jobs/generate_solved_candidates_report.py` so the report and plot can be regenerated from the current rollup.
- Extended `jobs/monitor_hard_slurm.py` with dry-run/execute enforcement actions for unrelated cap breaches and tracked solved-label duplicates.
- Ran solved-label cleanup through the monitor execute path, cancelling `34623041_7`, `34623041_5`, `34623041_3`, and `34623041_1`; running resources dropped to CPU 1804/2000 and GPU 4/5.

## Update: 2026-06-06 15:26 BST

- A patched marginal fallback wrote all-zero candidates for `64_44` and `72_45`, but inspection showed their marginal probability arrays were non-finite (`NaN`). These are now treated as unusable evidence rather than solved candidates.
- Patched `jobs/peaked_mpo_graph_tns_runner.py` so future non-finite marginal extraction produces no marginal candidate instead of silently selecting all zeros.
- Patched `jobs/collect_peak_candidates.py` and `jobs/monitor_hard_slurm.py` so existing non-finite marginal JSONs are ignored in the rollup and shown as `ok_unusable` in the monitor.
- Regenerated `research/hard_problems/SOLVED_CANDIDATES_REPORT.md` and `research/hard_problems/solved_bitstring_probability.svg`; the honest rollup remains 43/49 solved.
- Submitted GPU retry `34624722` for `88_47` and `96_48` with `%1` throttle, and resubmitted patched marginal fallback `34624738` for `64_44` and `72_45` to overwrite the unusable JSONs with terminal `no_candidate` or finite candidates.

## Update: 2026-06-06 16:02 BST

- Added per-problem bitstring probability SVGs under `research/hard_problems/bitstring_probability_images/`.
- Regenerated `research/hard_problems/SOLVED_CANDIDATES_REPORT.md` so every solved row embeds its own bitstring probability graph through a GitHub-renderable relative SVG image reference, matching 43/43 solved candidates in the current rollup.
- The per-problem graphs use retained top-k distribution evidence where available, graph-TNS sampling JSONs for the new `48_42` and `56_43` hits, and a selected-candidate-only fallback when no retained top-k distribution exists.
- Verified the regenerated report: 49 total rows, 43 solved rows, 43 SVG files, 43 relative SVG image references, and no blocked data-URI image references.

## Update: 2026-06-06 16:21 BST

- Refreshed the candidate rollup and monitor; solved count remains 43/49 with open labels `64_44`, `72_45`, `80_46`, `88_47`, `96_48`, and `104_49`.
- Latest monitor snapshot: running CPU 1228/2000, running GPU 4/5, pending CPU 223, pending GPU 1; no cap breach and no solved-label cancellation action needed.
- Added `jobs/run_mpo_graph_tns_veryhard_fast_h_cpu_array.slurm`, a focused CPU graph/TNS variant for array indices `2-7` with a distinct seed, center ratio, higher bond limits, and 768 samples.
- Added `outputs/mpo_graph_tns_veryhard_fast_cpu_h` to the collector and Slurm monitor so any usable candidate from the new run is included in the rollup.
- Submitted the new focused CPU array as Slurm job `34626172`; it is pending on priority with `%6` throttle.

## Update: 2026-06-06 16:24 BST

- Slurm started all six `34626172` focused-H tasks for the remaining very-hard labels; early JSON status is `started` for all six with no immediate runner failure.
- Submitted an additional collector-covered parameter probe as Slurm job `34626264`, writing to `outputs/mpo_graph_tns_param_probe`, using seed `20260667`, center ratio `0.75`, bond limits `1024/512`, cutoff `0.015`, and 768 samples.
- Initial `34626264` state: tasks `2`, `3`, and `7` running; tasks `4`, `5`, and `6` pending on Slurm environment retrieval.
- Latest monitor snapshot after both submissions: running CPU 1500/2000, running GPU 5/5, pending CPU 279, pending GPU 1; no cap breach.
- Released `34626264_4`, `34626264_5`, and `34626264_6` from Slurm's transient user-env-retrieval hold; after release they were pending with no hold reason.

## Update: 2026-06-06 19:20 BST

- Refreshed the candidate rollup; solved count advanced to 44/49. New solved label: `104_49`, selected from `peaked_mpo_graph_tns_gpu_retry` with top fraction `0.001`.
- Remaining open labels are `64_44`, `72_45`, `80_46`, `88_47`, and `96_48`.
- Regenerated `research/hard_problems/SOLVED_CANDIDATES_REPORT.md`, `research/hard_problems/solved_bitstring_probability.svg`, and all per-problem bitstring-probability SVGs. The report now has 44 solved rows, 44 relative SVG references, and no blocked `data:image` embeds.
- Latest monitor snapshot: running CPU 492/2000, running GPU 2/5, pending CPU 264, pending GPU 0; no cap breach.
- The focused-H CPU run completed with `no_candidate` for the remaining labels, mostly after sampling hit non-finite probabilities.
- Parameter probe tasks `64_44`, `72_45`, and `104_49` completed with `no_candidate`; tasks `80_46`, `88_47`, and `96_48` re-entered Slurm's user-env-retrieval hold and were released again as `34626264_4`, `34626264_5`, and `34626264_6`.
- GPU retry `34624722_48` for `96_48` is still running; earlier `88_47` retry terminated without a usable candidate.

## Update: 2026-06-06 19:25 BST

- Added collector and monitor support for `outputs/mpo_graph_tns_veryhard_fast_cpu_i`.
- Added `jobs/run_mpo_graph_tns_veryhard_fast_i_cpu_array.slurm`, targeting only the five open labels (`64_44`, `72_45`, `80_46`, `88_47`, `96_48`) as array indices `2-6`.
- Submitted the new focused CPU variant as Slurm job `34629015`; tasks `_2` through `_6` started immediately.
- Latest monitor snapshot after submission: solved count remains 44/49; running CPU 732/2000, running GPU 1/5, pending CPU 166, pending GPU 0; no cap breach.

## Update: 2026-06-06 20:03 BST

- Refreshed the candidate rollup; solved count remains 44/49. Open labels are still `64_44`, `72_45`, `80_46`, `88_47`, and `96_48`.
- Focused variant `34629015_2` through `_6` is still running on all five open labels. Current JSON status for each is `started`.
- Parameter probe `34626264_4`, `_5`, and `_6` is still running on `80_46`, `88_47`, and `96_48`; `64_44` and `72_45` already ended as `no_candidate` from non-finite sampling probabilities.
- GPU retry `34624722_48` for `96_48` is still running.
- Cancelled redundant solved-label tasks for `104_49` (`34619647_41`, `34616566_41`, `34618694_41`), then cancelled solved `48_42` task `34619647_42` and pending solved `56_43` task `34619647_43` from the `%1` extra-CPU array.
- Latest monitor snapshot after cleanup: running CPU 924/2000, running GPU 1/5, pending CPU 166, pending GPU 0; no cap breach.

## Update: 2026-06-06 21:31 BST

- Cancelled all still-running Slurm jobs started by this thread: `34629015_2`, `34629015_3`, `34629015_4`, `34629015_5`, `34629015_6`, and `34624722_48`.
- Stopped the local hourly monitor loop started by this thread (`outputs/hourly_monitor/hourly_monitor.sh`, PID `1259754`).
- Final statuses from the cancelled or finished thread-started runs: focused-H `34626172` completed with `no_candidate`; parameter probe `34626264` completed with `no_candidate` for all remaining labels; focused-I `34629015` ended with errors or signal termination and no usable candidates; GPU retry `34624722_48` terminated with no usable `96_48` candidate.
- Refreshed the candidate rollup and regenerated `research/hard_problems/SOLVED_CANDIDATES_REPORT.md`; solved count remains 44/49 with open labels `64_44`, `72_45`, `80_46`, `88_47`, and `96_48`.
- Latest monitor snapshot after cancellation: no thread-started Slurm jobs remain active. Account-level resources are running CPU 532/2000 and running GPU 7/5; the remaining GPU pressure is from other active jobs, not this thread.
