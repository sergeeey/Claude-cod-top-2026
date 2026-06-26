# activeContext.md — Claude-cod-top-2026

## Scope Fence
- **Goal:** production-ready Claude Code config для переиспользования в любых проектах
- **Boundary:** только hooks/ agents/ skills/ rules/ — не трогать внешние проекты
- **Done when:** install.sh работает на trёх машинах, CI зелёный, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, публикация в marketplace






















































## Current Focus
SESSION 2026-06-26: boyko-method evolution + end-to-end skills
BOYKO v1.3.0 (63763ee, feature/boyko-v1.3.0): context: fork в frontmatter (skill теперь в изолированном subagent), строгие evidence criteria (VERIFIED/INFERRED/WEAK/РАЗОРВАНА — каждая требует явный источник до постановки метки), output caps по режимам (Quick: 8/20/3, Standard: 20/60/7, Deep: 40/120/12), fallback для /multi-lens, улучшен description для семантического роутинга.
СКВОЗНЫЕ СКИЛЛЫ (c059016): research-pipeline v2.0, paper-assembly v1.1, incident-response v2.0 — все три переписаны как end-to-end циклы с Feasibility Gate, питает-переходами, quality gates.
ВЕРИФИКАЦИЯ ПРЕДЛОЖЕНИЙ: проверили 5 векторов улучшения boyko — context:fork РЕАЛЬНО (changelog + 3 скилла репо), HaluGate NLI НЕ СУЩЕСТВУЕТ, "60-70% token reduction" ВЫДУМАНО, GraphRAG/Playwright — оверкилл. Внедрили только верифицированные улучшения.
BRANCH STATUS: feature/boyko-v1.3.0 — 1 commit (63763ee), Push pending.
RESEARCH-PIPELINE BUGFIX (aa28bfc, feature/research-pipeline-bugfixes): 8 багов исправлены — days цепочка (funnel+pipeline+verifier), /30.0→/float(days), Step 0 FP filter, import math→module level, _fetch_hn() реальный HN Algolia API, 5 стабов→NotImplementedError, whole-word match в _cluster_by_theme.
PENDING: push обоих feature branches в main.

SESSION 2026-06-23: sync + install + skill improvement
SYNC: git pull origin main — 40 новых коммитов с прошлой сессии (e32cf54). 19 новых хуков, 2 новых скилла, новые templates.
INSTALL: скопированы 19 новых хуков в ~/.claude/hooks/ (83 total). Skills: hypothesis-revival + wealth-protocol добавлены в ~/.claude/skills/extensions/. Registry обновлён.
HYPOTHESIS-REVIVAL v1.1.0 (2893b7e): добавлены 4 anti-hallucination guards по review пользователя — DEATH_REASON (disproven=hard skip), ENABLER_STRENGTH 0-10 (blocks buzzword enablers), KNOWN_REFUTATION_CHECK (post-2015 kill search), TOY_TEST_1DAY (обязательный 1-day falsifiable test). Hard rule: "Revival forbidden unless old blocker explicitly removed by concrete modern enabler."
[summarized] [summarized] [summarized] [summarized] [summarized] [summarized] [summarized] [summarized] [summarized] [summarized] [su...
FVA-RAG: research-scout --anti-context mode — kill queries first, prevents confirmation bias (fde0bfd)
PERELMAN AUDIT: claim_entropy + no-collapse tests in templates; perelman-audit.md rule (e099aef)
COUNTERFACTUAL FRAME: Step -0.5 in FL stack; claim.md §§ Counterfactual Frame (898f3ea)
CLAIM ENTROPY TRACKER: hooks/claim_entropy_tracker.py — PostToolUse(Write|Edit) on experiments/**/claim.md. Parses entropy table, enforces monotone decrease, nudges on violation. 31 tests. Registered globally. (e9cd6cd)
HOOK SYNC: 19 global-only hooks brought into git tracking + 6 audit scripts. 58 hooks in worktree now matches global. (a66eb1e)
P1 DONE: null_results_pre_check (UserPromptSubmit, ≥2-token slug match vs null_results/) + promotion_gate_guard (PostToolUse/decision.md, 5 Perelman conditions). 40 tests. Deployed + registered. (ebb0169)
SCOPE FENCE STATUS: CI ✅ coverage 81% ✅ | PENDING: install.sh on sboi
DISTRIBUTION SPRINT: Step 1 ✅ + Step 2 ✅ | Step 3 (Habr) on hold | Step 4 Day 4 of 7
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
OBSIDIAN: graph.json colorGroups reset by app — set only while Obsidian is CLOSED.
LATEST CHECKPOINT: .claude/checkpoints/2026-05-06_pr106-attention-decay-merged.md

## Project State
- **Version:** 3.9.0 (updated 2026-06-14)
- **Branch:** main green CI ✅
- **Tests:** 1387 collected (2026-06-14, local)
- **Coverage:** 81% (CI/Linux, canonical)
- **Hooks:** 80 .py files in hooks/ (tracked in main repo, incl. 19 synced from global 2026-06-20); doc_bridge.py + doc_registry.py + expert_registry.py + file_auto_parser.py in ~/.claude/hooks/ (global)
- **Skills:** 115 (hypothesis-revival v1.1.0 = latest, 2026-06-23)
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
- Next: merge PR #57 → sync hooks → install.sh на 2-й машине






















































## Auto-commit log
- [2026-06-26 17:54] `aa28bfc`: fix(research-pipeline): 8 bugs вЂ” days propagation, HN impl, explicit stubs, FP filter
- [2026-06-26 17:41] `63763ee`: feat(boyko): v1.3.0 вЂ” context: fork, evidence criteria, output caps
- [2026-06-26 17:24] `c059016`: feat(skills): 3 skills в†’ СЃРєРІРѕР·РЅРѕР№ С†РёРєР» v2.0 (research-pipeline, paper-assembly, incident-response)
- [2026-06-26 16:44] `03ff403`: feat(skills): boyko-method v1.2.0 вЂ” Feasibility Gate + quick/deep modes + Stage 3 example + triggers array
- [2026-06-26] `0009823`: fix(skills): boyko-method plugin.json — add trigger + fix schema (скилл был невидим)
- [2026-06-26 16:40] `0009823`: fix(skills): boyko-method plugin.json вЂ” add trigger field + fix schema
- [2026-06-23 17:41] `54b75cd`: fix(skills): ab-test v1.1.1 вЂ” 3 code correctness bugs
- [2026-06-23 17:35] `24f33b1`: feat(skills): ab-test v1.1.0 вЂ” 5 statistical improvements
- [2026-06-23 17:31] `8fa66c5`: fix(skills): hypothesis-revival plugin.json вЂ” add trigger field
- [2026-06-23 17:26] `e568b19`: fix(skills): hypothesis-revival v1.1.0 вЂ” 6 reviewer bugs fixed
- [2026-06-23 17:21] `2893b7e`: fix(skills): hypothesis-revival v1.1.0 вЂ” 4 anti-hallucination guards
[summarized] [summarized] [summarized] [summarized] [summarized] [summarized] [summarized] [summarized] [summarized] [summarized] - [...
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
