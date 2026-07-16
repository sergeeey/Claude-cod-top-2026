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
| **updated** | 2026-07-16 |
| **goal** | Evidence-aware Goal Operating Layer for Claude Code — reusable, verifiable config |
| **branch** | main |
| **last verified SHA** | `71070f6` (CI green) |
| **released** | `v3.10.0` (tag + public GitHub Release) |
| **hooks / agents / skills** | 89 / 15 / 123 |
| **current focus** | RFC-003 severity classifier deployed in shadow (OFF by default); routing safety-floor now code-enforced (routing_floor_classifier); memory architecture being tidied |
| **blockers** | none critical. Guard FP still unsolved-by-design (shadow collecting data). |
| **next action** | RFC-003 step 6 needs a multi-session real shadow sample before step 7 |

## Recent findings

- 2026-07-16 **SESSION SUMMARY — big multi-phase session. main → `f42c151`, released
  `v3.10.0` (tag pushed; GitHub Release page still needs a manual "Draft from tag").**
  Repo repositioned from "Trust Layer" to **"Evidence-aware Goal Operating Layer for
  Claude Code"** (owner-approved). Everything below verified & pushed; CI green across the
  chain. ~20 merges. `~/.claude` re-synced twice (additive via `scripts/sync_config.py
  --no-pull`), all sync backups cleaned after verifying settings.json valid.

  **The 5-sprint plan (all done):**
  - S1 metadata/lifecycle/deps consistency (4 defects; `[VALIDATED:]`→`[REVIEWED:]`, 60-day
    staleness now CI-enforced, 39 stale skills→review; hook-count gate hardened for all 3
    metadata files + adjective-evading counts; phantom experiment citations fixed).
  - S2 registry capability/pack v3-lite on 15 skills + **PyYAML pinned as dev/CI dep**
    (un-skipped the yaml gates that passed vacuously); skeptic-triggers reframed as
    signals-not-verdicts. Guard FP/FN baseline recorded.
  - S3 self-dev loop: `/release-scout` (propose-only, FL pre-gates) + `research-sources.yaml`
    + durable schedule setup scripts (dry-run default). Dry-run validated live; surfaced a
    real candidate (`updatedToolOutput`).
  - S4 RFC-001 claim pipeline (Claimify stages + 5-route type routing) + bilingual corpus.
    Decisions D1-D3 recorded (front-stage inside claim-decomposer; NORMATIVE=terminal flag;
    route on 5 not 8).
  - S5 `PRODUCT_CONSTITUTION.md` (Core Loop + Contribution Gate) + pack taxonomy.

  **Owner decisions executed:** rename ✅, release 3.10.0 ✅, release-scout schedule ✅,
  build guard classifier → became RFC-003.

  **RFC-003 (response-guard severity calibration) — the deep thread, steps 0-6 done:**
  the guard over-warns on benign security prose AND under-detects real injections. TWO
  approaches were REJECTED before shipping (the repo's own value proven on itself):
  - regex-composition (`null_results/20260716-regex-composition-response-guard`): 0/0 on
    calibration, 6/8 on held-out — overfit, doesn't generalize.
  - LLM-judge suppression (`null_results/20260716-llm-judge-response-guard`): sec-auditor
    red-team found it structurally unsound (weak injectable model gating the only control).
  The SURVIVING design = deterministic **severity calibration in shadow mode**
  (`hooks/severity_calibrator.py`, RFC-003): never suppresses, only calibrates volume;
  downgrade needs (descriptive context) AND (no strong directive). Red-teamed (step 4):
  6 real bypasses found+fixed (worst: homoglyph `ignоre` in a fence downgraded a canonical
  injection — root cause: detector ran on raw text while scan() normalizes; fixed by
  reusing `_normalize`). Wired into web/mcp_response_guard **shadow mode, OFF by default**
  (env `CLAUDE_GUARD_SHADOW`), zero displayed-behavior change, fully wrapped.
  **Step-6 real-data probe (n=4):** safety holds+improves (an under-rated exfil was
  upgraded to HIGH), but FP reduction is WEAKER than the corpus implied (real security prose
  → REQUIRES_CHECK, not INFO — descriptive regex is real-phrasing-limited). Shadow data
  corrected the corpus's headline number before any user-facing change. **Step 7 (enable
  displayed changes) waits for a real multi-session shadow sample — not shipped.**

  **Method wins to remember:** held-out testing killed an overfit fix on static data;
  red-team killed an unsound design before code; shadow mode corrected corpus-optimism on
  real traffic. Three different "measure before you trust" gates, each caught a different lie.

