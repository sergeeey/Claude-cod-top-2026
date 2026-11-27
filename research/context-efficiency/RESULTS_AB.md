# Approved A/B run: memory slice (arm A vs arm B)

Date: 2026-11-21. Owner approved the paid run. Model `claude-haiku-5-5`. 36 sessions, 6 tasks x 2 arms x 3 reps. Runner: `measure/ab/run_ab.py`.

## Verdict

**INCONCLUSIVE** for benefit. Quality is at ceiling in both arms, so this run cannot detect a quality difference. Cost is lower in arm B by about 8% at the median, but within noise and confounded by cache state.

## What was run

| Arm | Setting | Memory slice |
|---|---|---|
| A | `--settings {}` | global `CLAUDE.md` and all global rules loaded |
| B | `--settings` with `claudeMdExcludes` for `**/serge/.claude/CLAUDE.md` and `**/serge/.claude/rules/**` | excluded |

Same model, same tools (`Read Edit Write Glob Grep`, `pytest`, `python`), same hooks, same prompts, same permission mode. Sessions run in `scratchpad/ab/runs/`, not in the repo.

## Results

| Metric | Arm A | Arm B |
|---|---|---|
| Hidden acceptance tests passed | 18/18 | 18/18 |
| Median turns | 7 | 8 |
| Median `total_cost_usd` (CLI) | 0.113 | 0.104 |
| Median `cache_creation_input_tokens` (interleaved runs) | 63 778 | 64 398 |
| Median `cache_read_input_tokens` | 712 753 | 588 790 |
| Median wall time, s | 48.8 | 49.3 |
| CLI errors | 0 | 0 |

Per task (hidden pass A / B, median cost A / B, median turns A / B): all tasks 3/3 in both arms. Cost direction flips across tasks (t4 and t5 cheaper in B, t2 and t1 cheaper in A, t3 and t6 close). Sum of CLI `total_cost_usd` over the 36 full runs: **$4.125**.

## Why it is inconclusive

1. **Ceiling.** 36/36 hidden passes in both arms. The tasks were too easy for Haiku, so a quality loss would not show up. This is not evidence of no harm.
2. **Cost difference is noise.** About 8% median, three runs per cell, and the per-task direction is mixed. No confidence interval was computed; with this n it would include zero.
3. **Cache state confounds the startup effect.** The dry run, with a cold cache, showed arm A at 155 969 and arm B at 75 872 cache-creation tokens. In the interleaved full runs the medians are almost equal (63 778 vs 64 398), because cache entries from earlier runs with the same prefix are reused within the 5-minute window. So per-run cache-creation does not isolate the memory slice.
4. **Arm B drops the safety-tier rules too.** `autonomy-budget` and `private-material` are excluded in B. The tasks do not test them, so this run says nothing about safety.

## Interruption and the reboot

- The runner stopped at 31 of 36 full runs. It was resumed; the resume skips finished rows and ran only the 5 missing ones (t1 A3, t2 B3, t3 A3, t4 B3, t5 B3). All 36 are present, one row per key.
- Windows event log: the reboot was a kernel crash at 14:47–14:50 on 2026-11-21 (bugcheck 0x1e, access violation 0xc0000005, crash dump written, event 41 unexpected shutdown). **It happened before the background runner started** (runner processes appear after 15:00). The dry run ran 14:17–14:18, half an hour before the crash.
- Cause of the crash: [UNKNOWN]. The event log does not name a driver. To attribute it, read `C:\Windows\MEMORY.DMP` with a debugger.
- The runner is one sequential Python process starting one `claude -p` at a time. The many `claude.exe` and MCP server processes seen in the process list belong to the desktop app's sessions and MCP servers.

## Next step (recommended, not run)

To detect a quality or cost difference, the next run needs:

1. Harder tasks where Haiku fails sometimes, so the pass rate is not at ceiling.
2. Blocked ordering (all A, then all B), or a gap of more than 5 minutes between runs, so cache state does not leak between arms.
3. More repetitions per cell, and a confidence interval on the cost difference.

This needs a new owner decision because it means another paid batch.

## Files

- `measure/ab/run_ab.py`, `make_tasks.py`, `baseline_check.py`, `analyze.py`: runner and analysis.
- `measure/ab/tasks/`, `measure/ab/hidden/`: the six task dirs and the hidden acceptance tests (copied in only after each run).
- `results/ab_runs.jsonl`: one row per session, raw CLI usage and hidden-test outcome. Includes `stderr_tail` and `hidden_out`; local, untracked.
- Nothing committed or pushed.
