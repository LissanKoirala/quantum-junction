# peaked-circuit-simulation run log

## 2026-06-05 23:38 BST

- User requested removing the 5-task cap and using at most 1000 CPUs at a time.
- Existing Slurm array: `34607501`.
- Each task requests 16 CPUs, 80G RAM, and 1 GPU.
- Full 49-task concurrency is `49 * 16 = 784` CPUs, below the requested 1000-CPU cap.
- Ran `scontrol update JobId=34607501 ArrayTaskThrottle=49`.
- The command reported `34607501_5: Job has already finished`, but subsequent Slurm state showed the update applied to the remaining array:
  - `ArrayTaskThrottle=49`
  - pending group shown as `34607501_[9-48%49]`
- Updated `jobs/run_peaked_all_array.slurm` and `outputs/peaked_circuit_sim_all/SUMMARY.md` to reflect `%49`.
- Current outputs at this checkpoint:
  - JSON files: 9
  - `ok`: 4
  - `started`: 5
  - images: 4
  - stats JSONL: 4

## 2026-06-05 23:40:59 BST

- Monitored Slurm job: `34607501`
- Queue active: `True`
- JSON files: `12`
- Images: `4`
- Stats JSONL: `4`
- Status counts: `{'ok': 4, 'started': 8}`
- Known-reference matches: `['16_12']`
- Known-reference mismatches: `[{'challenge': '24_13', 'candidate': '111110011111001011010011', 'known': '111110011111001011010001', 'hamming': 1}]`

```text
JOBID PARTITION                           NAME    STATE       TIME  NODES NODELIST(REASON)
34607501_[12-48%49 interrupt                     peaked_all  PENDING       0:00      1 (Resources)
       34607501_11 interrupt                     peaked_all  RUNNING       0:37      1 erc-hpc-comp204
       34607501_10 interrupt                     peaked_all  RUNNING       1:09      1 erc-hpc-comp204
        34607501_9 interrupt                     peaked_all  RUNNING       1:16      1 erc-hpc-comp195
        34607501_8 interrupt                     peaked_all  RUNNING       4:56      1 erc-hpc-vm064
        34607501_7 interrupt                     peaked_all  RUNNING       9:05      1 erc-hpc-comp203
        34607501_6 interrupt                     peaked_all  RUNNING      11:40      1 erc-hpc-vm065
        34607501_4 interrupt                     peaked_all  RUNNING      17:29      1 erc-hpc-comp204
        34607501_3 interrupt                     peaked_all  RUNNING      17:29      1 erc-hpc-comp204
```

## 2026-06-05 23:41 BST

- Added monitor scripts:
  - `jobs/monitor_peaked_all.py`
  - `jobs/monitor_peaked_all.slurm`
- Validated the monitor with a one-shot local check.
- Submitted 30-minute monitor as Slurm job `34608329`.
- Monitor behavior:
  - appends to this file every 30 minutes
  - writes current machine-readable status to `outputs/peaked_circuit_sim_all/MONITOR_STATUS.json`
  - writes `outputs/peaked_circuit_sim_all/MONITOR_FINAL.md` after the array leaves the queue
- Current queue showed pending tasks blocked by `Resources`, not `JobArrayTaskLimit`.
- Current output counts:
  - JSON files: 12
  - `ok`: 4
  - `started`: 8
  - images: 4
  - stats JSONL: 4

## 2026-06-05 23:41:25 BST

- Monitored Slurm job: `34607501`
- Queue active: `True`
- JSON files: `12`
- Images: `4`
- Stats JSONL: `4`
- Status counts: `{'ok': 4, 'started': 8}`
- Known-reference matches: `['16_12']`
- Known-reference mismatches: `[{'challenge': '24_13', 'candidate': '111110011111001011010011', 'known': '111110011111001011010001', 'hamming': 1}]`

