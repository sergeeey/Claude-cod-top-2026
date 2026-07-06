# ТЗ: Атомарный независимый аудит Claude-cod-top-2026 через Codex

**Статус:** DRAFT — ждёт подтверждения перед запуском
**Дата:** 2026-07-06
**Инструмент верификации:** Codex CLI (codex-cli 0.142.4, авторизован, `ready: true` — проверено `codex-companion.mjs setup --json`)

## Зачем Codex, а не ещё один Claude-агент

`reviewer` + `sec-auditor` + `skeptic` — все три модель Claude. Общая архитектура =
общие слепые зоны. Прецедент уже был в этом репо (см. `CLAUDE.md` чеклист п.4):
2026-06-04 HIGH-баг прошёл через 3 самопроверки Claude подряд, Codex поймал его
с первого захода. Разные веса → разные ошибки ловятся первыми.

## Почему атомизация, а не один вызов "проверь весь репо"

Репо большое: 85 hooks, 14 agents (+3 команды), 119 skills (12 core + 107
extensions), 14 rules, 69 тестовых файлов, ~10 markdown-документов с claims.
Один Codex-вызов на "весь репо" либо не влезет в осмысленный контекст, либо
даст generic ответ уровня "в целом выглядит нормально". Узкий scope на атом
+ конкретный чек-лист = глубокая, а не поверхностная проверка.

## Проверенная механика вызова

- `/codex:review` и `/codex:adversarial-review` — **не подходят**: они
  git-diff-scoped (working-tree или branch vs `--base`), не берут
  произвольный путь уже закоммиченного, стабильного репо.
- Правильный примитив: `Agent(subagent_type="codex:codex-rescue")`
  (он же слэш-команда `/codex:rescue`) — свободный natural-language prompt.
  Каждый atom-вызов должен явно указывать: (a) какой путь читать, (b) что
  НЕ читать (иначе Codex расползается по всему репо), (c) конкретный
  чек-лист вопросов, (d) требуемый формат ответа.
- Все атомы запускаются **независимо** — один Codex-вызов не видит вывод
  другого. Это тот же Context Asymmetry Rule, что и для skeptic в
  `rules/falsification-ladder.md`: агент с чужим reasoning склонен его
  подтверждать, а не искать разрыв.

## Атомы (11, по факту структуры репо на 2026-07-06)

