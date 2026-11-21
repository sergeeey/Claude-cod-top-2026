# Audit of the approved A/B run (memory slice, claude-haiku-5-5)

Date: 2026-11-21. Read-only audit. No model calls, no new paid sessions, no changes to `~/.claude`, no push. Raw results (`results/ab_runs.jsonl`) were not modified.

## Verdict

**INCONCLUSIVE** for benefit. **STOP** on further paid testing until a new protocol is approved.

| Question | Result |
|---|---|
| Data integrity | 36 unique runs, complete, no duplicates. One session folder held a leftover file from the interrupted run; resolved deterministically by token match (section 1). |
| Cost reproduces from logs | Yes. Recomputed cost from official prices equals CLI cost in 36/36 runs (difference 0.000000). |
| Quality | Both arms 36/36 hidden-test pass, re-run independently, no mismatch. Ceiling: this run cannot detect a quality difference. |
| Cost effect | Direction favours B, but it depends on 5 cache-cold runs, all in arm A. Without them the effect is about −5% and its 95% CI includes zero. |
| Causal validity | Not established. Cache state differs by arm and is not explained by time gaps. |
| Safety | Arm B excluded `autonomy-budget` and `private-material`. B must not be recommended for operation without a separate safety check. |

## 1. Integrity of the 36 records

Command: `measure/audit/audit_ab.py` (run from `measure/audit`).

| Check | Result |
|---|---|
| Raw rows | 38 = 36 full + 2 dry-run (dry rows excluded from all statistics) |
| Unique full keys (arm, task, rep) | 36, duplicates 0 |
| Expected vs present | 36 expected, 0 missing, 0 unexpected |
| `rc != 0`, `is_error`, parse errors, hidden failures | 0, 0, 0, 0 |
| Session folders per run (cwd-derived) | 1 per run, except A t1_paginate rep 3 which has 2 session files |

**The two-file case.** The interrupted run left a second session file in `A t1 r3`. Its per-request totals do not reproduce the CLI row; the selected file `1cbafb30-…jsonl` does, exactly (input, output, cache_creation, cache_read). Selection is by token match and is recorded in `audit_per_run.csv` (`session_pick`). Result: `NO_MATCH` count 0.

**An earlier error in the audit script, found and fixed.** The first version summed usage per jsonl record. Claude Code writes one record per content block, each repeating the request's `usage`, so the first version double-counted (e.g. a session with 7 CLI turns showed 15 records from 6 unique `message.id`). The script now deduplicates by `message.id` and flags conflicting duplicates (none found). With deduplication, token totals match the CLI in 36/36 runs. The earlier analysis numbers (median cost, pass counts) came from CLI rows, not from the logs, so they were not affected by this error.

## 2. Cost recomputation

Prices: official Haiku 5.5 pricing (platform.claude.com, fetched 2026-11-21). Prompt length per request = input + cache_creation + cache_read; ≤100k uses the lower tier, >100k the higher tier (documented for Haiku 5.5). Cache writes are split by 5-minute and 1-hour TTL where the log reports the split.

| Check | Result |
|---|---|
| Recomputed cost vs CLI `total_cost_usd` | equal in 36/36 runs (min and max difference 0.000000) |
| Tier used | every run had turns above 100k prompt tokens (`high_tier_turns` > 0), so the higher tier applies to most requests |
| Total CLI cost, all 36 runs | $4.1248 |
| Arm A total / arm B total | $2.2620 / $1.8628 |

Token totals (all 36 runs, from logs):

| Type | Tokens | Priced at (≤100k / >100k, USD per MTok) |
|---|---|---|
| Input (fresh) | 398 | 0.10 / 0.50 |
| Output | 119 596 | 0.50 / 2.50 |
| Cache creation | 2 637 297 | 0.125 (5m) or 0.20 (1h) / 0.625 or 1.00 |
| Cache read | 23 766 991 | 0.01 / 0.05 |

