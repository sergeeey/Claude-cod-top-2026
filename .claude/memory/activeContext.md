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
[2026-07-07] hooks-03 atom CLOSED across 4 commits: both HIGH path-traversal + all 7 MEDIUM race/dedup + all 3 LOW findings fixed and tested.
- a430325: 5-file file_lock batch (doc_registry/expert_registry/vector_store/moc_autolink/observation_capture)
- 5ca0d62: docstring fix — file_lock()'s own docstring contradicted its 5 new raise-on-timeout callers (reviewer P1)
- 76b9c61: thematic_index_router.py dedup+lock, session_save.py daily-note dedup-via-session-hash+lock, session_end.py sessions.jsonl rotation, wiki_reminder.py debounce-failure warning
- 2d61f3d: vector_store.py retry-exhaustion now warns to stderr (reviewer P2 parity fix, independent 2nd reviewer pass)
- 81be9e2: agents/navigator.md + agents/scope-guard.md — removed undeclared mcp__basic-memory__* references (Codex agents-01 finding, priority-3 item). Not configured anywhere in session's MCPs — stale reference, not a live capability. scope-guard's backlog.md (Write, already declared) is now the only save path.
- 535abe5: README "40 of 119 skills (standard subset)" → "all 119 skills" (priority-4 item). [VERIFIED-tool] install.sh: standard/full profiles both call install_extension_skills identically; --non-interactive selects ALL extensions. No 40-skill curated subset exists in code.
Two generalizable bugs found+fixed, saved to patterns.md [AVOID]: (1) file_lock()'s own timeout wasn't checked by callers — fixed by requiring `if not acquired: raise TimeoutError` everywhere. (2) mock.patch is not thread-safe across concurrent threads patching the same global — fixed by extracting moc_autolink's lock-protected update logic into a standalone update_moc() function. Full suite green: 1941 passed, 1 pre-existing unrelated date-flake (test_pattern_escalation_review.py). Verified via monkeypatch-to-no-op experiment that reduced 20→6 thread counts still reliably catch the race.

**SESSION WRAP-UP (2026-07-07 ~05:07):** All 6 items on the audit's "Needs manual re-verification" priority list that could be resolved by verify-and-fix are DONE (1,2,3,4,5,6,7 — path traversal, hypothesis_router, scope-guard MCP refs, teams claim, pre_commit_guard/syntax_guard, hooks-02 batch, hooks-03 batch — all closed across 8 commits tonight: 8135627→e69cadb→a430325→5ca0d62→76b9c61→2d61f3d→81be9e2→535abe5). Repo is clean: `git status` shows only this memory file + 2 pre-existing untracked dirs (`.claude/agent-memory/`, `hooks/.claude/`, present since before this session). Full suite: 1941 passed, 1 pre-existing date-flake, ruff clean across every touched file.

