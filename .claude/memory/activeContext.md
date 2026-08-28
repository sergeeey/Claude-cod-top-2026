# activeContext.md — Claude-cod-top-2026

<!-- ─────────────────────────────────────────────────────────────────────────
     CURRENT STATE is the authoritative snapshot. Read THIS block first.
     Everything below CURRENT STATE is either durable (Scope Fence) or a
     bounded, auto-written log (Auto-commit log, capped at 15 entries) — never
     a place to accumulate narrative history.

     Split executed 2026-08-28 (docs/memory-architecture.md's own deferred
     target, finally applied): this file had grown to a CURRENT STATE table
     whose single "updated" cell alone was 52,267 characters — the Read tool
     could not return even a 45-line window without exceeding its token cap.
     The full pre-split content (multiple months of accumulated narrative,
     several stale/superseded "Current Focus"/"Project State" sections, a
     duplicated "Recent findings" header) is preserved byte-for-byte at
     .claude/memory/history/pre-2026-08-28-consolidation.md — nothing was
     deleted, only moved. Going forward: keep this table SHORT and current;
     anything narrative or dated belongs in history/, not here.

     Known gap surfaced while doing this split, not fixed here (separate,
     deliberate decision): the LIVE global ~/.claude/hooks/post_commit_memory.py
     on this machine never got the 2026-08-22 update that caps the Auto-commit
     log at 15 entries and archives to history/commits-<date>.md — the repo's
     own copy has that code, but .claude/memory/history/ did not exist on this
     machine until this split created it. Until the live hook is updated, this
     log will grow unbounded again and need another manual trim.
──────────────────────────────────────────────────────────────────────────── -->
## CURRENT STATE (authoritative)

| field | value |
|-------|-------|
| **updated** | 2026-08-28, after PR #284 merged [VERIFIED: `git log -1`] |
| **goal** | Evidence-aware Goal Operating Layer for Claude Code — reusable, verifiable config (hooks/agents/skills/rules), self-checking against its own Falsification Ladder methodology. |
| **branch** | `main` = `ca5439f` (PR #284 merged) [VERIFIED: `git log -1`, `git branch --show-current`] |
| **released** | `v3.10.0` (tag + public GitHub Release); `boyko-baseline-v1`/`v2` are eval-suite reference tags, not releases |
| **hooks / agents / skills** | 96 registry entries (88 wired · 2 dormant · 6 library) / 13 agents + 3 teams / 130 skills [VERIFIED: `docs/hook-control-matrix.md` Totals line, `agents/*.md` minus CLAUDE.md, `find skills -name SKILL.md \| wc -l`] |
| **tests** | 2860 collected [VERIFIED: `pytest --collect-only -q`]; README badge synced to match CI's measured count as of PR #283 |
| **open non-main branches** | 7 on origin, not further triaged this session: `chore/focusos-evening-snr-{20260731,20260801}` (draft PRs #249/#250, decision pending), `docs/skill-disambiguation-deep-research-tracy-fix` (awaiting user's own `git branch -D`), `fix/backport-null-retroscan-identifier-scan` (unmerged `boyko-scientific-consortium` skill, intentionally preserved), `docs/sync-readme-test-count-and-activecontext-merge-status`, `feat/elai-independence-mdr`, `fix/ci-registry-schema-repair` |
| **current focus** | No single active thread — most recent work was a `/boyko-project-radar` full-project sweep (2026-08-28) → Gate 12a (PR #283) → response-guard-fp-calibration parked (PR #284) → this memory split. See `history/pre-2026-08-28-consolidation.md` for what preceded it. |
| **next action** | None blocking. Open candidates from the last `/tracy` strategic pass (2026-08-28): `hooks/session_save.py` split (1043-line God-module, 2 unrelated responsibilities), `utils.py` → `hooks/lib/` migration (stuck at 2/71 call sites since 2026-08-22), 3 named-but-untested shell-obfuscation techniques against `hooks/lib/security.py`. |

## Scope Fence

- **Goal:** production-ready Claude Code config for reuse across any project
- **Boundary:** only `hooks/` `agents/` `skills/` `rules/` — never touch external projects
- **Done when:** `install.sh` works on 3 machines, CI green, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, marketplace publication

## Auto-commit log
- [2026-08-28 18:47] `e2a2e2b`: Merge pull request #285 from sergeeey/docs/memory-split-activecontext-consolidation
- [2026-08-28 16:37] `b9ebe78`: feat(memory): execute activeContext.md CURRENT STATE split, finally applying docs/memory-architecture.md's deferred target
- [2026-08-28 15:47] `858b62e`: docs(experiments): park response-guard-fp-calibration -- stalled 6 weeks, untracked
- [2026-08-28 15:34] `2a73ec4`: docs(readme): sync test count 2842->2854 (9 new Gate 12a tests)
- [2026-08-28 15:30] `7a2eff5`: feat(hooks): Gate 12a -- PREVENT hooks must call hook_main() with explicit fail_closed=
- [2026-08-28 14:34] `2f92f21`: docs(hooks): fix registry.yaml's own header comment listing valid class values
- [2026-08-28 14:33] `ba18ffa`: docs(readme): sync test count 2840->2842 (2 new weakened_test_guard tests)
- [2026-08-28 14:30] `3129c9b`: docs(hooks): document expert_registry.py's real out-of-repo caller
- [2026-08-28 14:29] `f8eb420`: fix(hooks): wrap weakened_test_guard.py's entrypoint in hook_main(fail_closed=True)
- [2026-08-28 14:19] `c8f6f51`: docs(experiments): sync INDEX.md with 3 real but unindexed 2026-08-24 pilots
- [2026-08-28 14:15] `61ed2aa`: docs(hooks): fix blocking-protocol drift in hooks/CLAUDE.md
- [2026-08-23 21:14] `990c5ce`: fix(ci): sync hooks/hooks.json for independence_scorer+mutation_tracker
- [2026-08-23 21:12] `d941fde`: fix(ci): regenerate hook-control-matrix.md for 96 hooks (was 94)
- [2026-08-23 21:09] `302baf6`: fix(ci): add independence_scorer+mutation_tracker to registry.yaml, sync doc counts 94→96
- [2026-08-23 21:04] `49787ee`: fix(hooks): correct emit_hook_result call signature in independence/mutation hooks
- [2026-08-23 20:49] `5fe38d0`: feat(hooks): add ELAI independence scorer + mutation detection rate (MDR)
- [2026-08-22 20:13] `0551b54`: refactor(hooks): split utils.py god module into hooks/lib/{runtime,state,discovery,security}
