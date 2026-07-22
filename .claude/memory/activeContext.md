# activeContext.md — Claude-cod-top-2026

<!-- ─────────────────────────────────────────────────────────────────────────
     CURRENT STATE is the authoritative snapshot. Read THIS block first.
     Everything under "## Recent findings" below is a running LOG (append-only,
     auto-written by hooks) — useful history, but NOT the source of truth for
     "what is true now". When they disagree, CURRENT STATE wins.
     (Memory-architecture debt: this file mixes state + long history; the target
     split — current-state / history / procedural — is docs/memory-architecture.md.)
──────────────────────────────────────────────────────────────────────────── -->
## CURRENT STATE (authoritative)

| field | value |
|-------|-------|
| **updated** | 2026-07-21 (session continuation) |
| **goal** | Evidence-aware Goal Operating Layer for Claude Code — reusable, verifiable config |
| **branch** | `main` = `61953f2` (PR #219 MERGED — gitnexus_reindex hook + 17-commit upstream merge; remote branch deleted post-merge). Mothball `e28819e` still orphaned on local `rebase/pr208-onto-main` (unrelated, old, low priority). |
| **last verified SHA** | `61953f2` (origin/main) — PR #219 CI all green (3.11 ✅ 3.12 ✅ windows-install ✅) after one badge-drift fix (2367→2388, CI-measured; same recurring class as PR #215/#218's). |
| **released** | `v3.10.0` (tag + public GitHub Release) — `CITATION.cff` synced (was stale at 3.9.0) |
| **hooks / agents / skills** | 93 / 13 / 125 |
| **current focus** | PR #219 (this continuation): (1) Built `hooks/gitnexus_reindex.py` (`6b36c73`) — CLAUDE.md falsely claimed a commit/merge hook already auto-refreshed the gitnexus index; none existed, index was stale for months. Async via async_wrapper, file_lock-guarded against concurrent reindexes, commit-only (merge remains a known documented gap). Moved `extract_command_cwd` into shared `utils.py`. Reviewer found + fixed 2 real bugs pre-merge: multi-hop `cd /a && cd /b` resolved to the first dir not the last; the fix for that broke on quoted paths containing a literal `&`/`;`/`\|` (e.g. `"R&D"`), feeding a malformed cwd into `pre_commit_guard.py`'s branch-protection and making it fail OPEN. (2) MCP audit: installed+verified `github-official` (official remote, existing `gh` auth); got `Hugging Face` connector authorized; `bioRxiv` connector (3rd-party deepsense.ai wrapper) still fails OAuth registration server-side, not fixable from this end; declined arXiv/Wolfram Alpha MCPs (only unaudited hobby-repo implementations exist). Incident: `claude mcp get github-official` printed the raw GitHub token in plaintext to session output (unlike `mcp add`, which redacts) — user was told to rotate it. (3) Merged 17 upstream commits from separate work on another machine (skill-staleness fix, false-pass-rate tracking, pre_vault_write hardening, agent-contract fixes) — found a real count-drift: both branches independently added a new hook (`gitnexus_reindex.py` / `verdict_logger.py`) and each locally computed a "92 hooks" badge that coincidentally matched but was wrong for the combined state (true: 93, re-derived via `scripts/sync_doc_counts.py`). |
| **blockers** | None. Housekeeping note: a post-merge activeContext.md update (commit `9d1cd71`) was pushed to `feat/checkpoint-fidelity-gap-b` AFTER `gh pr merge` had already completed the actual GitHub-side merge (using `ce9451d` as tip) — so that commit's content never reached `main` and sits orphaned on the local branch (couldn't force-delete: `git branch -D` is denied by permission policy). This file's fix lands via this separate `docs/sync-activecontext-post-pr219` branch instead. All real code from PR #219 IS in `main` (verified: `git merge-base --is-ancestor ce9451d HEAD` = true). |
| **current focus (prior continuation)** | Methodology-library **infrastructure layer**: (1) `ec81085` — vendored `rules/perelman-audit.md` (was declared by `boyko-triangle-audit` depends_on but never shipped → clean-install dangling) + check_architecture **gate 9** `gate_dangling_rule_dependencies`. (2) `4da25da` — added `kind`/`maturity` taxonomy to all 129 registry entries + **gate 10** `gate_kind_maturity`. Both merged via PR #215/#216/#217/#218 (all landed on `main` before this continuation started). |
| **next action** | Methodology-DEEPENING roadmap (not started): benchmark 8-12 tasks per `docs/methodologies/strong-inference.md` §14 (3 arms; MCID pre-registered) → only if it beats baseline, promote `hypothesis-arbiter` to `maturity: dogfooded` with real `maturity_evidence` → Boyko stage-aware resolver using kind/maturity. |