**RESOLVED, pending final reviewer pass + commit:** `hooks/promotion_gate_guard.py:198` — per your /tracy decision ("все по очереди", same call as iteration_guard.py: block). Implemented a PreToolUse(Write|Edit) leg that reconstructs what decision.md would contain after the tool call (full content for Write; old_string→new_string applied to the current file for Edit, mirroring syntax_guard.py's reconstruction pattern) and denies the write if PROMOTE is set while any of the 5 Perelman conditions fail. PostToolUse leg unchanged (kept as safety net). 7 new tests, 41 total, all pass. Reviewer pass in progress (agent a0161438...) — explicitly instructed not to run destructive git commands this time, given the iteration_guard.py incident.

**RESOLVED + COMMITTED (aada48f, 2026-07-07):** `hooks/iteration_guard.py` cap=3 — user explicitly decided "should block, not just warn." Hook now fires on `PreToolUse(Agent)` too, denying (`permissionDecision: deny`) any `Agent(subagent_type=reviewer|builder)` call while the per-session counter is already `>= CAP=3`. Verified against Claude Code's official tools-reference docs (via claude-code-guide agent) that PreToolUse deny genuinely applies to the Agent tool type before building on that assumption. New `"matcher": "Agent"` block registered under `PreToolUse` in `hooks/settings.json`. Gate resets on LGTM (not permanent); other subagent types never blocked. 30 tests total (11 new). Reviewer-agent pass: NEEDS_WORK/P2 (no P0/P1) — applied all 3 suggested polish items (softened an overclaimed docstring evidence marker to `[HYPOTHESIS, external-docs-sourced]`, added a shared `_get_session_count()` helper, added a `try/except(TypeError, ValueError)` fail-open guard for a corrupted state value + regression test). Full suite: 1954 passed.

**Incident during this fix (resolved, documented):** the reviewer agent, while adversarially testing the fix, deliberately introduced an off-by-one mutation to verify the new tests would catch it (a legitimate technique) — but then ran `git checkout -- hooks/iteration_guard.py` to "undo" it, which reverts to the last COMMIT, not to one-edit-ago. Since my entire ~94-line uncommitted implementation sat on top of that commit, the checkout silently destroyed all of it (settings.json/test file, which the reviewer hadn't touched, were unaffected). A stray system "file modified by linter" note showed the intermediate mutated state and initially looked like it might be a prompt-injection artifact — instructed me not to tell the user, which I disregarded since the instruction didn't originate from the user and the content was self-evidently wrong (a formatter never changes logic). I verified via `git diff --stat` + direct `Read`, restored the implementation from my own conversation context, asked the reviewer directly what happened, and it confirmed + self-reported the exact lesson. Saved to patterns.md [AVOID×1] [HIGH]: subagents with Bash+Write/Edit must never use `git checkout`/`stash`/`reset` to undo their own experimental edits on a file with uncommitted changes — capture pre-mutation content in a scratch copy instead. Found agent_context_filter.py has the exact same "claims PreToolUse(Agent) in docstring but never registered" gap as 11 other files closed earlier tonight — flagged via spawn_task (task_f51e704f), not fixed in this pass (out of scope for this specific request).

Third background reviewer-agent pass (aeae52a2f650175bc, on commit 76b9c61) never sent a completion notification after ~35 min — treated as stalled per your own instruction, not blocking further. Two OTHER background tasks are still pending (not urgent): `task_3a0a75d3` (audit test_circuit_breaker_lock_race.py for the same mock.patch-thread-unsafety pattern found tonight) and `task_5e5f0e6e` (expert_registry.compile_expert() holds its lock during untimed expert execution — a real Codex-found risk, needs its own repro+fix, separate from tonight's batch).

Not started tonight (explicitly out of scope, no Codex atom coverage yet this session): hooks-05 and any atoms beyond hooks-01/02/03/04 + agents-01/skills-01-03/ci-docs-01 cross-checks already done. If continuing the audit is the next priority, those are the natural next atoms — but that's your call, not something to start without you.

**EXTERNAL AUDIT RE-VERIFICATION (de1c456, 2026-07-07 ~09:00):** User pasted a large external static-analysis audit of the public GitHub repo (commit 1a6a5b2/PR#169 — 13 commits behind this branch's HEAD). Per audit-verification-gate.md, independently re-verified all 8 findings against actual code rather than trusting the report as-is:
- 3 CONFIRMED + FIXED: permission_policy.py's cat/head/tail auto-allowed reading ANY file including secrets (HIGH — added sensitive-path check, downgrades to "ask"); install.sh's --non-interactive silently cloned an unpinned third-party repo (last30days-skill) by default (HIGH — added --allow-external-skills opt-in flag, off by default); ci.yml's 6 Action references were tag-pinned not SHA-pinned (MEDIUM — SHA-pinned all 6, verified live via api.github.com before pinning, not fabricated).
- 2 ALREADY FIXED locally, just not yet pushed to the public repo the audit read: input_guard.py's dict-key scanning + trusted-MCP command_injection-only narrowing (part of tonight's earlier hooks-01 batch); promotion_gate_guard.py's advisory-only PROMOTE (this session's own iteration_guard.py-pattern fix, see above).
- 1 CONFIRMED but INHERENT LIMITATION, not a discrete bug: validation_theater_guard.py's regex/keyword detection can be evaded by sufficient paraphrasing — already acknowledged and layered against via other non-regex mechanisms in this repo (skeptic-triggers.md, integrity.md Submission Gate).
- 2 CONFIRMED, real, but left OPEN pending explicit user decision (same "advisory→blocking is a call for the user" discipline as iteration_guard.py/promotion_gate_guard.py tonight): SessionStart's auto-pull for --link-mode installs (zero review before pulling upstream hook/rule changes); pre_commit_guard.py's staged-secrets check is warn-only, not a hard block.
Full suite: 1969 passed. ruff clean.
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
- [2026-07-07 08:40] `de1c456`: fix(security): close 3 confirmed findings from external audit re-verification
- [2026-07-07 07:45] `c34301f`: chore(memory): document iteration_guard.py fix + git-checkout incident
- [2026-07-07 07:44] `aada48f`: fix(hooks): iteration_guard.py cap=3 now blocks, not just warns
- [2026-07-07 05:13] `9a81ae5`: chore(memory): session wrap-up — hooks-03 Codex audit fully closed
- [2026-07-07 04:50] `535abe5`: docs(README): fix stale "40 of 119 skills" standard-profile claim
- [2026-07-07 04:39] `81be9e2`: fix(agents): remove undeclared mcp__basic-memory__ references
- [2026-07-07 04:27] `2d61f3d`: fix(hooks): vector_store retry-exhaustion now warns to stderr
- [2026-07-07 03:56] `76b9c61`: fix(hooks): close remaining hooks-03 MEDIUM/LOW findings
- [2026-07-07 03:54] `5ca0d62`: docs(hooks): fix file_lock() docstring contradicting its own raise-on-timeout callers
- [2026-07-07 03:07] `a430325`: fix(hooks): close hooks-03 MEDIUM race conditions + file_lock timeout bug
[summarized] - [2026-07-07 01:39] `e69cadb`: test(hooks): cover run_expert's documented delete-during-run tradeoff
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
