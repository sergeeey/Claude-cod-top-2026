# Autonomy Budget — Loop and Agent Constraints

## Problem This Solves

Agent loops that run without declared bounds can:
- Take irreversible actions (delete, push, deploy) before anyone notices
- Compound errors across many files in a single run
- Drift from the original goal across long chains

Every autonomous loop or agent MUST declare its budget BEFORE execution.

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

## Risk Tier Classification

| Tier | Scope | Auto-action | Example |
|------|-------|-------------|---------|
| **Green** | read-only, local, reversible | ✅ yes | research health check, lint report |
| **Yellow** | code edits, tests, refactor | ✅ yes — with tests + evidence | bug fix, new feature |
| **Red** | production, PII, security, irreversible | ❌ proposal only | deploy, auth change, schema migration |
| **Black** | money, health, legal, mass-delete | ❌ NEVER — human must act | financial transfer, DROP TABLE |

**Hard rule:** `risk_tier = Red` or `Black` → loop returns a proposal, NOT an action.

## Autonomy Budget for This Repo's Loops

| Loop | Trigger | Timeout | Files Changed | Risk Tier | Forbidden |
|------|---------|---------|---------------|-----------|-----------|
| Research Health | SessionStart | 8s | 0 (state file only) | Green | all project writes |
| Project Focus | SessionStart | 8s | 0 (state file only) | Green | all project writes |
| Anti-fraud Signal | SessionStart | 8s | 0 (state file only) | Green | all project writes |

All SessionStart hooks are **Green** by construction:
read files → emit `additionalContext` → write one state timestamp.
They never edit project files, never call git, never send messages.

## Violation Protocol

If a loop exceeds its budget or hits a forbidden action:
1. Log to stderr: `[loop-name] budget exceeded: <reason>`
2. `sys.exit(0)` — fail-open, never block SessionStart
3. Do NOT proceed with the forbidden action

## Relation to Evidence Policy

Budget compliance is not evidence of correctness.
A loop that stayed within budget can still emit `[UNKNOWN]` output.

```
Autonomy Budget  = safety floor  (prevents harm)
Evidence Policy  = quality floor (prevents falsehood)
Both required.   Neither replaces the other.
```
