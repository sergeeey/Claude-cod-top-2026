# Measurement baseline — 2026-11-25 (observation start, not a pre-modernization state)

> Purpose: fix what can be measured today so that any later change can be compared with it. The
> earlier reference `2026-07-24-external-audit-baseline.md` describes the state before the autumn
> changes; this file starts the observation of the current configuration. The current configuration is
> NOT the original one: it already contains the 2026-09 routing and gate fixes, the 2026-11-05
> dormant-hook noise reduction, the 2026-11-07 disabled hooks, the 2026-11-17 path-scoped rules, the
> 2026-11-24 `skill_search.py` and the week-long `skill_candidates` trial that started 2026-11-25.
> Nothing below is a before/after of any single change.

## Reference point T0

| Item | Value |
|---|---|
| Repository | `main` at `b17a5e5` (2026-11-24 after #558) |
| Live skill corpus | 193 personal skills, checksum `d253ce88…40f0` (normalised line endings, over SKILL.md bytes) |
| Search script / hook (live) | `skill_search.py` `eeee24a1…6d6b`, `skill_candidates.py` `0b2ffd60…9967`, hook entry present, counts-only log on, randomisation off |
| How to re-take it | `python scripts/snapshot_state.py --out DIR`, then `--compare OLD.json NEW.json` |

## Indicators: definition, denominator, source, limits, confidence, value

Window for all values: the last 30 days up to 2026-11-25 unless stated. Confidence is about the
measurement, not about whether the value is good. "Not measurable" is recorded as such.

| # | Indicator | Method and denominator | Source | Value now | Limits | Confidence |
|---|---|---|---|---|---|---|
| 1 | Share of tasks with a skill or tool named by the user | skill activations typed by the user as a slash command / human prompts | `scripts/skill_usage_report.py` (S0) over transcripts; prompts counted from the same transcripts | 111 of 2,703 prompts (4.1%); model-called activations 118 (4.4% of prompts) | a prompt is not a task; automatic and scheduled sessions inflate the denominator (median 1 prompt per session, mean 16); naming a skill in plain text is not counted | medium |
| 2 | Share of tasks with a confirmed successful result | tasks with an objective pass / tasks | none: no success label is recorded anywhere | not measurable | the first source will be the regression set and the weekly human label pack | none yet; observation starts at the regression set's first run |
| 3 | User-detected error frequency | prompts that report a wrong result / prompts | would need labelled prompts | not measurable | a keyword proxy was not validated and is not used | none |
| 4 | User interventions | "Request interrupted by user" events; prompts per session | transcripts | 23 interrupts (0.9% of prompts); 11 of 341 sessions (3%) have at least one; prompts per session median 1, mean 16.3, p90 45 | interrupts are only one kind of intervention; corrections by typing are not counted | medium for interrupts, low for the rest |
| 5 | Tokens and time per comparable successful task | tokens / tasks with an objective pass | transcripts have usage per turn; no comparable tasks exist yet | context at the first assistant turn: median 160k tokens, p10 104k, p90 525k (n=227) | this is starting context, not task cost; tasks are not comparable | low; real comparison needs the regression set |
| 6 | Confirmed unjustified hook blocks | blocks judged unjustified by an independent reviewer / blocks | `~/.claude/logs/hook_triggers.jsonl` (counts by hook and action) | 1,326 trigger records with action block or deny in 30 days, of 2,715 records; `permission_policy` 941, `skeptic_auto_trigger` 175, `input_guard` 156, `validation_theater_guard` 54; justified/unjustified: not measurable | the label `block` is used by some PostToolUse hooks that cannot block (advisory), so the number overstates real blocks; no reviewer labels exist | count: medium; justification: none |
| 7 | Repetition of known errors | increments of the `[×N]` counter of `memory/patterns.md` per period / patterns | `patterns.md` (outside the repository) | 41 patterns carry a counter; 17 with N≥2; 11 with N≥3; maximum 4; no time series | a counter records that a pattern was written again, not that the same error recurred; start the weekly increment count now | low |
| 8 | Autonomous recovery share | recovered without user input / failures | `tool_failures.jsonl` | 0 records in the window (the log is empty, so it says nothing) | the source is not populated | none |
| 9 | Effect of earlier architectural changes | changes with a recorded prediction and a later check / changes | `benchmarks/*/run-*` (14 recorded runs), `experiments/*/decision.md` (17), `null_results/` (8 files), pearl registry (31 pearls, only 2 with a `next_check` in the loaded index) | counts only | counting records is not evaluating effects; effect needs the paired comparison in `tests/eval/e2e-regression-set.md` | counts: high; effect: none |

## Context components (loaded volume, not proven influence)

What each component adds to the context is measurable; what it contributes to results is not. The
estimates use 3.6 characters per token and are labelled as estimates.

| Component | Measured volume | Source | Influence on results |
|---|---|---|---|
| Instruction files loaded at session start in at least half of sessions (global CLAUDE.md and rules) | 15 files, 112,395 bytes (about 31k tokens, estimate); largest: `memory-protocol.md` 19.9k, `estimand-ops.md` 18.9k, `doubt-driven-development.md` 12.8k bytes | `~/.claude/logs/instructions.jsonl`, current file sizes | not measured |
| Global CLAUDE.md | 7,386 bytes | file | not measured |
| Rules directory | 21 files, 251,295 bytes, not all loaded every session (some are path-scoped) | file system | not measured |
| Skill listing | 193 personal skills: names about 3.5k characters; descriptions 112,765 characters (each capped at 1,536) against a list budget of about 30,000 characters, so most descriptions never reach the model | S0 and `skill_search.py` corpus | not measured |
| Candidate hints from the search hook | at most two lines per prompt, only on a confident match | trial log and transcripts | under observation until 2026-12-02 |
| Hook-injected context in transcripts | 30 days: PostToolUse 3.51M characters, UserPromptSubmit 2.73M (about 1,000 characters per prompt), SessionStart 1.29M, PreToolUse 0.20M | `hook_additional_context` attachments | not measured |
| Project memory index | 16,933 bytes | file | not measured |
| MCP and tool descriptions | 12 MCP servers configured; description size is in the system prompt, not in any file | `.claude.json` | size unknown, influence not measured |
| Loaded skill instructions | counted per activation in S0 (next-5-turn tokens are not the skill's cost) | S0 | not measured |
| Total at the first assistant turn | median 160k tokens (see indicator 5) | transcript usage | — |

## Observations that start now

Weekly: the S0 report, the trial log counts, the human label pack (10-15 cases, with the owner's
consent), the `patterns.md` counter increments, `snapshot_state.py` compared with the previous one.
Per change: the regression set run on the baseline and on the candidate, with the guards listed there.

## Limits stated once

No value above is a causal effect. Indicators 2, 3, 8 have no data and are left empty on purpose.
Numbers from transcripts include scheduled and automatic sessions; scratch directories of experiments
are excluded. The values are aggregates; no message text is recorded.