| # | Атом | Объём | Чек-лист |
|---|------|-------|----------|
| 1 | `hooks/` — security & permission | 9: `input_guard`, `permission_policy`, `mcp_locality_guard`, `mcp_circuit_breaker(+post)`, `security_verify`, `elicitation_guard`, `config_audit`, `drift_guard` | Обход блокировки, false-negative на инъекции, race в circuit breaker, хардкод секретов |
| 2 | `hooks/` — git/quality gates | 9: `pre_commit_guard`, `commit_test_gate`, `weakened_test_guard`, `syntax_guard`, `read_before_edit`, `iteration_guard`, `checkpoint_guard`, `task_audit`, `instructions_audit` | Можно ли обойти гейт незаметно, false positive/negative, гонки между хуками одного PostToolUse-события |
| 3 | `hooks/` — memory/knowledge | 20: `memory_guard`, `pre_vault_write`, `knowledge_librarian`, `moc_autolink`, `wiki_reminder`, `prompt_wiki_inject`, `pattern_extractor(+escalation)`, `observation_capture`, `session_*`, `*_compact`, `doc_bridge/registry`, `file_auto_parser`, `expert_registry`, `vector_store`, `thematic_index_router` | Path traversal (прецедент был в PR #106), unbounded growth файлов, гонки записи в один файл из разных хуков — тот же класс бага, что нашли в `pre_compact.py` сегодня; есть ли аналоги здесь |
| 4 | `hooks/` — FL/research methodology | 15: `claim_entropy_tracker`, `estimand_guard`, `promotion_gate_guard`, `reject_gate_guard`, `null_results_pre_check`, `null_retroscan`, `experiment_insight`, `hypothesis_router`, `goal_budget_guard`, `goal_stub_detector`, `rationalization_detector`, `spot_check_guard`, `validation_theater_guard`, `skeptic_auto_trigger`, `subagent_verify` | Реально ли нельзя обойти гейт; соответствие хука тому, что заявляет `rules/*.md`, который он должен enforce-ить |
| 5 | `hooks/` — routing/orchestration | 10: `keyword_router`, `project_classifier`, `smart_model_router`, `thinking_level`, `plan_mode_guard`, `agent_context_filter`, `agent_lifecycle`, `team_rebalance`, `worktree_lifecycle`, `async_wrapper` | Infinite loop (recursion guard есть везде?), `async_wrapper` + `emit_hook_result` silent failure — уже задокументированный anti-pattern в `hooks/CLAUDE.md`, проверить что никто не наступил на него снова |
| 6 | `hooks/` — learning/telemetry/misc | 20: `learning_tracker/tips`, `mentor_nudge`, `hook_observability`, `hook_state`, `model_usage_tracker`, `statusline`, `webhook_notify`, `stop_failure`, `post_tool_failure`, `first_run_check`, `env_reload`, `direnv_loader`, `ace_reflector`, `markitdown_auto_convert`, `auto_capture`, `post_format`, `post_commit_memory`, `cogniml_client` | Дедуп-баг класса "44 копии в goals.md" (найден сегодня) — есть ли похожий паттерн в других memory-пишущих хуках этой группы |
| 7 | `agents/` (14 .md + 3 команды) | всё содержимое `agents/` | Prompt injection через description-поле, tool-permission scope (агент не даёт себе больше прав чем описано), согласованность `tools:` с реальным использованием в теле промпта |
| 8 | `skills/` (12 core + 107 extensions) | разбить на ~6 суб-батчей по ~20 (алфавитно, детерминированно) | Triggers реалистичны (не слишком широкие/узкие), пересечение триггеров двух скилов, битые ссылки на несуществующие файлы/скрипты |
| 9 | `rules/` (14 .md) | всё содержимое `rules/` | Внутренние противоречия между правилами (прецедент — decisions.md canonical/legacy split, найден и исправлен сегодня в личном конфиге); правило, которое не enforce-ится НИ ОДНИМ хуком |
| 10 | `tests/` (69 файлов) | вся папка | Тавтологические тесты (мокают то, что проверяют), покрытие security-critical хуков, дублирующиеся тесты |
| 11 | CI/CD + install + claims-в-документах | `.github/workflows/`, `install.sh`, `install.ps1`, `skill-manager.sh`, `pyproject.toml`, `README.md` + `*_GUIDE*.md` + `*_COMPARISON*.md` + `AGENTS.md` | Числа в README (hooks/agents/skills/tests count) реально совпадают с `find`/`ls`; badges актуальны; `install.sh` идемпотентен |

## Порядок выполнения

1. **Атомы 1–11 запускаются независимо** — Codex-вызов для атома N не видит
   вывод атома M. Каждый вызов: `Agent(subagent_type="codex:codex-rescue",
   prompt="Audit ONLY <path>. Do not read other directories. <чек-лист>.
   Return: severity + file:line + suggested fix.")`.
2. Технически можно запускать вручную по одному (`/codex:rescue --background`
   + периодическая проверка `/codex:status`), либо все 11 параллельно одним
   `Workflow`-скриптом (это ровно тот случай "N независимых ревьюеров +
   этап сборки", под который создан `Workflow`-инструмент) — **но Workflow
   требует явного запроса пользователя**, я не запускаю его сам.
3. **Сборка (assembly)** — отдельный шаг, делает Claude (не Codex): читает
   все 11 отчётов → убирает дубли находок → строит cross-atom проверки
   (например: claim из атома 11 "85 hooks" сверяется с фактическим счётом
   атомов 1–6) → ранжирует по severity → применяет
   `rules/audit-verification-gate.md` (HIGH/MEDIUM находки от Codex — это
   `[HYPOTHESIS]`, не `[VERIFIED]`, пока не перепроверены grep/тестом).
4. Итог — один документ `docs/CODEX_AUDIT_RESULTS_<date>.md`.

## Оценка стоимости/времени

- 11 независимых Codex-вызовов, каждый ~2–10 минут в зависимости от объёма
  атома (атомы 3, 6, 8 крупнее — дольше).
- Рекомендация: запускать в фоне (`--background`), не блокировать основную
  работу.
- Сборка — один проход Claude, ~10–15 минут чтения и синтеза.

## Что сознательно НЕ делаем (explicit skip)

- FL Full-Ladder / EstimandOps — это devops/audit-задача, не научная
  гипотеза; L0-классификация избыточна.
- Не запускаем `Workflow` автоматически — нужен явный опт-ин пользователя.
- Не запускаем `/codex:review`/`/codex:adversarial-review` — механически
  не подходят (diff-scoped, не path-scoped), см. раздел выше.
