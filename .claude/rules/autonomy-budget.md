# Autonomy Budget — project addendum

> **This is an ADDENDUM, not a full copy.** The canonical, general Green/Yellow/
> Red/Black tier system now lives in `rules/autonomy-budget.md` (installed to
> `~/.claude/rules/autonomy-budget.md`), generalized 2026-09-09 from this
> file's own loop-only original so it actually applies outside this one repo —
> that file loads alongside this one. Do not restate the tier table here. This
> file holds ONLY what's genuinely specific to Claude-cod-top-2026: the 3
> named SessionStart loops' own declared budgets.

## Problem This Solves

Agent loops that run without declared bounds can:
- Take irreversible actions (delete, push, deploy) before anyone notices
- Compound errors across many files in a single run
- Drift from the original goal across long chains

Every autonomous loop or agent in THIS repo MUST declare its budget BEFORE
execution, using the tier vocabulary from the canonical file above.

## Required Fields (fill before loop runs)

```yaml
loop:
  max_runtime_seconds: 30         # wall-clock cap (SessionStart hooks: ≤8s)
  max_files_changed: 0            # 0 = read-only; increase only for explicit writes
  max_shell_commands: 5           # per-run cap
  allowed_tools:
    - Read
    - Glob
    - Grep
  forbidden_actions:              # NEVER auto-execute
    - git push
    - git reset --hard
    - git commit (without explicit user request)
    - rm -rf
    - DROP TABLE / DELETE / TRUNCATE
    - deploy / publish / release / upload
    - send (email, Slack, PR, DM)
    - approve / confirm irreversible UI action
    - modify .env / secrets / production config
  risk_tier: Green                # Green | Yellow | Red | Black
  escalation_condition: >
    if blocked >2 turns OR risk_tier=Red OR forbidden_action attempted
  human_checkpoint: before_any_Red_or_Black_action
```

**Hard rule (from the canonical tier system):** `risk_tier = Red` or `Black` → loop returns a proposal, NOT an action.

## Autonomy Budget for This Repo's Loops

| Loop | Trigger | Timeout | Project Files Changed | Risk Tier | Forbidden |
|------|---------|---------|----------------------|-----------|-----------|
| Research Health | SessionStart | 8s | 0 (writes 1 state file outside repo: `~/.claude/state/`) | Green | all project writes |
| Project Focus | SessionStart | 8s | 0 (writes 1 state file outside repo) | Green | all project writes |
| Anti-fraud Signal | SessionStart | 8s | 0 (writes 1 state file outside repo) | Green | all project writes |

All SessionStart hooks are **Green** by construction:
read files → emit `additionalContext` → write one state timestamp outside the repo.
They never edit project files, never call git, never send messages.

> **Convention:** "Files Changed" = project repo files. State files in `~/.claude/state/` are
> telemetry/infrastructure — excluded from the count so `max_files_changed: 0` in the YAML template
> means "zero project files changed", not "zero files touched anywhere".

## Violation Protocol

If a loop exceeds its budget or hits a forbidden action:
1. Log to stderr: `[loop-name] budget exceeded: <reason>`
2. `sys.exit(0)` — fail-open, never block SessionStart
3. Do NOT proceed with the forbidden action

## Relation to Evidence Policy

See the canonical file's own "Relation to Evidence Policy" section — same
relationship, not repeated here.
