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
**PR #170 MERGED (2026-07-07 ~13:22, commit `06e57b3`):** All 3 external-audit findings + RF-01 + 5 more findings from a second independent re-audit (F-05/06/07/08/09, all confirmed real and fixed: pre_vault_write.py dead code, redact.py key-redaction, hook_state.py atomic writes, webhook_notify.py DNS-resolution SSRF check, install.sh commit-pin) + 2 real CI regressions (mypy errors, hypothesis_router.py host-OS-dependent path parsing) + README/doc-count drift from an unrelated main commit that had to be fixed to make the branch mergeable at all. Full history in earlier session log; PR is closed, `main` verified post-merge to actually contain all fixes (`git show origin/main:<file>` on all 5), CI green on the merge commit itself.

**boyko-knowledge-audit skill v3.1.1 (2026-07-07 ~19:00, branch `improve/boyko-knowledge-audit-skill`, commit `de27b21`):** User asked to rate this newly-merged skill (epistemic claim-classification audit tool) — rated 7/10: strong core taxonomy (Level 3-P vs 3-M distinction genuinely useful) but 6 real flaws (fake-precision rigor_score weights with no calibration — the exact "math elegance as evidence" pattern the skill itself teaches auditors to catch; near-tautological `classification_appropriateness_rate`; no cross-reference to this repo's existing epistemics stack — estimand-ops/falsification-ladder/hypothesis-arbiter/sabine/research-methodology — duplication risk; 638-line monolithic SKILL.md violating this project's own skill-creator convention; no evals; no adversarial/cross-model verification of its own classifications). Fixed all 6, then **actually tested it**: spawned a subagent to follow the skill's real instructions (not just read them) on a fresh Physics eval case with genuine Level 3+ claims — it correctly executed the new Step 5.7 (Adversarial Downgrade Check), downgrading a bare "Maxwell's equations" mention and an unproven "follows deductively" claim to Level 0, but surfaced 3 more real ambiguities in the instructions (no tie-breaker for canonical/textbook claims vs novel ones; ambiguous numerator bucket for a claim downgraded mid-check; "[8 секций]" leftover from before the 3-P/3-M split, should be 10). Fixed all 3. SKILL.md restructured 638→547 lines (Domain Modes, full hierarchy criteria, and Worked Example moved to `references/`), added `evals/evals.json` (3 cases), bumped plugin.json/registry.yaml to 3.1.1. Installed to `~/.claude/skills/boyko-knowledge-audit/` (flat layout, matching every other installed skill — confirmed via `ls ~/.claude/skills/`, not the `extensions/` subpath the repo source uses). Registry consistency verified (0 orphans), skill count unchanged (120). **Still pending:** push branch, open PR, verify CI green, merge (not yet done as of this note).
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
- [2026-07-07 19:03] `de27b21`: fix(skills): boyko-knowledge-audit v3.1.1 -- fix fake-rigor scoring, add adversarial check, split for progressive disclosure
- [2026-07-07 18:20] `b55fac6`: fix(docs): sync skill counts after merging main's boyko-knowledge-audit skill
- [2026-07-07 15:26] `9421829`: chore(memory): PR #170 fully CI-green, all 6 fixes confirmed
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
