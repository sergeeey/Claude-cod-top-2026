# activeContext.md — Claude-cod-top-2026

## Scope Fence
- **Goal:** production-ready Claude Code config для переиспользования в любых проектах
- **Boundary:** только hooks/ agents/ skills/ rules/ — не трогать внешние проекты
- **Done when:** install.sh работает на trёх машинах, CI зелёный, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, публикация в marketplace


## Recent findings
- 2026-07-12: пользователь попросил зеркалировать Impact Score поле (добавленное
  в global Pearl Registry) в repo pearl_registry тоже. Проверка вскрыла: repo's
  `rules/falsification-ladder.md` вообще НЕ содержал Pearl Registry секции —
  но `hooks/research_health_loop.py` УЖЕ парсит `pearl_registry/INDEX.md`
  (decay/staleness check на next_check) — shipped код без shipped спеки за ним,
  реальный пре-существующий gap, не только "не смёржено сегодня". Добавил
  тримнутую project-agnostic секцию в rules/falsification-ladder.md с
  impact_score с самого начала. По ходу нашёл РЕАЛЬНЫЙ баг в hook'е ДО
  коммита: `_parse_pearl_registry` читал next_check/status по ФИКСИРОВАННОЙ
  ПОЗИЦИИ (cols[5]/cols[6]) — вставка impact_score между
  falsifiable_prediction и trigger_condition (естественное место) сдвинула бы
  ВСЕ поля после неё, тихо подменив next_check на старое значение
  trigger_condition. Исправлено: парсинг по имени заголовка через
  header_index map вместо позиции — переживёт любую будущую перестановку
  колонок, не только эту. Добавлен regression-тест с impact_score в
  середине таблицы. 27/27 в файле, 2070/2070 по репо, ruff+mypy clean.
  Коммит `8d3dfd9`, ветка `feat/pearl-registry-impact-score`, не запушена —
  ждёт "го, пуш".
- 2026-07-11: новый глобальный скилл `~/.claude/skills/boyko-why-ladder/` — пользователь
  показал реальную рекурсивную лестницу объяснений (коэффициенты→базис→симметрия→октонионы,
  "почему X? → нашли Y → почему Y?"), спросил есть ли инструмент. Не было — ближайшие
  (`boyko-triangle-audit` Vertex 4, `hypothesis-arbiter`) одноразовые, не рекурсивные.
  Спроектирован скилл: на каждой ступени DERIVED/FITTED/UNKNOWN (переиспользует Vertex 4,
  не дублирует), находит САМОЕ СЛАБОЕ звено, в конце — обязательная классификация по дилемме
  Агриппы (FOUNDATIONAL_STOP/CIRCULAR/ONGOING_REGRESS), Depth Guard переиспользует порог
  Counterfactual Frame (≥3 нерешённых ступени). ПРОВЕРЕНО реальным тестом: независимый агент
  (без памяти сессии) прогнал 2 синтетических кейса — скилл поймал циркулярность в ОБОИХ,
  включая тот, что я сам сконструировал как "должен легитимно завершиться" (Гурвиц реален
  и процитирован верно, но не спасает циркулярную Ступень 4 — ровно тест, который скилл
  обязан проходить). Найдено 2 реальных бага в v1.0.0 (не в логике, в форме входа): (1)
  неоднозначность когда одна сущность переспрашивается дважды под видом двух ступеней,
  (2) шаг null_results/parked не имел условия пропуска для артефакта без папки эксперимента.
  Оба исправлены в v1.0.1. Оценка после теста: 8/10. Зеркалирован в репо —
  `skills/extensions/boyko-why-ladder/` — на ТОЙ ЖЕ ветке `feat/boyko-triangle-audit-skill`
  (не новая ветка), т.к. зависит от `boyko-triangle-audit`, который ещё не смёржен (PR #180
  открыт). registry.yaml depends_on: boyko-triangle-audit, hypothesis-arbiter,
  falsification-ladder(rule). Счётчики синхронизированы 122→123 skills / 110→111 extensions.
  2069/2069 тестов, ruff clean. Коммичу и пушу в тот же PR #180 сейчас.
