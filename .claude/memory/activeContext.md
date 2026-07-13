# activeContext.md — Claude-cod-top-2026

## Scope Fence
- **Goal:** production-ready Claude Code config для переиспользования в любых проектах
- **Boundary:** только hooks/ agents/ skills/ rules/ — не трогать внешние проекты
- **Done when:** install.sh работает на trёх машинах, CI зелёный, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, публикация в marketplace




## Recent findings
[summarized] - 2026-07-12: **[AVOID×3]** PR #185 (Phase 3) — тот же класс CI-фейла третий раз за сессию
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
- 2026-07-12: Phase 4 (F-06/F-07/F-13, ветка `fix/phase4-data-exposure`) — все три
  свелись к точечным фиксам после верификации audit-текста против реального кода
  (не слепое следование формулировке аудита, см. audit-verification-gate.md).
  F-13 (redact.py не подключён к PostToolUse(Bash)): аудит назвал 6 хуков, но
  проверка показала — только `auto_capture.py` реально ПЕРСИСТИТ сырой
  stdout/stderr в файл (`~/.claude/memory/_auto/raw/*.md`); остальные 5
  (`memory_guard`, `commit_test_gate`, `post_commit_memory`, `pattern_extractor`,
  `learning_tracker`) используют tool_response только для boolean-проверок,
  ничего не пишут наружу — сузил scope до 1 файла осознанно, не по 6. Подключил
  уже существующий `hooks/utils.py:redact_secrets()` (не `scripts/redact.py` —
  тот KZ-специфичный и живёт вне hooks/, redact_secrets шире и уже используется
  в `knowledge_librarian.py`). F-06 (нет fencing вокруг injected memory/wiki):
  добавлен `fence_untrusted_content()` в utils.py — оборачивает injected текст в
  `<untrusted-context>` с явным "не инструкция" preamble; подключён в
  `prompt_wiki_inject.py` и `agent_lifecycle.py`. F-07 (env_reload.py пишет
  сырые секреты без редакции) — **аудит был неточен**: проверил, кто читает
  `$CLAUDE_ENV_FILE` — потребителя внутри репо НЕТ, это внешняя shell-обёртка
  пользователя (source'ит файл в интерактивный shell). Редактировать значения
  = сломать саму фичу (задача reload — прокинуть РЕАЛЬНЫЕ креды). Реальная
  экспозиция — default file permissions (world/group-readable при создании),
  не содержимое. Fix: `secure_append_env_file()` — chmod 0600 после каждой
  записи (no-op на Windows, best-effort). **Skeptic Response Matrix (FL Step
  8a): Dismissed с обоснованием**, не слепой Fix — задокументировано здесь как
  ADR. 16 новых тестов, ruff+full suite clean (2097 passed / 13 skipped).
  **PR #186 merged (efd10cc).** Обнаружен реальный CI-фейл при верификации: README
  Tests-бейдж 2078 vs CI-actual 2095 (тот же класс [AVOID×3], четвёртый раз за
  сессию) — синхронизирован из ПРЯМОГО вывода CI ("Actual: 2095 tests..."), не из
  local pytest. Reviewer (Agent) поймал реальный P1 в fence_untrusted_content():
  содержимое с буквальной строкой `</untrusted-context>` могло закрыть fence
  раньше и переоткрыть поддельный блок — исправлено экранированием
  `<(/?)untrusted-context` перед вставкой, regression-тест добавлен. 1 итерация
  NEEDS_WORK → LGTM.
- 2026-07-12/13: Phase 5 (F-11 CI hygiene, ветка `fix/phase5-ci-hygiene`) — добавлен
  top-level `permissions: contents: read` в ci.yml (workflow не пишет в repo/PR/issues,
  дефолтный GITHUB_TOKEN мог быть шире); сужен `|| true` на строке с `-k "agent"`
  тестами — раньше глушил ЛЮБОЙ exit code включая реальный fail (exit 1), теперь
  толерантен только к "no tests collected" (exit 5). Оба ветки протестированы
  локально bash-симуляцией до пуша. **Побочная находка:** `test_pattern_escalation_review.py
  ::test_emits_when_due_and_candidates_exist` flaky на этой машине именно сейчас —
  UTC+5 (Алматы) только что пересёк локальную полночь, хук пишет дату в UTC, тест
  сверяет с local `date.today()` → расхождение на 1 день в этом узком окне. НЕ
  трогал (out of scope для F-11, не воспроизводится на CI — раннеры GitHub Actions
  в UTC). Deselect'нут для локальной проверки Phase 5.
- 2026-07-13: F-03 (submission_gate_guard.py, ветка `fix/f03-submission-gate-wording`) —
  design-решение (не механический фикс). Прочитал сам хук: он УЖЕ честно называет себя
  "Soft nudge only... never blocks" в docstring — баг был ТОЛЬКО в формулировке двух
  копий integrity.md ("CRITICAL", "cannot skip ANY", "No exceptions", "mechanically
  enforced... not prose"), которые переобещали hard-block, невозможный для
  PostToolUse/UserPromptSubmit хуков (тот же класс ограничения, что F-12 доказал
  раньше в этой сессии — хук может только инжектить context, не блокировать). Также
  нашёл: project-local `.claude/rules/integrity.md` перечисляет 5 триггеров как
  "auto-invoke gate", но хук реально реализует только 2 (keywords + file-globs) —
  round-number/synthetic-data/paradigm-shift триггеры НЕ wired ни в один хук. Развёл
  явно: "Hook-enforced (soft nudge)" vs "Not hook-enforced — self-apply". User
  подтвердил направление (смягчить wording, не пытаться hard-block — технически
  невозможно для этого класса триггеров) БЕЗ skeptic-сессии, т.к. вывод уже
  верифицирован официальной документацией в рамках F-12 этой же сессии. Docs-only
  diff (2 файла), full suite не затронут (2097/13, ruff clean).
  **Reviewer (iteration 1) поймал реальный P1**: моя первая формулировка "Not
  hook-enforced — self-apply" для round-numbers/synthetic-data была НЕВЕРНОЙ в
  обратную сторону — `validation_theater_guard.py`'s `PERFECT_SCORE_PATTERNS`/
  `SYNTHETIC_DATA_PATTERNS` реально ловят F1=1.0/accuracy=100%/mock_*/
  create_synthetic (просто НЕ через submission_gate_guard.py). Исправлено:
  сузил claim до "not enforced by submission_gate_guard.py specifically",
  явно указал что AUC/np.random.seed конкретно НЕ покрыты ни одним хуком.
  Iteration 2 → LGTM.
  **NEW FINDING (не в этой PR, follow-up):** `validation_theater_guard.py`
  сам страдает тем же классом overclaim — docstring говорит "Blocking mode...
  Hard block", но зарегистрирован на PostToolUse (не может блокировать per
  F-12) И `hooks/registry.yaml` сам говорит `escalation: warn`. Тот же баг,
  другой файл. Не трогал — вне scope F-03, отдельная находка для будущего
  аудита.
- 2026-07-13: Follow-up fix (ветка `fix/validation-theater-guard-wording`) —
  закрыл находку выше по просьбе юзера ("приведи в соответствие"). Тот же
  паттерн что F-03/F-19: только формулировка, НЕ логика (`sys.exit(1)`
  остаётся — это всё ещё сильный сигнал модели, просто не hard-block).
  Исправлено 4 места: (1) docstring hooks/validation_theater_guard.py —
  "Blocking mode... Hard block" → честное объяснение почему PostToolUse не
  может блокировать (tool уже выполнился), (2) inline-комментарий
  `# Hard block` у sys.exit(1) → "Strong signal, not a true block", (3)
  user-facing stderr-сообщение "🚫 BLOCKED: ..." → "🚫 STOP: ... The command
  already ran -- this cannot undo that", (4) hooks/registry.yaml's
  description "Blocks when both signals..." → "Strongly flags (...) — a
  signal, not a preventive block" (теперь согласуется с его же
  `escalation: warn` полем). Также docs/AI_CLAIM_HYGIENE.md:98 "blocks
  synthetic claims from reaching users" → "flags... post-hoc detector, not
  a preventive block". Проверил grep'ом: ни один тест не проверяет точный
  текст "BLOCKED"/"Hard block"/"Blocking mode" у этого хука — 116 связанных
  тестов + full suite (2097/13, 1 deselect той же timezone-flake) прошли
  без изменений. ruff clean.
  **Reviewer iteration 1: NEEDS_WORK (P1)** -- propustil `BENCHMARK.md`,
  kotoraya 3 raza (stroka 27 verdict-cell, 34-36 verbatim captured output,
  65-74 "honest distinction" section) pryamo utverzhdala chto row 1 = true
  block, tem zhe smyslom chto row 2's nastoyaschiy PreToolUse block -- tot zhe
  klass overclaim, ne ispravlen. Takzhe poimal: injection-style soobschenie
  v seredine review (normalnye system-reminders tipa "Auto Mode Active"
  reviewer prinyal za podozritelnye -- korrektno proignoriroval, false
  positive, ne realnaya injection). Ispravleno: table verdict "BLOCKED"->
  "STRONG SIGNAL, post-hoc" (row 1) vs "PREVENTED before disk" (row 2,
  differentiated ot row 1 explicitly); verbatim output sinhronizirovan s
  novym "STOP" tekstom huka; "honest distinction" sektsiya perepisana v
  3-way split (true block / post-hoc signal / soft nudge) + written policy
  kak 4ya kategoriya. Zaodno popravil examples/validation-theater-trap/
  run_trap.py (tot zhe klass "BLOCKED"->"FLAGGED", 4 mesta) -- on napryamuyu
  target demo dlya BENCHMARK.md row 1, ostavlyat nesoglasovannym bylo by
  tem zhe bagom zanovo. Prognal demo-skript tselikom -- vyvod sovpadaet s
  novym tekstom huka 1:1. CODEX_AUDIT_RESULTS.md:83 -- ostavil netronutym
  (historical changelog entry pro proshlyy fiks, ne live claim; reviewer
  sam pometil kak "borderline, not blocking"). ruff+116 testov chisto.
  **Iteration 3: LGTM.** Cap (3) uvazhen -- ne potrebovalsya 4-y tsikl.
  Novaya out-of-chain nahodka ot reviewer'a (ne blocking, P2): demo/
  validation-theater/README.md (starshiy, otdelnyy, ne-ispolnyaemyy demo,
  predshestvuet examples/validation-theater-trap/ iz PR#145) ispolzuet
  myagkuyu "claim blocked" formulirovku -- no ee bazovyy artifact
  (expected_hook_output.txt) uzhe chesten (opisyvaet additionalContext put',
  ne sys.exit(1)). Ne v citation chain etogo fiksa -- otdelnyy follow-up
  tiket, ne trogal.
  **Reviewer iteration 2: NEEDS_WORK (P1) again** -- citation chain shel
  odin hop dalshe chem ya proveril: examples/validation-theater-trap/README.md
  (v tom zhe kataloge chto run_trap.py) sam ssylalsya na tot zhe skript, no
  eschyo ne byl obnovlyon -- 5 mest (headline tagline "block an AI agent",
  table verdict "BLOCKED", "It blocks theater, not success", expected-output
  quote "Theater BLOCKED", "Block fires only when..."). Ispravleno vsyo 5 +
  dobavil korotkuyu "Note on precision" pod zagolovkom (post-hoc signal, ne
  preventive block, ssylka na BENCHMARK.md). Sdelal FINALNYY grep-sweep vsego
  repo na "BLOCKED"/"Hard block"/"Blocking mode" ryadom s validation_theater
  I otdelno na "Theater BLOCKED"/"validation-theater-guard.*BLOCKED" bez
  konteksta -- 0 sovpadeniy. Peresobral demo-skript -- vyvod 1:1 sovpadaet s
  novym README quote. ruff clean. Otpravleno na iteration 3 (cap).
- 2026-07-13: Task #13 (demo/validation-theater/README.md, ветка
  fix/demo-validation-theater-wording) -- poslednyaya out-of-chain nahodka
  ot reviewer'a v predyduschem fikse (iteration 3, P2 not-blocking). 3 mesta
  (stroka 3 intro, stroka 46 table cell, stroka 54 result table) "blocked"/
  "downgraded before reaching the user" -> "flagged, agent required to
  downgrade" + explicit note pro PostToolUse timing. expected_hook_output.txt
  NE tronut -- reviewer sam otsenil ego kak uzhe chestnyy (opisyvaet
  additionalContext-put', "BLOCKED" tam pro evidence-marker rejection,
  ne pro tool-call block). Net testov, ssylayuschihsya na etot demo-fayl --
  docs-only, ruff ne trebovalsya.


