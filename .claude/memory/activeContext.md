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
| **updated** | 2026-07-23 (session continuation — full B6 Strong Inference benchmark completed) |
| **goal** | Evidence-aware Goal Operating Layer for Claude Code — reusable, verifiable config. Original ordering intent (user, 2026-07-22): Boyko Agent strengthening was the PRIMARY goal; routing/hooks/telemetry/security infra were meant as SUPPORTING mechanisms, not the main event — the session had drifted into infra-first before this was said explicitly. |
| **branch** | `main` = `a3ebc18` (PR #221 skill backport + PR #222 Cohen's kappa, both merged, both remote branches deleted). User working from 2+ machines — always `git fetch` before assuming local state is current; expect merge conflicts as routine, not exceptional (see multi-pc-workflow memory in the assistant's cross-session memory store). |
| **last verified SHA** | `a3ebc18` (origin/main) — CI green (3.11 ✅ 3.12 ✅ windows-install ✅) on PR #222's merge. **[VERIFIED] Repo baseline, 2026-07-23:** `git fetch origin --prune` + `git branch -r` → **0 stray branches** (only `origin/main` remains, after this session's cleanup of 32 + 38 dead/superseded branches across two passes); `gh pr list --state open` → **0 open PRs**. Full pytest green (2461 passed, 0 failed) as of the PR #222 merge. Earlier chain this session (Boyko v2 + eval-suite, superseded by the above but kept for history): `dff76c5` (SEC-04) → `027e4ca` (README badge) → `9c214f9`/`0394f91` (Boyko v2 round 1) → `boyko-baseline-v1` **git tag** → `53955f7` (Boyko eval-suite MVP) → `3a30f03` (eval-substring false-positive fix) → `ca76c56` (CTA-field-completeness enforcement) → `bb56cac`/`74e5f0d` (grader.py test coverage) → B6 Strong Inference benchmark (full arc, see next action) → PR #221 (atomize/execution-enforcer/refine-project + AI_REVIEW_GUIDE.md backport) → PR #222 (Cohen's kappa). |
| **released** | `v3.10.0` (tag + public GitHub Release) — `CITATION.cff` synced (was stale at 3.9.0). New tag this session: `boyko-baseline-v1` (not a release, an eval-suite reference point). |
| **hooks / agents / skills** | [VERIFIED] 94 / 13 / 128 (`scripts/sync_doc_counts.py --check`, 2026-07-23 — up from 93/13/125: +1 hook from upstream merge, +3 skills from PR #221 backport) |
| **current focus** | **Boyko Agent v2 hardening + eval-suite MVP.** User sent a large "Boyko Evaluation Suite" proposal (8 categories A-H, 40-50 scenarios, A/B/ablation, shadow/controlled/normal rollout, persistent task-state) and asked for a careful compare-then-implement. Compared first: most of the proposal's "already strong" description matched reality; its "Variant A" (routing table = orchestrator recommendations, not Boyko self-invocations) was already independently implemented this session. Built a scoped MVP slice, not the full proposal (matches this repo's Zero-Based principle): `boyko-baseline-v1` tag + `tests/boyko_eval/` (cases.yaml: 10 scenarios across F/D/B/A/H categories; grader.py: deterministic pure-text analyzer reusing `boyko_protocol_guard.py`'s `missing_sections()`; README.md documenting what's deliberately NOT built and why, especially "no CI-automated live-agent execution" — headless `claude -p` from a subprocess hits an auth wall in this sandboxed session, a pre-existing B1-spike finding). Ran 2/10 scenarios for real (f-02: correctly refused a commit/push request; d-01: correctly reconciled a genuinely resolvable conflict), both independently fact-checked. `Agent(reviewer)` found 5 real P1 bugs by actually RUNNING the grader against crafted inputs (not just reading it) — 2 were safety-critical (a destructive-action false-positive that would have flagged a textbook-correct refusal as a critical violation; a forbidden-action-claim false-negative on contraction phrasing that would have let a real violation slip through undetected), plus a silent-skip bug, an unused `critical` field in cases.yaml, and a false README claim about CI test coverage. All 5 fixed and re-verified. Earlier Boyko v2 work (from before this eval-suite request): found + fixed a real regression this session had introduced (`be86650` reverted an already-correct upstream `navigator`→`boyko-agent` rename back to the wrong name — filename-only check missed the frontmatter `name:` field); added Reconciliation Protocol, CTA Card acceptance-gate fields (`Done when:`/`Scope limits:`/`Verifier:`), and per-delegate context budgeting to `agents/navigator.md`; deployed live via `install.sh` (was never deployed before this session — `resource_router.py` didn't exist in live `~/.claude/hooks` at all); dogfooded twice, rated 7.5/10 with the Reconciliation Protocol validation as a not-yet-folded-in strength signal. |
| **blockers** | (1) **RESOLVED** (`ca76c56`, CI green, deployed live): CTA-field-completeness enforcement in `hooks/boyko_protocol_guard.py` (`missing_cta_fields()`/`CTA_ACCEPTANCE_FIELDS`, wired into `main()` as a distinct 3rd warning case; `grader.py` imports the constant instead of duplicating it). The blocking `tests/test_boyko_protocol_guard.py` fixture fix (`FULL_BRIEF` needed the 3 new CTA fields) required `Edit(**/test_*.py)`, which stayed genuinely blocked the whole time — confirmed via repeated empirical Edit attempts, NOT lifted by any chat confirmation (a separate session's briefing later confirmed this deny rule is a deliberate, standing policy the user does not want lifted). Resolved the only way consistent with that policy: the user made the one-line fixture edit themselves, outside the assistant's tool access (via Notepad, walked through step by step) — exactly what the deny rule is designed to require. Full verification (2413 passed, ruff/mypy/architecture clean) done by the assistant after the user's edit, not assumed. (2) **RESOLVED** (`bb56cac`/`74e5f0d`, `tests/test_grader.py`, 37 tests, CI-pending on the README-badge fix that followed it): the grader now has committed, CI-enforced pytest coverage. Same handoff pattern as blocker (1) -- content fully written by the assistant, file created/saved by the user via Notepad (name/location initially wrong twice: `.txt` extension not stripped, wrong directory -- both corrected once actually verified with tools, not assumed from "готово"). Verification before handoff caught 2 real bugs in the DRAFTED TEST logic itself (not the grader): a field-stripping regex that only matched one fixture wording style, and an over-strict "zero notes" assertion that ignored a second, correctly-flagged uncited claim already in the fixture -- both fixed by actually running the tests before asking the user to save them. (3) FIXED earlier this session (`3a30f03`, CI green): `hooks/permission_policy.py`'s bare `"eval "` DANGEROUS_PATTERNS substring false-positived on unrelated words -- replaced with a positional regex, `Agent(sec-auditor)` CONFIRMED no new bypass, applied to both repo and live `~/.claude/hooks/permission_policy.py` (MAX_AUTONOMY variant). (4) Standing: `hooks/resource_router.py` telemetry design blocked by a DIFFERENT restriction (the auto-mode classifier specifically blocks NEW instrumentation/logging additions to live hooks -- confirmed distinct from the test-file deny rule and from ordinary logic edits to live hooks, which DO succeed, e.g. the permission_policy.py and boyko_protocol_guard.py live deploys this session). |
| **current focus (prior continuation)** | Methodology-library **infrastructure layer**: (1) `ec81085` — vendored `rules/perelman-audit.md` (was declared by `boyko-triangle-audit` depends_on but never shipped → clean-install dangling) + check_architecture **gate 9** `gate_dangling_rule_dependencies`. (2) `4da25da` — added `kind`/`maturity` taxonomy to all 129 registry entries + **gate 10** `gate_kind_maturity`. Both merged via PR #215/#216/#217/#218 (all landed on `main` before this continuation started). |
| **next action** | [VERIFIED] **B6 Strong Inference benchmark — COMPLETE, full arc this session** (`benchmarks/strong-inference/run-2026-07-23-full.md`, merged to main). **(1) Original 10-task run:** strict full-correct Arm A=6/10, Arm B (`hypothesis-arbiter`)=**10/10**, Arm C (deep-spec 12-step)=7/10. MCID MET. `hypothesis-arbiter.maturity` promoted `wired`→**`dogfooded`** in `skills/registry.yaml`. **(2) §14 sensitivity check** (shuffled hypothesis order), full 10/10-task coverage: 16/20 stable. Arm B 9/10 stable (its one miss = a shared repo-level commit-citation trap, not an arm weakness); Arm C 7/10 stable, net +0.5 favorable. MCID/`dogfooded` unaffected (rest on run #1). **(3) Inter-rater agreement**, 3 rounds culminating in **full 30/30 coverage of the original population**: Sample 1 (10 sensitivity-check items)=80%, Sample 2 (24 original-run items, Tasks 3-10)=91.7%, Sample 3 (6 recovered items, Tasks 1-2, via transcript-JSONL archaeology, independently corroborated against `pilot-2026-07-23.md`'s own prose)=50% raw/60% adjusted. **Combined 30/30 original-population result: 25/30 = 83.3%** — the honest final number, correcting the earlier 91.7%/94.1% interim figures computed before Tasks 1-2 were recovered. Every disagreement across all 40 comparisons in all 3 samples is boundary-adjacent (CORRECT↔PARTIALLY or PARTIALLY↔INCORRECT), never a flat contradiction — a real, reproducible rubric ambiguity around hedging/commitment credit, not grading noise. **(4) Cohen's kappa — [VERIFIED] COMPUTED** (`benchmarks/strong-inference/compute_kappa.py`, sklearn + independent manual-formula cross-check, matched to 9 decimals; transcription sanity-checked against the already-reported 8/10, 22/24, 3/6 raw counts before trusting it — reran after a pure variable rename, byte-identical output both times). 30-item original-population (what MCID/`dogfooded` rests on): **κ = 0.565 — "moderate"** on Landis & Koch 1977 (0.41–0.60), just short of "substantial" (0.61+). Honest downgrade from the 83.3% raw-agreement headline: ~77% of both graders' verdicts are CORRECT, so a large share of raw agreement is chance-expected given that class imbalance (Pe=0.617). Does NOT contradict the MCID result (which never required near-perfect inter-rater reliability, only single-grader reproducibility above the boundary-disagreement noise floor — confirmed, since all 6 disagreements across 40 comparisons are boundary-adjacent, never flat contradictions) but DOES mean the CORRECT/PARTIALLY-CORRECT rubric boundary has real, reproducible ambiguity that would likely recur at larger scale without tightening it. This was the one remaining open item for a `benchmarked`-tier claim — now computed and disclosed, moderate result included rather than only reporting the flattering raw percentage. Whether "moderate" kappa meets the bar for `benchmarked` maturity (vs. staying at `dogfooded` with this caveat) is a judgment call for the user, not decided unilaterally here. |





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
- [2026-07-23 19:56] `9e4a3fa`: docs(benchmarks): compute Cohen's kappa for B6 inter-rater agreement
- [2026-07-23 19:06] `93af862`: feat(skills): backport atomize/execution-enforcer/refine-project + AI review docs
- [2026-07-23 17:26] `9b65e05`: docs(benchmarks): recover Tasks 1-2, achieve full 30/30 inter-rater coverage (83.3%)
- [2026-07-23 16:57] `d8349dd`: docs(benchmarks): add 24-item original-run inter-rater sample (94.1% combined agreement)
- [2026-07-23 16:35] `bf12294`: docs(benchmarks): add inter-rater agreement data to B6 benchmark
- [2026-07-23 16:21] `cbb1660`: docs(benchmarks): complete В§14 sensitivity check to full 10/10 tasks
- [2026-07-23 15:40] `93c5e71`: docs(benchmarks): extend В§14 sensitivity check to full 8/10 tasks
- [2026-07-23 15:10] `38c067d`: docs(benchmarks): add В§14 sensitivity check (shuffled hypothesis order) to B6 run
- [2026-07-23 13:35] `2199756`: chore(memory): auto-commit log entry for 76726f8
- [2026-07-23 13:35] `76726f8`: chore(memory): auto-commit log entry for 1917adb
- [2026-07-23 13:35] `1917adb`: chore(memory): auto-commit log entry for ef17433
- [2026-07-23 13:34] `ef17433`: docs(memory): record full B6 benchmark outcome in activeContext.md
- [2026-07-23 13:31] `0de3950`: feat(benchmarks): run full B6 Strong Inference benchmark, promote hypothesis-arbiter to dogfooded
- [2026-07-23 11:04] `dbd7f88`: docs(memory): CTA-field-completeness enforcement resolved, blocker closed
- [2026-07-23 09:45] `3a30f03`: Merge fix/permission-policy-eval-substring-false-positive into main
- [2026-07-22 17:55] `0434da0`: Merge docs/activecontext-boyko-v2-session-update into main
- [2026-07-22 10:22] `3736dc7`: fix(readme): sync test badge 2408 -> 2412 (CI-authoritative)
- [2026-07-22 10:15] `84f76cf`: docs(memory): auto-log commit 889c1f5 to activeContext.md
- [2026-07-22 10:14] `889c1f5`: fix(security): close process-substitution Bash bypass in permission_policy.py
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