- 2026-07-11: новый глобальный скилл `~/.claude/skills/boyko-triangle-audit/` —
  пользователь предложил универсальную схему для серьёзной research-работы
  (Теория↔Вычисления↔Независимая проверка→Объяснение, 4 вершины), спросил
  сравнить с существующим стеком. Найден конкретный gap: `promotion_gate_guard.py`
  уже механически гейтит 2 из 4 вершин (Вычисления через controls, Проверка
  через no-collapse+external-reconstruction), но НЕ проверяет содержательность
  Теории/Объяснения — только формальное наличие поля Rationale в decision.md.
  Создан скилл (не хук — нужна LLM-оценка "это реальный механизм или пересказ
  результата", не regex): present-strong/present-weak/missing на каждую вершину,
  обязательная evidence-цитата, ловит FITTED-vs-DERIVED путаницу и числовое
  совпадение без degeneracy-проверки. Зеркалирован в репо —
  `skills/extensions/boyko-triangle-audit/` (`59f41f9`, ветка
  `feat/boyko-triangle-audit-skill`, не запушена). depends_on:
  falsification-ladder(rule), perelman-audit(rule) в registry.yaml. Счётчики
  синхронизированы 121→122 skills / 109→110 extensions (README/plugin.json×2/
  marketplace.json). Попутно исправлен category-дрейф ДО коммита (plugin.json
  "analysis" vs registry.yaml "research") — тот же баг уже был известен и не
  исправлен на boyko-specialist. 2069/2069 тестов, ruff clean, YAML валиден.
  Ждёт push + PR + "го, мёрж".
[summarized] - 2026-07-08: `boyko-knowledge-audit` frontmatter/registry.yaml/plugin.json описывали
  верно но контекст неполный (не учёл `promotion_gate_guard.py`, который
  реально блокирует), F-05 подтверждён (install.sh silent `cp` failures —
  не тронут, отдельная задача), F-02 частично реален другим механизмом:
  голый `[VERIFIED-REAL]` тег рядом с synthetic-маркером в ОДНОМ выводе
  раньше отключал блок в `should_block_validation()`. Fixed `000f383`
  (ветка `fix/validation-theater-verified-real-spoofing`, не запушена) —
  узко для structured-тега, не всего REAL_DATA_MARKERS (первая версия фикса
  сломала легитимный URL+dataset тест, сужена после падения теста). 2 новых
  regression-теста, 19/19 в файле, 2043/2044 по репо (1 unrelated date-flake
  в pattern_escalation_review — UTC vs local timezone, зафлагован отдельной
  задачей task_89911930, не этой сессией). PR #175 смёржен (badge пришлось
  синкать дважды — coverage % плавал 79/80 между CI-прогонами, зафлагован
  отдельной задачей task_5427630c).
- 2026-07-10: `boyko-specialist` (глобальный скилл, созданный ранее в сессии)
  зеркалирован в этот репо — `skills/extensions/boyko-specialist/` (SKILL.md +
  plugin.json), по образцу `boyko-knowledge-audit`/`boyko-method`. Синхронизированы
  счётчики скиллов (121 всего, 109 extensions) в marketplace.json/plugin.json/
  README.md (3 места) — заодно поправил несвязанный дрейф: marketplace.json
  говорил "84 hooks", реально 85 (совпадает с plugin.json). Коммит `f9baf92`,
  ветка `feat/boyko-specialist-skill`, не запушена.
- 2026-07-10: PR #178 (`fix/dispatcher-evidence-first-safety-floor`) переработан
  `dispatcher/SKILL.md` (`c17e4bf`) под внешний adversarial review — evidence-first
  framing, Safety Floor, разорван dispatcher↔routing-policy цикл, allowed-tools сужен.
  Второй "second opinion" review нашёл P1: Safety Floor жил ТОЛЬКО в тексте
  dispatcher, а routing-policy вызывает dispatcher лишь при confidence LOW/ambiguous —
  на частом HIGH-confidence пути (сама эта сессия имела margin=4/HIGH) routing-policy
  шёл по СВОЕЙ Stage-0 таблице ("MVP → tests optional") без единой ссылки на floor.
  Перепроверил напрямую (Read routing-policy/SKILL.md строки 40-60) — подтвердилось
  [VERIFIED-REAL], не натяжка. Фикс (`52c7ce7`): добавлен `## Absolute Safety Floor`
  сразу после Stage 0 в routing-policy/SKILL.md (+ зеркало в global) — применяется
  на КАЖДОМ пути независимо от confidence/вызова dispatcher. Минимальный, не
  архитектурный: routing-policy остался владельцем task routing. 104/104 (structure+
  routing tests) + ruff clean. PR #178 смёржен (`1cf5a44`), ветка удалена.