## Recent findings
[summarized] - 2026-07-19 (later, this session): investigated the "~600/701 orphaned git.exe
    (12/111). Of those with a Related section: 19 use RU `## Связанные скилы`, 22 use
    EN `## Related Skills` — the two-convention split, quantified. Full unification is
    Sprint 5 (Packs), not now.
- 2026-07-14: пользователь прислал "RDR 2.1" (второй, более зрелый вариант того же
  авторского методологического препринта, .docx). Сравнил против реальных файлов
  (grep, не по памяти) — большая часть уже покрыта (Recomposition Gate дословно уже
  есть, Independence levels ≈ вчерашняя Strength Ladder, EVI/Optimal Stopping ≈ CDT
  Protocol). Нашёл 4 реальных новых куска, подтверждено отсутствие через grep:
  Substrate Gate, checkpoint fidelity criterion, typed dependency graph с авто-
  пропагацией статуса, Reproducer role. Не согласился с одним пунктом документа —
  "объединить Pearl+Null registry в одну базу, разделение запрещено" — явно
  возразил, у нас разделение сознательное (разная семантика REJECT/ARCHIVE/Pearl),
  не источник риска. По запросу пользователя реализован ТОЛЬКО Substrate Gate
  (Step 2a в Full-Ladder): READY/BLOCKED-INFRASTRUCTURE/UNTRUSTED-ENVIRONMENT,
  жёсткое правило "test could not run ≠ claim failed" — напрямую связано с
  сегодняшним же F-12 (hook зарегистрирован не на то событие, reachable но не
  enforced — ровно тот класс путаницы, который Substrate Gate должен ловить).
  Добавлено в rules/falsification-ladder.md (global + repo) + шаблон
  experiments/_template/substrate_gate.md. 2125/2127 тестов (2 pre-existing skip),
  ruff clean. Коммичу сейчас, ветка `feat/substrate-gate-fl-step-2a`, ждёт "го, пуш".

## Scope Fence
- **Goal:** production-ready Claude Code config для переиспользования в любых проектах
- **Boundary:** только hooks/ agents/ skills/ rules/ — не трогать внешние проекты
- **Done when:** install.sh работает на trёх машинах, CI зелёный, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, публикация в marketplace









## Recent findings
[summarized] [summarized] [summarized] [summarized] [summarized] - 2026-07-12: **[AVOID×3]** PR #185 (Phase 3) — тот же класс CI-фейл...
  **Reviewer iteration 1: NEEDS_WORK (P2)** -- poymal realnyy false-negative
  gap v moey zhe matcher-consistency logike: has_actual_wildcard schitalsya
  po vsemu hook'u srazu, ne per-event -- iteration_guard's SubagentStop
  registratsiya (matcher='') mogla by zamaskirovat REALNUYU oshibku na ego
  PreToolUse storone (adversarialno podtverdil eto sam do fiksa). Pervaya
  popytka fiksa (hardcode _TOOL_SCOPED_EVENTS={PreToolUse,PostToolUse})
  slomala 2 DRUGIH validnyh entry (env_reload's FileChanged, research_health_loop's
  SessionStart -- oba imeyut REALNYE non-tool-name matchery). Ispravil pravilno:
  vychislyayu events_with_real_matchers DINAMICHESKI iz samih dannyh (kakie
  event'y hot' raz ispolzuyut ne-wildcard matcher gde ugodno v settings.json),
  ne ugadyvayu zaranee. Proveril adversarial'no: simuliroval slomannyy case
  (Agent declared, tolko Bash realno zaregistrirovan) -- teper' korrektno
  FALSE (was True do fiksa). Vse 5 testov + full suite (2113/13) zeleno posle.

  P0.1 (Bash(*) permissions) sознательно NE nachat -- eto smena default
  povedeniya dlya vseh sushestvuyushih ustanovok etogo published plugin,
  trebuet otdelnogo yavnogo resheniya polzovatelya, ne bezopasno dogadyvatsya
  vslepuyu pro allowlist soderzhimoe.

  Full suite: 2113 passed / 13 skipped (bylo 2098), ruff clean.

## Session 2026-06-28 Final State
PR #138 P0-P2 audit ✅ | PR #140 inbox dedup hooks 86→85 ✅ | PR #141 tests 3 hooks ✅ MERGED CI green
P3 triggers: 314/344 SKILL.md ✅ | README badge 1652/75% ✅ | hook count synced all docs ✅
AUDIT DEBT = ZERO. Open PRs = 0. CI = green (3.11+3.12+windows). Obsidian updated.













## Current Focus
[summarized] [summarized] [summarized] [summarized] [summarized] **PR #171 MERGED (2026-07-12, branch `improve/boyko-knowledge-audit-...
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













































































































## Auto-commit log
[summarized] - [2026-07-21 23:14] `bae578f`: docs(memory): sync activeContext with PR #219 merged state
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