- 2026-07-13: P0.2/P0.3/P0.4 (novaya nezavisimaya audit-sessiya, 7.7/10,
  branch fix/p0-input-guard-split) -- proverit VSE 6 klyuchevyh claims audita
  napryamuyu cherez Read/Grep pered nachalom raboty (ne poverit pereskazu).
  Vse 6 podtverdilis: Bash(*) blacklist model, input_guard.py registry
  matcher/fail_mode mismatch, subagent_verify 2-finding minimum, hooks
  registry NE gate-itsya CI (tolko skills), net PostToolUse untrusted-output
  klassifikatora.

  P0.2 (input_guard split): NE pereimenoval input_guard.py (30-file blast
  radius cherez grep) -- ostavil kak est, tolko ispravil docstring (uzhe
  ne pretenduet na "MCP server responses"), izvlek is_high_threat() v
  reusable funktsiyu. Novyy fayl mcp_response_guard.py (PostToolUse, mcp__*)
  zakryvaet realny gap -- scan-it tool_response cherez te zhe scan()/
  collect_strings()/is_high_threat() (reuse, ne duplikat regex). 11 novyh
  testov.

  P0.3 (registry.yaml consistency): ispravil input_guard's matcher
  (Write|Edit|Bash|mcp__ -> mcp__*) i fail_mode (closed -> open, kod sam
  govorit "must sys.exit(0) on parse failure").

  P0.4 (CI gate): dobavil TestHooksRegistryConsistency v test_structure.py.
  KRITICHNO: NE ispolzoval yaml.safe_load -- PyYAML ne CI dependency
  (requirements.txt tolko pytest/ruff/mypy), sushestvuyushiy skills registry
  test uzhe importorskip'itsya i SILENTLY SKIPPED v CI (podtverzhdeno). Napisal
  stdlib-only parser, chtoby moy gate REALNO ranilsya v CI, ne povtoril tu zhe
  oshibku dlya hooks/registry.yaml.

  **SERIOZNAYA NAHODKA (ne v iznachalnom P0 spiske):** novyy gate srazu
  poymal `skeptic_auto_trigger.py` -- kod sam gejtitsya na
  VALIDATION_TOOL_NAMES={Agent,Bash,Skill} (vklyuchaya ArgosArb-critical
  hard-block put', sys.exit(2)), no byl zaregistrirovan TOLKO na
  matcher="Skill|Agent" -- Bash-vetka, vklyuchaya kriticheskiy blok, byla
  100% dead code. Tot zhe klass baga chto F-12 (validation_theater_guard,
  ranshe segodnya), prosto ne obnaruzhen do sistemicheskogo gate'a.
  Ispravleno: dobavlen v PostToolUse(Bash) v settings.json + ta zhe
  "Hard block"->"strong signal" formulirovka chto vezde segodnya.

  Exact-string matcher/event comparison DAL massu false-positive shuma
  (poryadok tokenov Write|Edit vs Edit|Write, '' vs '*' ekvivalentnost',
  pipe-combined multi-event declarations). Perepisal na set/subset/wildcard-
  aware comparison s prefix-glob podderzhkoy (mcp__* pokryvaet mcp__context7).

  Orphan-check nashel 25 hooks/*.py BEZ registry entry (~tret' vseh hookov).
  Klassificiroval i dokumentiroval vse 25: 3 chistyh biblioteki (doc_bridge,
  doc_registry, expert_registry -- net main()), 7 REALNYH zaregistrirovannyh
  hookov prosto propushennyh iz registry (real entries s tochnym event/
  matcher iz settings.json), 7 DORMANT hookov -- imeyut main() i deklariruyut
  namerenie v svoem docstring, no NIGDE ne zaregistrirovany, nikogda ne
  zapuskayutsya. NE vklyuchil ih v settings.json (eto povedencheskoe reshenie
  -- neizvestnoe vzaimodejstvie, mozhet byt' namerenno otklyucheny), dokumentiroval
  chestno kak "dormant, not currently registered".

  Popravil webhook_notify.py: docstring zayavlyal "Stop/PostToolUse", no
  realno zaregistrirovan tolko na Stop, kod ne imeet tool-specific vetvleniya.
  NE dobavil PostToolUse registratsiyu -- eto setevoy vyzov (Slack/Telegram)
  s matcher="*" (kazhdyy tool call), rasширение oblasti deystviya = realnoe
  povedencheskoe reshenie, ne tihiy fiks.

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
[summarized] **PR #171 MERGED (2026-07-12, branch `improve/boyko-knowledge-audit-skill`, commit `de27b21`):** boyko-knowledge-audit v...
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
[summarized] - [2026-07-12 23:07] `8fa2db7`: fix(ci): sync README Tests badge to CI-authoritative count (2078)
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
