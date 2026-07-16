# Memory architecture — current state, debt, and target

Recorded 2026-07-16 after an external config audit flagged memory as the biggest
configuration debt. This documents the tangle so the deep cleanup is a planned, careful
pass — not a risky autonomous restructure of files that hooks auto-write.

## The four overlapping memory systems (the debt)

1. **Native Auto Memory** (Claude Code's own) — `~/.claude/projects/<project>/memory/MEMORY.md`.
2. **Custom global memory** — `~/.claude/memory/_auto/` (patterns.md, learning_log.md), written
   by `pattern_extractor` / `learning_tracker` hooks. Named `_auto` but is NOT native Auto Memory.
3. **Custom project memory (canonical)** — `.claude/memory/` (activeContext.md, goals.md,
   decisions.md, …). Hooks resolve here; `rules/context-loading.md` calls activeContext the
   "single source of truth" that every subagent must read.
4. **Legacy root memory (stale)** — `memory/` at the repo root (activeContext.md, decisions.md).
   April 2026 (v3.2.0), now marked DEPRECATED. Kept because `post_commit_memory.py` uses
   `find_file_upward` and removing it could change resolution — remove only with that verified.

## Why this hurts routing

`context-loading.md` requires every subagent to read `.claude/memory/activeContext.md`. That
file had grown to ~23 KB mixing current state with months of history and contradictory counts
(2125 / 2113 / 1621 tests). A subagent reading stale state routes worse and re-does work.

## Done now (safe, non-breaking)

- `.claude/memory/activeContext.md` now leads with a lean **CURRENT STATE** block (the
  authoritative snapshot: goal, branch, last verified SHA, focus, blockers, next action). The
  running log stays below but is explicitly demoted to "history, not source of truth".
- The legacy root `memory/activeContext.md` carries a DEPRECATED banner.

## Target (the deferred, careful cleanup)

| Concern | Where it should live |
|---|---|
| user prefs + discovered project facts | native Auto Memory |
| current task state (goal/branch/blockers/budget/SHA) | a short `activeContext.md` CURRENT STATE block, ideally generated from git/CI/state |
| proven reusable workflows | `.claude/memory/procedures/` (procedural memory) |
| completed sessions + checkpoints | `.claude/memory/history/` |
| falsified hypotheses | `null_results/` |
| durable architecture decisions | `decisions.md` / ADRs |

**Rules of the target:**
- `activeContext.md` holds ONLY current state — no long history.
- One canonical memory root (`.claude/memory/`); the legacy root `memory/` is retired once the
  `find_file_upward` resolution is confirmed to prefer `.claude/memory/`.
- The hook auto-append (`post_commit_memory`, `pre_compact`) writes to a bounded log section,
  and a periodic job archives log entries older than the current session to `history/`.

## Also flagged by the audit (separate follow-ups)

- Rules duplication: `integrity` / `rationalizations` / `doubt-driven-development` exist in both
  `rules/` (→ global) and `.claude/rules/` (project). Pick canonical-vs-addendum, not two copies.
- `autonomy-budget.md` is only in `.claude/rules/` (project) — not installed globally, despite
  being framed as a global autonomy foundation. Move to installable `rules/` or an autonomy skill.
- Few path-scoped rules: science/security/testing rules apply on all tasks (instruction noise).
  Add `paths:` frontmatter so they load only for relevant files.
- A `/config-explain` command (effective config for the session: loaded instructions, active
  rules, skills, memory, permissions, hooks, conflicts) — the `instructions_audit.py`
  (InstructionsLoaded hook) log can seed it.
