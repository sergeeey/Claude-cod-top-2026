# activeContext.md — Claude-cod-top-2026

## Scope Fence
- **Goal:** production-ready Claude Code config для переиспользования в любых проектах
- **Boundary:** только hooks/ agents/ skills/ rules/ — не трогать внешние проекты
- **Done when:** install.sh работает на trёх машинах, CI зелёный, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, публикация в marketplace
































































































## Session 2026-06-28 Final State
PR #138 P0-P2 audit ✅ | PR #140 inbox dedup hooks 86→85 ✅ | PR #141 tests 3 hooks ✅ MERGED CI green
P3 triggers: 314/344 SKILL.md ✅ | README badge 1652/75% ✅ | hook count synced all docs ✅
AUDIT DEBT = ZERO. Open PRs = 0. CI = green (3.11+3.12+windows). Obsidian updated.





## Current Focus
**RETROSPECTIVE + PROCESS TOOLING (2026-07-07 ~20:00, branch `chore/pre-commit-checklist-and-readme-gate`):** User asked why, given all this methodology, so many findings still slipped through across the last 3 days — answered honestly (root causes, not excuses): (1) mypy was dropped from the routine "ran the checklist" muscle memory for a full day despite being in CLAUDE.md's mandatory list — 3 mechanical steps to remember under session-length pressure is fragile; (2) README badge drift is documented `[AVOID×4]` (PR #115/#124/#125) and STILL recurred twice more this session — a reactive "fix when CI complains" sync isn't a real fix for a known-recurring pattern; (3) point-fixes (RF-01's first pass) missed mirrored/parallel cases of the same bug; (4) long-lived branch absorbed unrelated drift from main in one late surprise instead of incremental syncs; (5) a tool that teaches "catch fake rigor" (boyko-knowledge-audit) wasn't checked against its own standard until asked; (6) 3 real ambiguities in that skill were found only by an agent ACTUALLY RUNNING it, not by rereading it.

Implemented 2 concrete process fixes the user asked for:
- `scripts/pre_commit_checklist.py` — runs ruff+mypy+pytest as ONE command (`--fast` skips pytest), so "ran the checklist" means "ran one script," not "recalled 3 commands." Does NOT replace the reviewer/cross-model steps (those need an Agent).
- `hooks/pre_commit_guard.py` Check 5 — README Tests-badge freshness, WARNING only, gated to commits touching `tests/` or `skills/` (the only real inputs to the count). Uses `pytest --collect-only` (~1-15s, not the full ~150s suite) so it's cheap enough to run on every relevant commit. Directly targets the `[AVOID×4]` pattern that a purely reactive CI check didn't stop from recurring.

9 new tests (parsing, fail-open on timeout, end-to-end warn/silent/skip via `main()`). Full suite: 2034 passed, ruff clean, mypy clean (115 files). Wrote up the retrospective as an Obsidian note (`knowledge/lessons/Lesson — Methodology Coverage vs Enforcement Gap.md`).

**REVIEWER CAUGHT A REAL P1 BEFORE PUSH (commit `49a0a7c`, not yet pushed):** the reviewer-agent pass hit the Evaluator-Optimizer cap (4th non-LGTM verdict) and escalated rather than looping again. Its P1: Check 5's local-vs-badge count comparison is fundamentally unreliable — `scripts/sync_readme_from_ci.py`'s own docstring documents local pytest counts MORE tests than CI (env-dependent tests). Independently measured before accepting: local `--collect-only` reported 2034 against a README badge of 2009 that CI had JUST correctly synced — a 25-test gap with zero real staleness. Confirmed real, not a false alarm. **Redesigned Check 5**: removed `_collected_test_count`/`_readme_test_badge_count` and the whole count-comparison approach; replaced with an unconditional reminder on the same trigger (staged `tests/`/`skills/` files) pointing at `scripts/sync_readme_from_ci.py`, without running pytest locally at all — sidesteps the local-vs-CI ground-truth problem entirely instead of guessing with an untrustworthy number. 3 tests replaced the 9 (net -5, since the removed functions' unit tests are gone too). Full suite re-verified: 2029 passed, ruff clean, mypy clean. **Still pending:** commit this fix, push, open PR.

**PR #170 CI-GREEN (2026-07-07 ~12:30):** https://github.com/sergeeey/Claude-cod-top-2026/pull/170, fix/pre-compact-dedup → main. All 3 external-audit findings + RF-01 (SessionStart trust-critical list expanded, incl. `.claude/<name>/` duplicates found by reviewer P1) + 2 real CI regressions found ONLY by insisting on runtime evidence over log claims:
1. mypy failures (4 errors, pre-existing on this branch from earlier commits, not today's fixes) in weakened_test_guard.py (`HookState.get()` returns `object`, narrowed with `cast(dict, ...)`) and promotion_gate_guard.py (`tool_input.get()` on untyped dict → `Any` into `-> str` fn, wrapped in `str(...)`). **Lesson applied against self:** had only run ruff+pytest all session, never mypy — this repo's own "verified subset, claimed whole" [AVOID×4] pattern.
2. hypothesis_router.py's memory-path check used `Path(event["file_path"])`, host-OS-dependent — Windows-style test fixtures (`r"C:\Users\...\.claude\memory\..."`) parse into multiple `.parts` on WindowsPath but become ONE opaque component on PosixPath (Linux CI), so the file silently was never recognized as a memory-path hypothesis file when the hook (or its tests) ran on non-Windows. Fixed by normalizing backslash→forward-slash before `Path()` construction — portable regardless of host OS. Confirmed via direct PurePosixPath/PureWindowsPath comparison before fixing, not just inferred from the CI log.
3. README Tests/Coverage badge (1730/75%) hadn't been re-synced across ~275 tests added over many commits on this branch — `scripts/sync_readme_from_ci.py` only pulls from `main`'s latest run (doesn't reflect this branch), so let the fixed CI run itself report its own authoritative line (`Actual: 1989 tests, 80% coverage`) and synced README to match exactly, rather than hand-editing from local pytest count (this repo's own recurring mistake, PR #115/#124/#125).

**SECOND EXTERNAL RE-AUDIT + FULL RESPONSE (2026-07-07 ~13:30):** User pasted a full independent re-audit of public `main` (9 findings F-01..F-09) plus their own quick self-recheck against local code. Per audit-verification-gate.md, independently re-verified EVERY finding myself (not trusting either the audit or the pasted self-recheck) before acting — several were already stale:
- F-01 (input_guard key-scanning), F-02 (regex `||` bug) — already fixed / never reproduces on current code (confirmed by reading the file directly).
- F-03 (validation-theater URL bypass) — mostly already fixed; the residual (a URL adjacent to the literal word "dataset" still counts as evidence) is this repo's own KNOWN, documented ceiling of regex-based detection, not a fresh bug — left alone.
- F-04 (permission_policy `cat .env`/Task) — `cat .env` already fixed (returns `ask`); `Task`/`WebFetch`/`WebSearch` genuinely blanket-`allow`, but severity is lower than claimed since a subagent's own inner Bash/Write calls re-trigger this same hook independently — left alone (full allowlist rewrite would break normal workflow for marginal gain).
- F-05, F-06, F-07(residual), F-08, F-09 — all CONFIRMED REAL, fixed (see commits below).

Rated the user's own proposed 5-PR mega-plan 5/10 as written (solid engineering instincts, 8/10 in isolation, but 3 of 5 PRs targeted already-fixed things since it wasn't checked against this branch's actual state first) — descoped to the 5 genuinely-open items and executed:
- `9ae3adf` — pre_vault_write.py was DEAD CODE: read `hook_input["parameters"]` (real schema field is `tool_input`) AND was never registered in settings.json. Also found a second latent bug while fixing: its own `"/.claude/memory" not in file_path` pre-check used a forward-slash literal that never matches Windows paths — would've been a no-op on this repo's primary dev OS even after the schema fix. Removed it (validate_vault_write()'s own portable `.resolve().relative_to()` check is the real gate). Now wired under PreToolUse Edit|Write, uses get_tool_input()/emit_permission_decision() like every other hook, reconstructs Edit content via old_string/new_string. 6 new tests.
- `260f52b` — scripts/redact.py now redacts dict KEYS too (mirrors input_guard.py's already-fixed bug). Deliberately did NOT change its fail-open-on-malformed-JSON behavior — that's a consistent repo-wide convention (input_guard.py does the same), not a bug unique to this file. 4 new tests.
- `670ffaa` — hooks/hook_state.py: atomic writes (tempfile.mkstemp + fsync + os.replace) instead of plain write_text — a crash mid-write no longer corrupts/resets existing state to `{}`. 3 new tests.
- `20fc59c` — hooks/webhook_notify.py: SSRF check now resolves DNS (socket.getaddrinfo, 3s timeout, fails open on resolution failure matching repo convention) and checks every resolved address, not just the literal hostname string — a domain pointed at 169.254.169.254 no longer sails through. 7 new tests (all mocked, no real network). Also fixed test_structure.py's stdlib-only allowlist (`socket` is genuine stdlib, just never imported by a hook before).
- `cc78cc0` — install.sh: last30days-skill clone now pinned to a reviewed commit SHA (verified via direct `curl` to GitHub API, length-checked with Python `len()`, not eyeballed) — closes the "opt-in flag still silently pulls different code every install" residual gap left after the earlier opt-in fix.

Full local suite: 2025 passed, ruff clean, mypy clean. `tests/test_install.sh`: 20/20 passed (incl. new Test 12). All 6 commits pushed (89e2586). New CI run failed on the now-expected README badge drift (2009 actual vs 1989 stale) + a cascade-canceled 3.11 job (not a real failure — GitHub Actions matrix `fail-fast` canceled 3.11 mid-run because sibling 3.12 failed first). Fixed badge (9930aab), pushed, re-ran CI: **all green** — test(3.11) ✓, test(3.12) ✓ (README metrics, doc-counts, registry↔disk, smoke tests, syntax, secrets, author-paths, skill-artifacts all pass), windows-install ✓, eval skipping (by design).
**PR #170 fully done, CI-green, nothing pending** unless the user wants to merge or asks for another round.

Final commits: e3f98e0 (mypy), ddb59c1 (hypothesis_router), 153a997 (README badge). **All CI checks pass**: test(3.11) ✓, test(3.12) ✓ (incl. README metrics, doc-counts, registry↔disk, smoke tests, syntax, secrets, author-paths, skill-artifacts), windows-install ✓, eval skipping (by design, manual/schedule-only). **Nothing left pending on this PR** unless the user wants to merge it or asks for further review.
[summarized] [2026-07-07] hooks-03 atom CLOSED across 4 commits: both HIGH path-traversal + all 7 MEDIUM race/dedup + all 3 LOW findi...
HOOK SYNC: 19 global-only hooks brought into git tracking + 6 audit scripts. 58 hooks in worktree now matches global. (a66eb1e)
P1 DONE: null_results_pre_check (UserPromptSubmit, ≥2-token slug match vs null_results/) + promotion_gate_guard (PostToolUse/decision.md, 5 Perelman conditions). 40 tests. Deployed + registered. (ebb0169)
SCOPE FENCE STATUS: CI ✅ coverage 81% ✅ | PENDING: install.sh on sboi
DISTRIBUTION SPRINT: Step 1 ✅ + Step 2 ✅ | Step 3 (Habr) on hold | Step 4 Day 4 of 7
AUDIT DEBT CLEANUP: PR #138 (P0-P2 fixes) ✅ merged | PR #140 (inbox_review dedup + ruff E902) ✅ merged | PR #141 (tests for 3 PR#138 hooks: env_reload CLAUDE_ENV_FILE guard, expert_registry __import__ sandbox, pre_vault_write Path.home()) → open, 1656 passed
P3 DONE: triggers: field added to 314/344 SKILL.md via scripts/add_triggers.py (29 already had, 1 symlink skip). Extracted from description Triggers: text where available, fallback: name+keywords. All P0-P3 audit items CLOSED.
STATUS: AUDIT DEBT = ZERO. Pending: PR #141 merge.
mcp-bouncer: LIVE on PyPI 0.1.0 ✅ https://pypi.org/project/mcp-bouncer/ | Show HN: READY TO POST
EVALUATOR-OPTIMIZER GUARD: max_iterations=3 added to review-squad.md + CLAUDE.md ✅
SKEPTIC GAPS: 4/5 closed | OPEN: independent test set
ARTIFACTS LIVE: docs/anti-hallucination.md (gist), scripts/hook_metrics.py (CLI dashboard)
TELEMETRY: ~/.claude/logs/hook_triggers.jsonl 90+ entries, run `python scripts/hook_metrics.py --window 7`
CI HISTORY: was RED for 5 PRs (#98-#103) due to repo-wide ruff scoping — fixed in PR #104. Now GREEN.
ATTENTION DECAY: HOT/WARM/COLD scoring live in knowledge_librarian (PR #106) — path traversal + prompt injection + OOM fixed before merge by review-squad.
KNOWN ISSUES:
  - input_guard false-positive on mcp__context7__query-docs (27 blocks/2d) — wait for 7d data before narrowing regex
LESSON [AVOID×1]: scoped local ruff hides full-repo F401. Always run `ruff check .` (full) before push, not just changed files.
LESSON [AVOID×1]: memory-file hooks (pre_compact.py) that "carry forward" pending items need a dedup check and must scan section HEADINGS (not just bodies) for staleness dates — otherwise a note tied to an already-merged PR silently re-duplicates every compaction forever (44x observed) and a dated heading like "## Retrospective [date]" never ages out. Fixed in e20ae2f.
OBSIDIAN: graph.json colorGroups reset by app — set only while Obsidian is CLOSED.
LATEST CHECKPOINT: .claude/checkpoints/2026-05-06_pr106-attention-decay-merged.md

## Project State
- **Version:** 3.9.0 (updated 2026-06-14)
- **Branch:** main green CI ✅
- **Tests:** 1621 collected (2026-06-27, local — +234 from OpenCode borrow sprint)
- **Coverage:** 81% (CI/Linux, canonical)
- **Hooks:** 80 .py files in hooks/ (tracked in main repo, incl. 19 synced from global 2026-06-20); doc_bridge.py + doc_registry.py + expert_registry.py + file_auto_parser.py in ~/.claude/hooks/ (global)
- **Skills:** 114+ (wealth-protocol = latest addition per git log)
- **Open PRs:** 0 (PR #133 was current branch worktree — utils.py E501 fix)
- **Last checkpoint:** `.claude/checkpoints/2026-05-06_distribution-sprint-step2-done.md`





































































































## Architecture
- `hooks/` — 80 .py файлов в репо + 4 глобальных в ~/.claude/hooks/ (doc_bridge, doc_registry, expert_registry, file_auto_parser)
- `agents/` — 14 агентов + 3 команды (build/review/research squad)
- `skills/` — 114+ skills (core + extensions; latest: wealth-protocol, ab-test, pre-mortem, hypothesis-revival)
- `tests/` — 1387 тестов, pytest + bash smoke
- `rules/` — 9 markdown-правил
- `mcp-profiles/` — 3 профиля (core / deploy / science)
- `assets/` — banner.svg + pipeline.svg
- **Reasoning cache stack** (~/.claude/hooks/):
  - `doc_bridge.py` — парсит PDF/Excel/CSV/JSON/DOCX → structured dict
  - `doc_registry.py` — content-addressed (SHA256) реестр документов; recall notice вместо повторного анализа
  - `file_auto_parser.py` — UserPromptSubmit hook; автоматически парсит файлы из промпта; cache key = SHA256 для файлов < 10 MB
  - `expert_registry.py` — реестр скомпилированных Python-экспертов; v1-v4 features





































































































## Recent Merges (последние известные, 2026-06-14)
- #133 fix: utils.py E501 — split Russian phone redact_pii regex (1d18e4f) [current branch worktree]
- #108 feat: FVA-RAG anti-context mode + HD-MAVP claim template (fde0bfd)
- #107 feat: experiment_insight hook — auto-capture FL decision.md insights (bb3bc29)
- #106 feat: HOT/WARM/COLD attention scoring in knowledge_librarian ✅
- Older: see git log --oneline в репо





































































































## Key Features Added This Sprint
[summarized] [summarized] [summarized] [summarized] [summarized] [summarized] [summarized] [summarized] [summarized] [summarized] [su...
- **Audit Verification Gate:** `subagent_verify.py` Check 4 + `rules/audit-verification-gate.md`
- **Session Retrospective:** новый skill `/retro` + 4-stage workflow labels в routing-policy
- **Raw→Wiki pipeline:** `session_save.py` Step 4 — автоконвертация заметок из `raw/` в `wiki/`
- **ACE Reflector:** `ace_reflector.py` — SubagentStop hook, классифицирует подход, обновляет playbook.md
- **Syntax Guard:** `syntax_guard.py` — PreToolUse(Write/Edit) AST-валидация Python/JS до записи на диск
- **Knowledge Librarian:** `knowledge_librarian.py` — SessionStart, инжектирует wiki + patterns + playbook в контекст
- **Wikilinks в wiki:** `session_save.py` — автоматические [[Related Notes]] по тегам
- **5 Obsidian skills:** obsidian-markdown, obsidian-cli, obsidian-bases, json-canvas, defuddle
- **Wiki Index (Karpathy map):** `session_save.py` Step 5 — генерирует index.md из wiki/ (O(1) vs O(N) grep)
- **Scientific Research skill:** KILL_CRITERIA + baseline + red team + falsification gates
- **plan_mode_guard milestones:** алерт только на {3, 5, 10, 20, 30, 50} файлах — конец alert fatigue
- **prompt_wiki_inject:** UserPromptSubmit — инжекция wiki перед каждым промтом (не только SessionStart)
- **wiki_reminder:** Stop hook — детектор решений (3+ keywords EN+RU) + debounce 5 мин + 2MB limit
- **Recursion guard:** `CLAUDE_INVOKED_BY` в session_save + auto_capture + prompt_wiki_inject — защита от Agent SDK loops
- **Contradiction detector:** `session_save._detect_contradictions` — tag overlap + [AVOID]/[REPEAT] opposing markers
- **Goal-scoped categories:** `_assign_category(tags)` — auto-assign research/hooks/skills/patterns/obsidian/tools/general
- **Inbox review:** `scripts/inbox_review.py` — weekly batch processor для ~/.claude/memory/inbox/ с rich cross-linking
- **Rate limits statusline:** `hooks/statusline.py` — 5h/7d usage windows с countdown и цветовой индикацией (v2.1.80+)
- **Plugin System:** `.claude-plugin/plugin.json` + `marketplace.json` — установка через `/plugin marketplace add sergeeey/Claude-cod-top-2026`
- **Wiki index 100%:** `update_wiki_index()` — убран cap [:8], исключены chunk-файлы `_N.md`. Было: 52/1444 (3.6%) → стало: 199/199 (100%)

## Install Command (for other projects)
```bash
bash install.sh --profile=standard --non-interactive
```





































































































## Test Status
2026-04-19: 972 passed, 0 failed (branch fix/ci-green-972-tests)





































































































## Retrospective [2026-04-12]
- Worked: cherry-pick для bug fixes после squash merge — clean PR без переписывания истории [REPEAT]
- Avoid: squash merge с 2+ коммитами — второй теряется; закрывать PR только после `git log --oneline` на main [AVOID ×2]
- Done: PR #57 merged 2026-04-12. Remaining item (install.sh на 2-й машине) tracked in goals.md → Текущие / открытые.





































































































## Auto-commit log
- [2026-07-07 19:41] `49a0a7c`: feat(process): unified pre-commit checklist + README-drift gate
- [2026-07-07 19:36] `06e57b3`: Merge pull request #170 from sergeeey/fix/pre-compact-dedup
- [2026-07-07 15:24] `9930aab`: fix(ci): sync README Tests badge to CI-authoritative count (2009)
- [2026-07-07 14:46] `89e2586`: chore(memory): document second external re-audit response (F-05/06/07/08/09)
- [2026-07-07 14:45] `cc78cc0`: fix(security): pin last30days-skill clone to a reviewed commit SHA
- [2026-07-07 14:44] `20fc59c`: fix(security): webhook_notify.py SSRF check must resolve DNS, not just the literal hostname
- [2026-07-07 14:43] `670ffaa`: fix(security): hook_state.py atomic writes, not truncate-then-write
- [2026-07-07 14:43] `260f52b`: fix(security): redact.py must redact dict keys, not just values
- [2026-07-07 14:43] `9ae3adf`: fix(security): pre_vault_write.py was dead code -- wrong schema, never wired
- [2026-07-07 14:13] `a3bd066`: chore(memory): consolidate PR #170 CI-green status
- [2026-07-07 14:11] `153a997`: fix(ci): sync README Tests/Coverage badge to CI-authoritative count
- [2026-07-07 14:09] `ddb59c1`: fix(ci): hypothesis_router.py memory-path check fails on Linux CI
- [2026-07-07 14:00] `73ff139`: chore(memory): document mypy CI fix + README badge drift found
- [2026-07-07 13:59] `e3f98e0`: fix(ci): resolve mypy failures blocking PR #170's public CI run
- [2026-07-07 13:35] `08c5358`: chore(memory): document reviewer P1/P2 fix + push status
- [2026-07-07 13:35] `d70d5b2`: fix(security): close reviewer P1/P2 on RF-01 trust-critical list
- [2026-07-07 13:26] `a25ccdf`: chore(memory): document RF-01 fix + push status
- [2026-07-07 13:25] `3d26564`: fix(security): expand SessionStart trust-critical path list (RF-01)
- [2026-07-07 13:02] `7e0fb6a`: chore(memory): auto-commit log entry for 3799967
- [2026-07-07 09:47] `3799967`: chore(memory): auto-commit log entry for 4e8105a
- [2026-07-07 09:43] `4e8105a`: chore(memory): confirm reviewer P1 fix already closed, dedup applied
[summarized] - [2026-07-07 09:32] `b1eb11a`: chore(memory): document reviewer P1 fix + final commit for 3 security decisions
- [2026-04-12 22:52] `9853e45`: feat: rate limits in statusline — 5h/7d windows with countdown
- [2026-04-12 17:07] `faa3421`: fix: add __future__ to stdlib allowlist in test_all_hooks_stdlib_only
- [2026-04-12 17:05] `7b52d13`: chore: post-merge sync — v3.6.0, 827 tests, Open PRs: 0, next → install.sh 2nd machine
- [2026-04-12 16:59] `1e8a7a6`: chore: update activeContext — v3.6.0, 827 tests, PR #57 fix open
- [2026-04-12] PR #57: fix: 7 bugs/risks from review-squad (cherry-pick of 37a69fd)
- [2026-04-12] PR #56: feat: contradiction detector + inbox review + goal-scoped categories
- [2026-04-12 17:xx] `772fb58`: feat: UserPromptSubmit wiki inject + Stop wiki reminder + recursion guard
- [2026-04-12 17:xx] `3a4b0c1`: fix: 807 tests green — WIKI_INDEX mock + milestone assertion
- [2026-04-12 15:25] `a9b45ba`: feat: wiki index.md — Karpathy navigation map for knowledge base
- [2026-04-12 15:16] `3fbbb6e`: feat: scientific-research skill + plan-mode-guard milestone alerts
- [2026-04-12 14:50] `6287505`: feat: add 5 obsidian skills + daily vault refresh cron
- [2026-04-12 14:41] `3179a60`: feat: auto-detect new projects at session start (#53)
- [2026-04-12 13:56] `74475cb`: feat: auto_capture.py — automatic git commit + test failure → raw/ notes
- [2026-04-12 12:10] `f6125fc`: feat: populate_vault.py — seed Obsidian from git/CogniML/patterns/retro
- [2026-04-12 11:36] `a4d24c3`: feat: CogniML integration — semantic search fallback + wiki push (#53)
- [2026-04-12 11:30] `eea259d`: feat: Second Brain 3.0 — ACE Reflector, Syntax Guard, Knowledge Librarian, Wikilinks (#52)
- [2026-04-09] `9a7a99a`: feat: Raw→Wiki pipeline (#51) — 755 tests, 20 skills
- [2026-04-09] Sprint 3: PRs #44 #45 #46 merged — 746 tests, 9 rules, 18 skills
- [2026-04-06] `c348dd0`: feat: Speed Mode + Causal Debugging (PR #42)
- [2026-04-05] `840a8f3`: feat: coverage 45%→86% + cyberpunk visual identity (PR #40)
