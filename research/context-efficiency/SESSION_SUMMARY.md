# Session summary: context efficiency and A/B audit (2026-11-21)

Branch `feat/data-analysis-discovery-protocol`. All research work is under `research/context-efficiency/`. Nothing pushed. No changes to `~/.claude`, hooks, or global settings.

## Verdict

**INCONCLUSIVE, decision STOP.** Next paid A/B run is not approved.

## Commits (local, not pushed)

| Commit | Content |
|---|---|
| `bd185fc` | Audit of the 36-session haiku-5-5 A/B run: report, audit scripts, probes, raw results, stats |
| `1b043ff` | Decision record in `AUDIT_AB.md`; SHA-256 of result files |

## What was established

- **Measurement works.** Per-turn token totals from session logs match the CLI in 36/36 runs after deduplicating by `message.id`. Claude Code writes one jsonl record per content block, each repeating the request's usage; summing records double-counts. An early version of the audit script made this error and was fixed.
- **Cost recomputed from official Haiku 5.5 prices matches CLI cost in 36/36 runs.** Total $4.125. Arm A $2.262, arm B $1.863.
- **Quality is at ceiling.** 36/36 hidden tests pass, re-run independently without a model call.
- **Cost difference is not causal.** The all-runs estimate (−17.7%) and the estimate without cache-cold runs (−5.4%, CI through zero) are both sensitivity estimates. Five cache-cold runs (cache_creation about 120k) are all arm A, first repetition. Their cause is unknown.
- **Arm B removes safety-tier rules** (`autonomy-budget`, `private-material-never-in-repo`). B must not be used for operation without a separate safety test.

## Not done, and why

- No new paid runs. The proposed next protocol (80 sessions, about $20–28 plus a pilot) is written up in `AUDIT_AB.md` and needs owner approval.
- No reviewer-agent run. An independent recomputation was done instead.
- `benchmarks/sci-code-audit/_sealed_ground_truth.md`: staged deletion in the index, file ignored by `.gitignore` line 100, still in history at commit `7cd6ce8`. Not touched. Its origin needs an owner decision.
- Task fixtures and hidden tests (`measure/ab/tasks`, `measure/ab/hidden`) are untracked. Their hashes are in `measure/ab/MANIFEST.sha256` (local). Reproducing the experiment needs those files.

## Files

- `AUDIT_AB.md`: audit, decision record, reproduce commands
- `REPORT.md`: first context-efficiency report (v2, after review)
- `RESULTS_AB.md`: first analysis of the A/B run (superseded by `AUDIT_AB.md` for conclusions)
- `measure/audit/`: `audit_ab.py`, `stats_audit.py`, `sensitivity.py`, `same_arm_gap.py`
- `measure/*.py`: usage probe, startup footprint, session totals, follow-up probe
- `results/`: raw runs (`ab_runs.jsonl`), `audit_per_run.csv`, `stats_summary.json`, `SHA256SUMS.txt`
- `SESSION_SUMMARY.md`: this file

## Open items for the next session

1. Owner decision on `_sealed_ground_truth.md`.
2. Owner decision on whether to approve the next A/B. Its design should keep safety-tier rules in the prefix and control cache state with contiguous blocks.
3. Decide where to store fixtures and tests so the experiment can be reproduced from git.
4. `.claude/memory/activeContext.md` was not updated. The file has uncommitted changes from another session in this repo, so this session did not edit it. Add a NOW block once that work lands.
