# activeContext.md — Claude-cod-top-2026

## Scope Fence
- **Goal:** production-ready Claude Code config для переиспользования в любых проектах
- **Boundary:** только hooks/ agents/ skills/ rules/ — не трогать внешние проекты
- **Done when:** install.sh работает на trёх машинах, CI зелёный, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, публикация в marketplace




















## Current Focus
**[2026-05-15] Session additions (commits 83905ea → 5f4418d):**
- FL (Falsification Ladder) framework: experiments/_template/ (8 files), null_results/, parked/
- GSD integration: ~/.claude/settings.json (9 hooks), skillListingBudgetFraction=0.03
- ResearchOps v0.4 adoption: hooks/registry.yaml, scripts/validate_experiment.py, scripts/ev_score.py, scripts/consistency_audit.py, emit_permission_decision() in utils.py, permissionDecision migration for security_verify+pre_commit_guard
- B4 fix: input_guard TRUSTED_MCP_PREFIXES allowlist → 87 false-positives/12d eliminated
- B1 coverage: 4 new test files (1381 lines) → hooks+scripts 68%→77%
- B2 Evidence Policy: evidence_guard.py now knows [VERIFIED-REAL/SYNTHETIC/INLINE], docs/evidence-policy.md unified

**Tests: 1304** | hooks+scripts coverage: 77% | CI/Linux full: ~81% | Open PRs: 0
**HOOKS: 58 active** (registry.yaml = source of truth)
SCOPE FENCE: CI ✅ | PENDING: install.sh on sboi (A1, requires 2nd machine — BLOCKED-EXTERNAL)
KNOWN ISSUES: none active (input_guard FP resolved)
LESSON [AVOID×1]: scoped local ruff hides full-repo F401. Always `ruff check .` (full) before push.




















## Project State
- **Version:** 3.8.0
- **Branch:** main green CI ✅
- **Tests:** 1167 passing (was 1077 at session start; +90 net across 7 PRs)
- **Coverage:** 81% (CI/Linux, canonical) / 86% (local/Windows)
- **Hooks:** 57 active (settings.json + filesystem in sync; +skeptic_auto_trigger, +rationalization_detector, +redact_secrets layer)
- **Smoke tests:** 130/130 skills, 82/82 hooks
- **Open PRs:** 0
- **Last checkpoint:** `.claude/checkpoints/2026-05-06_distribution-sprint-step2-done.md`




















## Architecture
- `hooks/` — 49 хуков (.py) + utils.py + learning_tips.py, 27 событий в settings.json
- `agents/` — 14 агентов + 3 команды (build/review/research squad)
- `skills/` — 27 skills (8 core + 19 extensions)
- `tests/` — 37 тест-файлов, pytest + bash smoke
- `rules/` — 9 markdown-правил
- `mcp-profiles/` — 3 профиля (core / deploy / science)
- `assets/` — banner.svg (animated) + pipeline.svg + preview_design.html




















## Recent Merges
- #74 feat: career-prep skill + mentor_nudge contextual interview questions ✅
- #73 feat: BSV cards for all 23 skills ✅
- #66 fix: CI smoke tests + README metrics — plugin.json × 8 skills, badge 848/65%, arch 48 hooks
- #65 feat: 21 tests for knowledge hooks + mypy/ruff CI fixes + docs update
- #64 chore: post-merge sync v3.6.2
- #63 fix: wiki index 100% coverage — cap removed, chunk files skipped
- #61 feat: plugin manifest — /plugin install claude-cod-top-2026
- #60 feat: rate limits в statusline — 5h/7d + countdown
- #59 fix: __future__ stdlib allowlist
- #57 fix: 7 review-squad bugs (cherry-pick)
- #56 feat: contradiction detector + inbox review + goal-scoped categories
- #55 feat: Second Brain 4.0 — wiki index, scientific-research, prompt inject, wiki reminder
- #54 feat: 5 obsidian skills + daily vault refresh cron
- #53 feat: CogniML integration + auto-detect new projects at session start




















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
- Next: merge PR #57 → sync hooks → install.sh на 2-й машине




















## Auto-commit log
[summarized] [summarized] [summarized] [summarized] - [2026-05-06 15:48] `2f75655`: fix(ci): README freshness — 1187→1192 tests after...
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