Cache read is about 90% of all tokens processed and is the largest cost term. A reduction of the static prefix changes cache-read tokens roughly as ΔS × requests, and each cache-read token is priced at 1/10 of fresh input (1/10 of the higher tier as well). Token shares are not cost shares; use the USD figures.

## 3. Per-task results (task = unit of pairing)

Source: `results/stats_summary.json`, `results/audit_per_run.csv`.

| Task | Pass A | Pass B | Mean cost A | Mean cost B | Diff B−A | Diff % | Median turns A / B |
|---|---|---|---|---|---|---|---|
| t1_paginate | 3/3 | 3/3 | 0.1078 | 0.1050 | −0.0029 | −2.7% | 6 / 9 |
| t2_duration | 3/3 | 3/3 | 0.1286 | 0.1199 | −0.0087 | −6.8% | 7 / 11 |
| t3_money | 3/3 | 3/3 | 0.1256 | 0.1036 | −0.0219 | −17.5% | 8 / 10 |
| t4_intervals | 3/3 | 3/3 | 0.1378 | 0.1019 | −0.0359 | −26.0% | 9 / 7 |
| t5_config | 3/3 | 3/3 | 0.1251 | 0.0919 | −0.0332 | −26.5% | 7 / 6 |
| t6_csv | 3/3 | 3/3 | 0.1291 | 0.0986 | −0.0305 | −23.7% | 7 / 6 |

Task-level mean difference, all runs: −0.0222 (−17.7%). Bootstrap over the 6 tasks (10 000 resamples): 95% CI [−0.032, −0.012]. Sign test over 6 tasks: p = 0.031 (B cheaper in 6/6). This looks significant, but the cache-state analysis below shows it depends on five runs.

## 4. Cache-state confound (the main threat)

Five runs have cache_creation above 100 000 tokens (cold start of the prefix). Their cost is 0.16–0.17 USD, versus about 0.09–0.12 for the rest.

| Run | Arm | cache_creation | Cost USD |
|---|---|---|---|
| t2_duration r1 | A | 119 757 | 0.1619 |
| t3_money r1 | A | 121 023 | 0.1688 |
| t4_intervals r1 | A | 121 670 | 0.1711 |
| t5_config r1 | A | 118 868 | 0.1737 |
| t6_csv r1 | A | 123 915 | 0.1650 |

Facts:

- All five are arm A, all are `rep=1`, and all come from the first schedule block. Arm B has no cold runs.
- Their same-arm gap to the previous run was 7–113 s, inside the 5-minute cache window, so cache expiry by time does not explain them (`measure/audit/same_arm_gap.py`).
- Global memory files (`CLAUDE.md`, rules, `MEMORY.md`) were last modified at 11:08 or earlier, before the runs, so a memory change during the run does not explain them either.
- The sandbox cwd is part of the system prompt and differs per run; this may affect which prefix is cached, but I did not verify it. Mechanism: [UNKNOWN].

Sensitivity, with the exclusion rule written down before the effect was computed (`measure/audit/sensitivity.py`). Note: the rule was chosen after the outliers were seen, so it is post hoc:

| Analysis | Mean diff B−A | Diff % | Bootstrap 95% CI | Cheaper B in tasks |
|---|---|---|---|---|
| All 36 runs, task level | −0.0222 | −17.7% | [−0.032, −0.012] | 6/6 |
| Excluding cc > 100k (13 A, 18 B) | −0.0060 | −5.4% | [−0.013, +0.001] | 5/6 |
| Median, all runs | −0.0091 | −8.1% | — | — |

The exclusion is asymmetric (only A runs are removed), which is itself a selection effect. Neither version supports a claim of saving. The effect cannot be separated from cache state with this design.

## 5. Quality and the ceiling

