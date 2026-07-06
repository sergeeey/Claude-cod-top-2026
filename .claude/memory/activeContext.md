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
2026-07-07 (in progress): hooks-03 atom, partial — 2 of 2 HIGH path-traversal fixed (pre_vault_write.py: relative_to() didn't resolve() first, so "projects/../_auto/foo.md" kept its literal ".." and bypassed the _auto/ read-only guard; expert_registry.py: entry["name"] used directly as filename with zero validation, a name shaped like an absolute path could hijack the write location ANYWHERE on disk since pathlib's `/` replaces the base when the RHS is absolute — added strict slug regex + resolve/relative_to defense-in-depth). 2 of 7 MEDIUM race-condition findings fixed (doc_registry.py, expert_registry.py — same file_lock() pattern as mcp_circuit_breaker.py earlier). Found a NEW real bug via my own concurrency test (not Codex-reported): even with file_lock() around the write path, an unlocked early _load() in a different thread could collide with another thread's locked os.replace(), producing a genuine reproducible Windows PermissionError — fixed at the root by moving compile_expert/run_expert's early reads inside the lock too, PLUS added retry-on-PermissionError to _save() in both files as defense-in-depth for read-only callers (lookup/list_all) that intentionally stay unlocked. 1929 tests passed (1 unrelated pre-flagged flake).
STILL TODO in hooks-03: vector_store.py, session_save.py (x2: daily-note dup + index.md race), moc_autolink.py, observation_capture.py (5 more MEDIUM race conditions, same file_lock() pattern), thematic_index_router.py (MEDIUM dup-entry, different fix), 4 LOW findings (wiki_reminder.py debounce-swallow, session_end.py sessions.jsonl unbounded growth, moc_autolink.py failed-write-swallowed, session_save.py index.md-regen-swallowed).
2026-07-07: hooks-02 batch done (7 HIGH, 9 MEDIUM, 6 LOW + 5 self-discovered issues) — pre_commit_guard (shlex-tokenized git commit/push detection replacing substring checks, cwd propagated to all checks not just branch check, silent-ruff-skip now warns, branch-name substring false-positive fixed), commit_test_gate (failed pytest no longer stamps success, echo/heredoc pytest-mention no longer counted as real run, MultiEdit stamped), weakened_test_guard (Write-replace-whole-file now detected via PreToolUse stash, MultiEdit detected, unittest self.assertX() counted, skipif detected), syntax_guard (JS validation switched from executing `--input-type=module` to parse-only `--check`, Python Edit now reconstructs full file instead of fragment-only, Write's field-name bug fixed — was reading "new_content" which never appears in a real event, so Write validation had silently never worked), checkpoint_guard (moved PostToolUse→PreToolUse so warning appears before not after the risky op, PowerShell Remove-Item + git switch detection added, no-checkpoints-dir case now warns instead of silence), task_audit/instructions_audit (OSError now warns to stderr instead of vanishing silently). Self-discovered: commit_test_gate/iteration_guard/weakened_test_guard were completely UNREGISTERED in settings.json (dead hooks, now registered); "Edit|Write" matcher confirmed via WebSearch to be an unanchored regex matching MultiEdit/NotebookEdit too. Verified with reviewer-agent pass (zero P0/P1, one P2 found — pre_commit_guard heredoc false-positive — found and fixed). Codex cross-model pass unavailable both retries (rate-limited, resets ~1:57 AM) — proceeded on reviewer-only verification per the Codex-unavailable fallback, marked [SKIPPED-NO-CODEX] in docs/CODEX_AUDIT_RESULTS.md. 1915 tests passed (1 unrelated pre-flagged date-flake in pattern_escalation_review, spawned as separate task).
NOT YET DONE: hooks-03 atom (untouched), iteration_guard.py:79 cap-not-enforced (registered but enforcement gap needs a design decision), iteration_guard.py:58 missing-VERDICT-line, read_before_edit.py:33 Write-not-warned, concurrent-SubagentStop-counter race.
2026-07-06 (135a071): Atomized Codex audit (docs/CODEX_AUDIT_SPEC.md, 16 atoms) found ~34 HIGH findings across hooks/agents/skills/tests. Fixed all 14 hooks-04 (FL/EstimandOps gate layer: claim_entropy_tracker, promotion_gate_guard, reject_gate_guard, hypothesis_router — 8/15 files were never registered in settings.json, now all registered) + hooks-01 (security: permission_policy redirect bypass, input_guard trusted-MCP full-bypass narrowed, security_verify Bash-redirect blind spot, mcp_circuit_breaker race condition closed via new file_lock() in utils.py). Verified with reviewer-agent + independent Codex cross-model pass before commit — caught a real security_verify.py gap (tee/dd of=/quoted-paths) my own fix had missed, plus a self-inflicted Windows PermissionError regression in file_lock()'s stale-lock reaping (tight retry loop under contention) — both fixed and verified flake-free (5x + 3x repeated runs). 2 Codex false positives caught by direct verification (agents/teams/ "doesn't exist" claim — false, exists with 3 files; reported independently by 2 atoms, the audit's key meta-lesson). 1846 tests passed, 0 failures. See docs/CODEX_AUDIT_RESULTS.md for full per-finding status.
NOT YET DONE: hooks-02/hooks-03 atoms (untouched), pre_commit_guard.py git-C bypass, syntax_guard.py JS-execution gap (both hooks-02 scope), promotion_gate_guard.py:198 PROMOTE-persists-despite-failed-conditions (needs explicit PostToolUse→PreToolUse architecture decision, deliberately not silently implemented), mcp_circuit_breaker.py HALF_OPEN permanent-wedge-on-crash (pre-existing, logged not fixed).
[summarized] 2026-07-06: PR #168 merged — fixed 2 fake_run_git mocks missing `cwd` kwarg (was breaking main CI) + README badge sync. ...
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
- [2026-07-07 00:53] `2d27117`: fix(hooks): close Codex-audit HIGH/MEDIUM/LOW findings in hooks-02
- [2026-07-07 00:36] `135a071`: fix(hooks): close Codex-audit HIGH/MEDIUM findings in hooks-04 + hooks-01
- [2026-07-07 00:35] `135a071`: fix(hooks): close Codex-audit HIGH/MEDIUM findings in hooks-04 + hooks-01
- [2026-07-06 23:33] `135a071`: fix(hooks): close Codex-audit HIGH/MEDIUM findings in hooks-04 + hooks-01
[summarized] - [2026-07-06 20:25] `cd22ac1`: docs: sync README test count 1717 → 1730 (CI-authoritative)
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