- 2026-07-16: **Sprint 1 (metadata + consistency) — 4 defects closed, 2 external-audit
  premises corrected.** Two external audit docs drove this; both were partly wrong and
  verifying beat trusting.
  - **1.1 hook drift**: audit said "86 vs 88" — actual was 87 vs 88, in
    `.claude-plugin/marketplace.json`. Root cause was TWO defects, not one: CI's
    check_meta loop enumerated 2 of 3 metadata files (there are two marketplace.json —
    root + .claude-plugin/, only root was gated), AND "87 deterministic hooks" evades a
    plain `[0-9]+ hooks` pattern — the count escaped **by adjective**. Fixed both;
    verified the gate against the defect (old pattern matches nothing = silent pass).
  - **1.2 phantom evidence**: `docs/positioning.md` cited 2 experiment dirs that were
    NEVER committed — real runs done in the parallel `repo-clean-test` clone, only
    conclusions backported. Imported both artifacts; the cited SHA `1d787bb` is
    local-only to that clone — the work landed here as `3462c2b` (re-verified via
    `install.sh:408 install_commands()`, not by trusting the artifact). ALSO found a
    real overclaim: "each with a context-blind red-team pass" — only 1 of 2 had one.
  - **1.3 premise FALSIFIED**: audit attacked `[VALIDATED: date]` as an unsubstantiated
    evidence claim. Wrong — per `docs/anti-patterns.md` it means "last lifecycle review",
    a staleness marker. But a bigger real defect was underneath: the documented 60-day
    rule was **never enforced** — 39 of 47 files claimed `[STATUS: confirmed]` while
    60–126d stale. Renamed `[VALIDATED:]`→`[REVIEWED:]` (the name collided with
    integrity.md's evidence vocabulary — proof the collision is real: it misled a careful
    auditor), flipped 39 stale→review, added enforcing tests.
  - **1.4 one-way edges**: registry had 10 real depends_on edges, all recorded only
    downstream. 9 upstream skills missing 14 backlinks (e.g. sci-hypothesis had no idea
    hypothesis-arbiter consumes it). Added backlinks + test.
  - Every new test was **adversarially verified to fail** on the defect it guards, not
    just to pass on fixed data.
  - **KNOWN HOLE**: TestDependencyBacklinks needs PyYAML → skips silently in CI
    (requirements.txt pins only pytest/cov/ruff/mypy). Local-only gate. Same class as
    the Substrate Gate's "registered but not enforced". Documented in the test docstring.
  - 2159 local / predicted 2156 CI (4 of 5 new tests count; the yaml one skips).
    README synced to 2156 — reasoned from CI's last VERIFIED number (2152), not local.
    CONFIRMED green on CI @ a4f4eb3 — the 2156 prediction held (README verify-metrics
    step re-measures on the runner and would have failed otherwise).
  - **DECISION (Tracy + ZBT, 2026-07-16): `scripts/sync_counts.py` NOT built.** Plan
    asked for an auto-fix script; its premise ("no single source → need sync") was
    obsoleted by the root-cause finding (2 gate holes, both now closed → drift is
    detected + fails build). Auto-fix rejected: 95% of value is detection; an
    auto-reconciler would hide an accidental hook deletion (88→87 silently) against
    the repo's "verify, don't auto-trust" thesis. Revival trigger: 3+ future drift
    incidents. Recorded in plan file.
  - **Sprint 5 baseline (plugin-eval Layer 1 over 111 extension skills, 2026-07-16):**
    BSV block 28% (32/111), Related-Skills section 36% (41/111), triggers: in-file 10%
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
[summarized] [summarized] - 2026-07-12: **[AVOID×3]** PR #185 (Phase 3) — тот же класс CI-фейла третий раз за сессию
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
[summarized] [summarized] **PR #171 MERGED (2026-07-12, branch `improve/boyko-knowledge-audit-skill`, commit `de27b21`):** boyko-know...
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









































































































## Auto-commit log
- [2026-07-16 14:52] `f66de21`: release: 3.10.0 вЂ” Evidence-aware Goal Operating Layer (repositioning release)
- [2026-07-16 14:44] `072a7f2`: Merge docs/rfc-002-guard-classifier-rejected: LLM-judge design rejected by red-team
- [2026-07-16 14:37] `b33e3da`: Merge feat/release-scout-durable-schedule: durable OS-level weekly schedule
- [2026-07-16 14:32] `6d4d7a6`: Merge feat/repositioning-goal-operating-layer: Evidence-aware Goal Operating Layer identity
- [2026-07-16 14:23] `62001ed`: Merge docs/rfc-001-resolve-open-questions: D1-D3 folded into RFC-001
- [2026-07-16 13:39] `d2e1ec0`: feat(product): PRODUCT_CONSTITUTION v1 + pack taxonomy anchor (identity change NOT applied)
- [2026-07-16 13:36] `33de3de`: Merge feat/sprint4-claim-pipeline-rfc-corpus: claim pipeline RFC + benchmark corpus
- [2026-07-16 13:31] `3dea644`: Merge feat/sprint3-release-scout-self-dev-loop: propose-only self-dev scout
- [2026-07-16 13:25] `54ff536`: Merge docs/sprint2.3-skeptic-trigger-calibration: triggers are signals not verdicts
- [2026-07-16 13:21] `5cbf539`: docs(guard): REJECT regex-composition guard fix вЂ” falsified by held-out testing
- [2026-07-16 13:12] `d1c8b87`: feat(registry): capability v3-lite on 15 core skills + close the yaml-gate CI hole
- [2026-07-16 12:59] `2c221b1`: test(guard): record FP/FN baseline for the injection guard against a labelled corpus
- [2026-07-16 12:35] `cbf7dce`: fix(tests): match the retired tag's shape, not every mention of its name
- [2026-07-16 12:31] `96a106a`: fix(consistency): close Sprint 1 вЂ” phantom evidence, unenforced lifecycle, one-way deps
- [2026-07-16 12:04] `706fce0`: fix(metadata): close the two gaps that let hook count drift to 87 vs 88
- [2026-07-13 20:19] `94363ca`: fix(docs): sync README/plugin.json/marketplace.json to 87 hooks / 2114 tests
[summarized] - [2026-07-13 20:01] `d3c357c`: fix(security): P0.2/P0.3/P0.4 hook registry accuracy + coverage gate
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