- Independent re-run of the hidden acceptance tests on the saved run directories, without any model call: 36/36 pass, no mismatch with the logged result (`measure/audit/stats_audit.py`).
- 18/18 passes in each arm. Upper 95% bound on failure rate with 0 failures in 18 runs: 18.5% per arm. This is a bound, not an estimate of quality.
- Tool errors: arm A 16 in total, arm B 11. Median Read calls: 1 in both arms. These are descriptive proxies only; no test was run.
- Median requests (assistant API calls): A 5, B 6.

The tasks are easy for this model (6–11 turns, 0 failures). A quality difference of several percent could not be detected. This is a limit of the test set, not evidence that the memory slice has no effect on quality.

## 6. Other confounds, stated

| Factor | Status |
|---|---|
| Model | fixed at claude-haiku-5-5 in both arms; verified in logs (`models` column) |
| Hooks | user-level hooks run in both arms; arm B does not disable them. Hooks write telemetry to `~/.claude/logs` on every run. |
| Auto-memory index (`MEMORY.md`) | not excluded by `claudeMdExcludes`; present in both arms only if its project path matches, which it does not for the sandbox cwd. Effect on comparison: none, since neither arm loads it from the repo. |
| Activity hook for `activeContext.md` | depends on the repo cwd; absent in the sandbox in both arms |
| Order of runs | randomised block order (seed 42). The cold cluster sits in block 1. |
| File reads | median 1 Read in both arms |
| Retries | tool-error counts only; no explicit retry count |
| Arm B scope | excluded memory is global CLAUDE.md and `rules/**`, which includes `autonomy-budget` and `private-material-never-in-repo`. Tasks do not test those rules, so safety behaviour under B is unknown. |

## 7. Safety and recommendation for operation

B removes the safety-tier rules. Its measured cost and quality results say nothing about whether those rules change behaviour in risky situations. Do not use arm B as an operating configuration without a separate test of safety-tier behaviour.

## 8. Decision

- **Verdict: INCONCLUSIVE.** The cost difference is plausible, but it depends on cache-cold runs in one arm; the quality question is at ceiling.
- **Decision: STOP** further paid testing until a new protocol is approved.

### Proposed minimal next protocol (not run)

1. Tasks that Haiku sometimes fails: at least 8 tasks, chosen so the pass rate is well below 100% in a pilot of arm A. The pilot itself is paid, so it needs approval.
2. Arms: A (full memory), B' (full memory minus everything except the two safety-tier files, which stay in the prefix), so the safety rules are kept.
3. Cache control: run each arm as a contiguous block, with a 6-minute wait before the first run of each block, and record `cache_creation` per run. Do not exclude runs after the fact.
4. Repetitions: 5 per task per arm = 80 sessions.
5. Pre-registered analysis: task-level paired difference of cost and pass rate, bootstrap over tasks; report the cache-creation distribution per arm.
6. Cost estimate: current runs cost about $0.11 per session on these easy tasks. Harder tasks may cost 2–3 times more per session. Rough budget: 80 sessions × $0.25–0.35 ≈ $20–28, plus a pilot of about 16 sessions. Confirm the price from the official page before running (already done for Haiku 5.5 today).

Required before running: the owner's approval of the spend and of the protocol.

## 9. Reproduce

```
cd research/context-efficiency/measure/audit
python audit_ab.py          # integrity, token match, cost recomputation -> results/audit_per_run.csv
python stats_audit.py       # hidden-test re-run, timestamps, tool use, task-level bootstrap -> results/stats_summary.json
python sensitivity.py       # cache-outlier sensitivity
python same_arm_gap.py      # time since previous same-arm run vs cache_creation
```

`stats_audit.py` takes about 2 minutes (36 pytest subprocesses plus log parsing); run it in the background if needed. It reads run directories from `scratchpad/ab/runs` (path set in the script); if those are gone, skip section 5 and rely on the logged hidden results.

## Files

- `measure/audit/`: `audit_ab.py`, `stats_audit.py`, `sensitivity.py`, `same_arm_gap.py`.
- `results/audit_per_run.csv`, `results/stats_summary.json`: outputs of the scripts above.
- `results/ab_runs.jsonl`: raw runner output, unchanged.