```text
JOBID PARTITION                           NAME    STATE       TIME  NODES NODELIST(REASON)
           34607501_[12-48%49] interrupt                     peaked_all  PENDING       0:00      1 (Resources)
                   34607501_11 interrupt                     peaked_all  RUNNING       1:04      1 erc-hpc-comp204
                   34607501_10 interrupt                     peaked_all  RUNNING       1:36      1 erc-hpc-comp204
                    34607501_9 interrupt                     peaked_all  RUNNING       1:43      1 erc-hpc-comp195
                    34607501_8 interrupt                     peaked_all  RUNNING       5:23      1 erc-hpc-vm064
                    34607501_7 interrupt                     peaked_all  RUNNING       9:32      1 erc-hpc-comp203
                    34607501_6 interrupt                     peaked_all  RUNNING      12:07      1 erc-hpc-vm065
                    34607501_4 interrupt                     peaked_all  RUNNING      17:56      1 erc-hpc-comp204
                    34607501_3 interrupt                     peaked_all  RUNNING      17:56      1 erc-hpc-comp204
```

## 2026-06-05 23:55 BST

- User requested status check.
- Current result summary:
  - JSON files: 12
  - `ok`: 7
  - `started`: 5
  - images: 7
  - stats JSONL: 7
  - errors: 0
- Known-reference validation so far:
  - `16_12` matches known exact answer.
  - `24_13` is off by one bit versus known exact answer and should be rerun later with stricter settings.
- Slurm briefly showed the remaining pending group back at `%5` / `JobArrayTaskLimit` after more task transitions.
- Reapplied `scontrol update JobID=34607501 ArrayTaskThrottle=49`.
- Verified current pending group:
  - `34607501_[13-48%49]`
  - `ArrayTaskThrottle=49`
  - pending reason `None`
- Replaced monitor job:
  - old monitor `34608329` was cancelled while completing
  - new monitor `34608840` submitted from updated script
  - updated monitor now re-checks and reapplies `ArrayTaskThrottle=49` every cycle

## 2026-06-05 23:55:04 BST

- Monitored Slurm job: `34607501`
- Queue active: `True`
- Throttle action: `ArrayTaskThrottle already 49.`
- JSON files: `17`
- Images: `8`
- Stats JSONL: `8`
- Status counts: `{'ok': 8, 'started': 8}`
- Known-reference matches: `['16_12']`
- Known-reference mismatches: `[{'challenge': '24_13', 'candidate': '111110011111001011010011', 'known': '111110011111001011010001', 'hamming': 1}]`

```text
JOBID PARTITION                           NAME    STATE       TIME  NODES NODELIST(REASON)
           34607501_[17-48%49] interrupt                     peaked_all  PENDING       0:00      1 (None)
                   34607501_16 interrupt                     peaked_all  RUNNING       0:02      1 erc-hpc-comp204
                   34607501_15 interrupt                     peaked_all  RUNNING       0:02      1 erc-hpc-comp204
                   34607501_14 interrupt                     peaked_all  RUNNING       0:02      1 erc-hpc-vm063
                   34607501_13 interrupt                     peaked_all  RUNNING       0:02      1 erc-hpc-comp192
                   34607501_12 interrupt                     peaked_all  RUNNING       1:22      1 erc-hpc-vm065
                   34607501_11 interrupt                     peaked_all  RUNNING      14:43      1 erc-hpc-comp204
                    34607501_9 interrupt                     peaked_all  RUNNING      15:22      1 erc-hpc-comp195
                    34607501_8 interrupt                     peaked_all  RUNNING      19:02      1 erc-hpc-vm064
                    34607501_3 interrupt                     peaked_all  RUNNING      31:35      1 erc-hpc-comp204
```

## 2026-06-06 00:25:05 BST

- Monitored Slurm job: `34607501`
- Queue active: `True`
- Throttle action: `Requested ArrayTaskThrottle=49; before=5; after=49; scontrol='34607501_11: Job has already finished'`
- JSON files: `21`
- Images: `12`
- Stats JSONL: `12`
- Status counts: `{'ok': 12, 'started': 9}`
- Known-reference matches: `['16_12', '8_11']`
- Known-reference mismatches: `[{'challenge': '24_13', 'candidate': '111110011111001011010011', 'known': '111110011111001011010001', 'hamming': 1}]`

```text
JOBID PARTITION                           NAME    STATE       TIME  NODES NODELIST(REASON)
           34607501_[21-48%49] interrupt                     peaked_all  PENDING       0:00      1 (None)
                   34607501_20 interrupt                     peaked_all  RUNNING       0:27      1 erc-hpc-vm061
                   34607501_19 interrupt                     peaked_all  RUNNING      18:37      1 erc-hpc-vm063
                   34607501_18 interrupt                     peaked_all  RUNNING      24:22      1 erc-hpc-comp192
                   34607501_12 interrupt                     peaked_all  RUNNING      31:22      1 erc-hpc-vm065
                    34607501_9 interrupt                     peaked_all  RUNNING      45:22      1 erc-hpc-comp195
```

