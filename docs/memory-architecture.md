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
- **Full split executed (2026-08-28)**: the CURRENT STATE table itself had accumulated months
  of narrative into individual cells — its `updated` cell alone had grown to 52,267 characters,
  and the Read tool could not return even a 45-line window without exceeding its token cap
  (found via `/atomize` during a `/boyko-project-radar` full-project sweep the same day). The
  full pre-split file (760 lines, ~96 KB — several stale/superseded "Current Focus"/"Project
  State" sections, a duplicated "Recent findings" header) was archived byte-for-byte to
  `.claude/memory/history/pre-2026-08-28-consolidation.md`, and `activeContext.md` was rebuilt
  as CURRENT STATE (short, tool-verified facts) + Scope Fence + the capped Auto-commit log —
  64 lines, ~6 KB, longest line 502 chars. Nothing was deleted, only moved.
- The legacy root `memory/activeContext.md` carries a DEPRECATED banner.

## Target (the deferred, careful cleanup)

| Concern | Where it should live |
|---|---|
| user prefs + discovered project facts | native Auto Memory |
| current task state (goal/branch/blockers/budget/SHA) | a short `activeContext.md` CURRENT STATE block ✅ **DONE 2026-08-28** (values are tool-verified at write time, not auto-regenerated on every read — "ideally generated from git/CI/state" stays aspirational) |
| proven reusable workflows | `.claude/memory/procedures/` (procedural memory) |
| completed sessions + checkpoints | `.claude/memory/history/` ✅ **DONE 2026-08-22** |
| falsified hypotheses | `null_results/` |
| durable architecture decisions | `decisions.md` / ADRs |

**`history/` implemented (2026-08-22)**, prompted by an external comparison against
DeepSeek Harness's `.agents/notes/<date>-<slug>.md` pattern — adapted, not copied:
- `hooks/post_commit_memory.py` now writes every commit to a permanent, per-day archive
  (`history/commits-<YYYYMMDD>.md`) *before* touching `activeContext.md`, then caps the
  Auto-commit log section there to the most recent `_ACTIVE_LOG_CAP` (15) entries. Trimming
  the active view is safe because the full record already landed in the archive — this is
  exactly the growth this doc originally flagged ("~23 KB mixing current state with months
  of history").
- A **daily archive**, not one file per commit: DeepSeek's own agent writes one narrative
  file per noteworthy change; mirroring that literally for every mechanical commit (this
  repo's own "docs(memory): auto-log entry for `<sha>`" churn is a good example) would
  multiply tiny files instead of reducing clutter. The richer, hand-written
  `history/<date>-<slug>.md` note (what/why/outcome) is still the right artifact for a
  genuinely noteworthy chunk of work — written by the agent doing the work, not generated
  per commit.

**Rules of the target:**
- `activeContext.md` holds ONLY current state — no long history.
- One canonical memory root (`.claude/memory/`); the legacy root `memory/` is retired once the
  `find_file_upward` resolution is confirmed to prefer `.claude/memory/`.
- The hook auto-append (`post_commit_memory`, `pre_compact`) writes to a bounded log section,
  and a periodic job archives log entries older than the current session to `history/`.

## Also flagged by the audit (separate follow-ups)

- ~~Canonical `decisions.md` missing~~ **DONE (2026-07-16):** `.claude/memory/decisions.md`
  didn't exist — `post_commit_memory.py`'s `find_decisions_file()` and `session_start.py`
  both only ever resolved that exact path, so every `arch:`/`decision:`/`security:`/`pattern:`
  commit silently dropped its entry. Created the canonical file (migrated the legacy file's
  full history verbatim), added a DEPRECATED banner to `memory/decisions.md` matching the
  `activeContext.md` precedent. Verified `find_decisions_file()` now resolves to the canonical
  path. `memory/` itself is still not retired — that's the separate, riskier step below.
- ~~Rules duplication~~ **DONE (2026-07-16):** `rules/` is canonical; the `.claude/rules/`
  copies became a pointer stub (`rationalizations`, `doubt-driven-development` — were identical)
  or a marked addendum (`integrity` — kept only its project delta: vault routing +
  submission gate). Re-duplication is now blocked by `TestRulesNotDuplicated`.
- `autonomy-budget.md` is only in `.claude/rules/` (project) — not installed globally, despite
  being framed as a global autonomy foundation. Move to installable `rules/` or an autonomy skill.
- Few path-scoped rules: science/security/testing rules apply on all tasks (instruction noise).
  Add `paths:` frontmatter so they load only for relevant files.
- A `/config-explain` command (effective config for the session: loaded instructions, active
  rules, skills, memory, permissions, hooks, conflicts) — the `instructions_audit.py`
  (InstructionsLoaded hook) log can seed it.