- 2026-07-11: из ретро-урока по PR #178 (тот же класс дефекта: правило есть в
  тексте, механизм не срабатывает) — спроектирован и реализован
  `hooks/submission_gate_guard.py` (`fcc58f7`, ветка
  `feat/submission-gate-guard-hook`, не запушена). Операционализирует уже
  написанный integrity.md Submission Gate (patterns.md 2026-07-11 [AVOID×4]:
  препринт ушёл на внешнее ревью без срабатывания гейта — текст был, механизма
  не было). UserPromptSubmit (verb+noun co-occurrence) + PostToolUse(Write|Edit)
  (manuscript-shaped file path). Self-audit нашёл реальный баг ДО коммита:
  наивный substring-match ложно сработал бы на "already"⊃"ready",
  "incomplete"⊃"complete", "newspaper"⊃"paper" — исправлено на `\b`
  word-boundary regex, 3 regression-теста добавлены. Второй найденный и
  исправленный баг: сам Submission Gate текст существовал только в ЭТОМ репо
  локальном `.claude/rules/integrity.md`, не в shipped `rules/integrity.md` —
  хук ссылался бы на секцию, которой нет в свежей установке (тот же класс
  бага, который хук должен закрывать!). Портировал урезанную project-agnostic
  версию в shipped rules/integrity.md. Синхронизирован счётчик хуков 85→86
  (README/architecture.md/plugin.json×2/marketplace.json). 2069/2069 тестов,
  ruff+mypy clean. Осознанно НЕ покрыто: routing-bypass класс (dispatcher↔
  routing-policy) — структурно специфичен графу skills, не generic
  prompt/file паттерну (Structure-Bias Guard). Ждёт push + PR + "го, мёрж".

## Session 2026-06-28 Final State
PR #138 P0-P2 audit ✅ | PR #140 inbox dedup hooks 86→85 ✅ | PR #141 tests 3 hooks ✅ MERGED CI green
P3 triggers: 314/344 SKILL.md ✅ | README badge 1652/75% ✅ | hook count synced all docs ✅
AUDIT DEBT = ZERO. Open PRs = 0. CI = green (3.11+3.12+windows). Obsidian updated.






## Current Focus
**PR #171 MERGED (2026-07-12, branch `improve/boyko-knowledge-audit-skill`, commit `de27b21`):** boyko-knowledge-audit v3.1.1 — fixed fake-precision rigor_score (added `[HEURISTIC]` marker), near-tautological `classification_appropriateness_rate` (added Step 5.7 Adversarial Downgrade Check for Level 3+ claims), no cross-reference to project's epistemics stack, 638-line monolithic SKILL.md (split to `references/`), no evals (added `evals/evals.json`). Conflicted with main's independent `2700cd2` (8→9-level self-consistency fix) — resolved by keeping PR171's superset content and correcting its 2 stale "8-уровневая" strings to "9-уровневая [3-P/3-M]" to match its own already-updated body.
[summarized] **RETROSPECTIVE + PROCESS TOOLING (2026-07-07 ~20:00, branch `chore/pre-commit-checklist-and-readme-gate`):** User asked...
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
- [2026-07-12] PR #171 merged: boyko-knowledge-audit v3.1.1 (fake-rigor fix, Step 5.7, references/ split, evals) -- resolved conflict with main's independent 3-P/3-M self-consistency fix
- [2026-07-12 15:24] `8d3dfd9`: feat(rules): add Pearl Registry section (with impact_score) to shipped falsification-ladder.md
- [2026-07-11 14:18] `3d53df6`: chore(memory): document boyko-triangle-audit skill work
- [2026-07-11 14:18] `59f41f9`: feat(skills): add boyko-triangle-audit skill + sync repo skill counts
- [2026-07-11 10:35] `c65ae0d`: fix(ci): sync README Tests/Coverage badge to CI-authoritative count (2053/80%)
- [2026-07-11 10:25] `fcc58f7`: feat(hooks): submission_gate_guard.py -- mechanically enforce integrity.md's Submission Gate
- [2026-07-10 19:51] `52c7ce7`: fix(skills): close the routing-policy HIGH-confidence Safety Floor gap
[summarized] - [2026-07-10 19:28] `c17e4bf`: fix(skills): dispatcher -- evidence-first routing, safety floor, break routing-policy cy...
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