## 2026-06-06 status audit

- User asked whether everything is done.
- Current `squeue` for `34607501` and monitor `34608840` is empty.
- Slurm accounting shows the sweep did not finish all 49 tasks:
  - tasks `0-8`, `10`, `11`, and `15` completed
  - tasks `9`, `12-14`, `16-20`, and pending `21-48` were cancelled by UID `852617`
  - monitor `34608840` was also cancelled by UID `852617`
- Output state:
  - manifest entries: 49
  - JSON files: 21
  - completed `ok` JSON: 12
  - partial `started` JSON: 9
  - missing JSON: 28
  - images: 12
  - stats JSONL: 12
- Known-reference checks:
  - `16_12` matches
  - `8_11` matches
  - `24_13` is off by one bit and should be rerun with stricter settings
- Not complete. A retry/resume run is needed for the 9 partial tasks, 28 missing tasks, and stricter rerun of `24_13`.

## 2026-06-06 retry submission

- User asked to fix and keep monitoring.
- Created retry manifest: `outputs/peaked_circuit_sim_all/retry_manifest.tsv`.
- Retry manifest rows: 38.
  - 9 rows for partial `started` JSONs from the cancelled sweep.
  - 28 rows for missing challenge JSONs.
  - 1 strict rerun row for `24_13`, because it was a known-reference 1-bit mismatch.
- Added retry job script: `jobs/run_peaked_retry_array.slurm`.
- Added retry monitor wrapper: `jobs/monitor_peaked_retry.slurm`.
- Current running CPU allocation from other live jobs before retry: 496 CPUs.
- Retry cap: `%31`, with `16` CPUs per task, so max retry CPU allocation is `496`.
- Combined expected cap at submission: about `496 + 496 = 992` CPUs, below the requested 1000-CPU maximum.
- Submitted retry array: `34611837`.
- Submitted retry monitor: `34611838`.
- Retry monitor uses `jobs/monitor_peaked_all.py` and enforces `ArrayTaskThrottle=31` every 30 minutes.
- Initial retry status:
  - `34611837_0` running
  - `34611837_[1-37%31]` pending on priority
  - monitor `34611838` running
  - total running CPU allocation after submission: 513 CPUs

## 2026-06-06 02:49:36 BST

- Monitored Slurm job: `34611837`
- Queue active: `True`
- Throttle action: `ArrayTaskThrottle already 31.`
- JSON files: `21`
- Images: `12`
- Stats JSONL: `12`
- Status counts: `{'ok': 12, 'started': 9}`
- Known-reference matches: `['16_12', '8_11']`
- Known-reference mismatches: `[{'challenge': '24_13', 'candidate': '111110011111001011010011', 'known': '111110011111001011010001', 'hamming': 1}]`

```text
JOBID PARTITION                           NAME    STATE       TIME  NODES NODELIST(REASON)
            34611837_[1-37%31] interrupt                   peaked_retry  PENDING       0:00      1 (None)
                    34611837_0 interrupt                   peaked_retry  RUNNING       0:01      1 erc-hpc-vm065
```

## 2026-06-06 06:12:53 BST retry cancellation audit

- User asked whether everything is done.
- `squeue` has no active entries for retry array `34611837` or monitor `34611838`.
- `sacct` shows retry task `34611837_0` was `CANCELLED by 852617` after `00:03:01`.
- `sacct` shows retry tasks `34611837_[1-37%31]` were also `CANCELLED by 852617` before starting.
- No new retry outputs landed after cancellation.
- Current peaked-circuit output state:
  - Manifest rows: `49`
  - JSON files: `21`
  - Status counts: `{'ok': 12, 'started': 9}`
  - Missing challenge outputs: `28`
  - Images: `12`
  - Stats JSONL files: `12`
- Known-reference state remains:
  - `16_12` matched.
  - `8_11` matched.
  - `24_13` is still a 1-bit mismatch: predicted `111110011111001011010011`, known `111110011111001011010001`.
- Conclusion: not done; retry work needs resubmission after the cancellation issue is resolved.
