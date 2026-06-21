# Сравнительная таблица: Текущая конфигурация vs Полный потенциал Claude Code

**Дата**: 2026-03-31 | **Пользователь**: sboi (Windows 10 Pro)

---

## 1. CLAUDE.md и Rules

| Аспект | Текущее | Максимум | Статус | Рекомендация |
|--------|---------|----------|--------|-------------|
| CLAUDE.md (global) | 66 строк | ≤200 строк рекомендовано | ✅ Отлично | В рамках бюджета |
| Rules (модульные) | 8 файлов, 290 строк | Без лимита (по контексту) | ✅ Отлично | coding-style, context-loading, integrity, memory-protocol, mentor-protocol, permissions, security, testing — полный набор |
| Project CLAUDE.md | Нет | В каждом проекте | ⚠️ Не используется | Создавать CLAUDE.md в каждом рабочем проекте |
| Nested CLAUDE.md | Нет | В поддиректориях | ⚠️ Не используется | Для монорепо/больших проектов |
| Tiered Context | Нет | 3 уровня | ⚠️ Не используется | Tier 1 (<800 tok) / Tier 2 (on-demand) / Tier 3 (ссылки) |

---

## 2. Permissions (Разрешения)

| Аспект | Текущее | Максимум | Статус |
|--------|---------|----------|--------|
| Permission mode | default (implicit) | 6 режимов | ⚠️ Можно переключать |
| Allow rules | 11 правил (Bash/Read/Write/Edit/Grep/Glob/Task/WebFetch/WebSearch/Skill/NotebookEdit — всё *) | Гранулярные по паттернам | ⚠️ Слишком широкие |
| Deny rules | 27 правил | Без лимита | ✅ Отлично |
| Auto mode | Не используется | Фоновый классификатор, min prompts | ⚠️ Не включён |
| PermissionRequest hook | ✅ permission_policy.py | Программная auto-allow/deny | ✅ Используется |

### Детали deny rules (текущие)

| Категория | Правила | Оценка |
|-----------|---------|--------|
| Деструктивные | rm -rf, format, --delete-all | ✅ |
| Git опасные | push --force, reset --hard, clean -fd, branch -D | ✅ |
| SQL injection | DROP TABLE/DATABASE, TRUNCATE TABLE | ✅ |
| System escape | chmod 777, npm publish, curl\|bash, wget\|bash | ✅ |
| Secrets | Write(.env*), Write(secrets/**) | ✅ |
| Test protection | Edit(*.test.py, *.test.ts, *.spec.ts, *_test.py, *tests.py) | ✅ |
| Container | docker rm, kubectl delete | ✅ |
| Background process | `> /dev/null 2>&1 &` | ✅ |

**Вердикт**: Deny rules — одна из лучших конфигураций. Allow rules слишком широкие (`Bash(*)`), но компенсируются deny rules и PreToolUse hooks.

---

## 3. Hooks (Хуки)

| Событие | Текущее | Скрипты | Возможно (26 всего) | Статус |
|---------|---------|---------|---------------------|--------|
| SessionStart | ✅ | session_start.py | startup\|resume\|clear\|compact | ✅ |
| UserPromptSubmit | ✅ | keyword_router.py, thinking_level.py | Любой промпт | ✅ |
| PreToolUse (Bash) | ✅ | pre_commit_guard.py | Перед командами | ✅ |
| PreToolUse (Edit\|Write) | ✅ | read_before_edit.py, security_verify.py | Перед записью | ✅ |
| PreToolUse (mcp__*) | ✅ | input_guard.py, mcp_circuit_breaker.py | Перед MCP | ✅ |
| PreToolUse (mcp specific) | ✅ | mcp_locality_guard.py, redact.py | PII redaction | ✅ |
| PostToolUse (mcp__*) | ✅ | mcp_circuit_breaker_post.py | После MCP | ✅ |
| PostToolUse (Edit\|Write) | ✅ | post_format.py, plan_mode_guard.py | Автоформат | ✅ |
| PostToolUse (Skill\|Agent) | ✅ | drift_guard.py, evidence_guard.py, spot_check_guard.py | Quality gates | ✅ |
| PostToolUse (Bash) | ✅ | memory_guard.py, checkpoint_guard.py, post_commit_memory.py, pattern_extractor.py | Memory + patterns | ✅ |
| PreCompact | ✅ | pre_compact.py | Перед сжатием | ✅ |
| Stop | ✅ | session_save.py, webhook_notify.py | По завершении | ✅ |
| Notification | ✅ | console beep | Уведомления | ✅ |
| PermissionRequest | ✅ | permission_policy.py | Auto-allow/deny | ✅ |
| FileChanged | ✅ | env_reload.py (.env files) | Изменение файлов | ✅ |
| CwdChanged | ✅ | direnv_loader.py | Смена директории | ✅ |
| SubagentStart | ✅ | agent_lifecycle.py --start | Запуск субагента | ✅ |
| SubagentStop | ✅ | agent_lifecycle.py --stop | Стоп субагента | ✅ |
| ConfigChange | ✅ | config_audit.py | Изменение конфига | ✅ |
| TeammateIdle | ✅ | team_rebalance.py | Agent Teams idle | ✅ |
| PostToolUseFailure | ❌ | — | Обработка ошибок | 🔴 Не настроен |
| StopFailure | ❌ | — | API ошибки | 🔴 Не настроен |
| TaskCreated | ❌ | — | Создание задач | ⚪ Опционально |
| TaskCompleted | ❌ | — | Завершение задач | ⚪ Опционально |
| InstructionsLoaded | ❌ | — | Загрузка CLAUDE.md | ⚪ Опционально |
| WorktreeCreate | ❌ | — | Создание worktree | ⚪ Опционально |
| WorktreeRemove | ❌ | — | Удаление worktree | ⚪ Опционально |
| PostCompact | ❌ | — | После сжатия | ⚪ Опционально |
| Elicitation | ❌ | — | MCP user input | ⚪ Опционально |
| ElicitationResult | ❌ | — | MCP response | ⚪ Опционально |
| SessionEnd | ❌ | — | Конец сессии | ⚪ Опционально |

**Итого**: 20/26 событий задействовано (77%). **30 hook scripts**.

### Уникальные hook-фичи

| Фича | Текущее | Статус |
|------|---------|--------|
| Async wrappers (неблокирующие) | ✅ async_wrapper.py | ✅ Продвинуто |
| MCP Circuit Breaker | ✅ pre + post | ✅ Продвинуто |
| PII Redaction | ✅ redact.py | ✅ Продвинуто |
| Evidence guards | ✅ evidence_guard.py, spot_check_guard.py | ✅ Продвинуто |
| Drift detection | ✅ drift_guard.py | ✅ Продвинуто |
| Pattern learning | ✅ pattern_extractor.py | ✅ Продвинуто |
| Auto-format | ✅ post_format.py | ✅ |
| Webhook notifications | ✅ webhook_notify.py | ✅ |
| Custom status line | ✅ statusline.py | ✅ |
| Spinner tips (custom) | ✅ 21 custom tip | ✅ |
| PreToolUse input modification | ❌ | 🔴 v2.0.10+ фича |
| HTTP hooks | ❌ | ⚠️ Не используется |
| Prompt hooks (LLM) | ❌ | ⚠️ Не используется |
| Agent hooks (multi-turn) | ❌ | ⚠️ Не используется |

---

## 4. Субагенты и Teams

| Аспект | Текущее | Максимум | Статус |
|--------|---------|----------|--------|
| Core agents | 7: navigator, builder, reviewer, tester, explorer, architect, sec-auditor | Без лимита | ✅ |
| Extended agents | 2: teacher, verifier | Без лимита | ✅ |
| Archived agents | 4: security-guard, skill-suggester, fe-mentor, scope-guard | — | ⚠️ Можно восстановить при необходимости |
| Agent Teams | 3: review-squad, build-squad, research-squad | Без лимита | ✅ |
| Agent memory | Настроено (user/project/local) | ✅ | ✅ |
| Agent isolation (worktree) | Доступно | Per-agent | ⚠️ Проверить frontmatter |
| Agent models | Настроены (opus/sonnet per agent) | opus/sonnet/haiku | ✅ |
| Agent maxTurns | Настроены | Per-agent | ✅ |

### Матрица агентов

| Агент | Модель | Memory | Isolation | Для чего |
|-------|--------|--------|-----------|----------|
| navigator | opus | user | — | Task planning (80/20) |
| builder | sonnet | — | worktree | Code implementation |
| reviewer | sonnet | project | — | Code review |
| tester | sonnet | — | worktree | Writing tests |
| explorer | sonnet | local | — | Codebase search |
| architect | opus | — | — | Architecture design |
| sec-auditor | opus | project | — | Security audit |
| teacher | opus | — | — | Explaining concepts |
| verifier | — | — | — | Fact-checking |

### Матрица teams

| Team | Агенты | Паттерн |
|------|--------|---------|
| review-squad | reviewer + sec-auditor | Parallel |
| build-squad | builder + tester | Parallel (worktree) |
| research-squad | explorer + verifier | Sequential |

---

## 5. Skills (Навыки)

| Skill | Тип | Trigger | Статус |
|-------|-----|---------|--------|
| routing-policy | Core | Любая задача | ✅ Активен |
| brainstorming | Core | Архитектура, дизайн, альтернативы | ✅ Активен |
| tdd-workflow | Core | Tests, TDD, coverage | ✅ Активен |
| agent-teams | Core | Параллельная работа | ✅ Активен |
| git-worktrees | Core | Изоляция, эксперименты | ✅ Активен |
| mentor-mode | Core | Объяснения, обучение | ✅ Активен |
| reference-registry | Core | Внешние ссылки | ✅ Активен |
| humanizer | Core | Убрать AI-стиль | ✅ Активен |
| security-audit | Extension | Аудит безопасности | ✅ Активен |
| archcode-genomics | Extension | ARCHCODE проект | ✅ Специализированный |
| geoscan | Extension | Гео-данные | ✅ Специализированный |
| notebooklm | Extension | NotebookLM | ✅ Специализированный |
| suno-music | Extension | Suno AI | ✅ Специализированный |
| claude-api | Built-in | Anthropic API/SDK | ✅ Встроенный |
| simplify | Built-in | Code review | ✅ Встроенный |
| loop | Built-in | Recurring tasks | ✅ Встроенный |
| schedule | Built-in | Cloud scheduling | ✅ Встроенный |
| update-config | Built-in | Settings changes | ✅ Встроенный |
| keybindings-help | Built-in | Keyboard shortcuts | ✅ Встроенный |

**Итого**: 8 custom + 5 extension + 6 built-in = **19 skills**

### Не используемые возможности skills

| Возможность | Статус | Описание |
|------------|--------|----------|
| Inline code execution | ❌ | `` `command` `` в SKILL.md для динамического контекста |
| restrict-tools | ❌ | Ограничение инструментов внутри skill |
| disable-model-invocation | ❌ | Прямой вывод без LLM |
| "ultrathink" keyword | ❌ | Автовключение extended thinking в skill |

---

## 6. MCP серверы

| Аспект | Текущее | Максимум | Статус |
|--------|---------|----------|--------|
| Глобальный .mcp.json | ❌ Отсутствует | ~/.claude/.mcp.json | 🔴 Не настроен |
| Проектный .mcp.json | ❌ | .claude/.mcp.json | 🔴 Не настроен |
| Встроенные (claude.ai) | ✅ 9 серверов | 400+ в реестре | ⚠️ Частично |

### Текущие MCP (через claude.ai подписку)

| Сервер | Статус | Примечание |
|--------|--------|------------|
| Context7 | ✅ Подключён | Документация библиотек |
| Figma | ✅ Подключён | Дизайн → код |
| Gmail | ✅ Подключён | Email |
| Linear | ✅ Подключён | Project management |
| Sentry | ✅ Подключён | Error monitoring |
| Supabase | ✅ Подключён | Database |
| Vercel | ✅ Подключён | Deploy |
| bioRxiv | ✅ Подключён | Препринты |

### Не подключённые MCP (рекомендуемые)

| Сервер | Для чего | Приоритет |
|--------|----------|-----------|
| GitHub MCP | Repo, PR, Issues, Actions | 🔴 Высокий |
| Playwright | Browser automation, testing | ⚠️ Средний |
| PostgreSQL/SQLite | Direct DB access | ⚠️ Средний |
| Exa AI | Semantic search (лучше WebSearch) | ⚠️ Средний |
| Slack | Team communication | ⚠️ Средний |
| Terraform | IaC documentation | ⚪ Низкий |

---

## 7. Плагины

| Аспект | Текущее | Максимум | Статус |
|--------|---------|----------|--------|
| Маркетплейсы | 1 (claude-plugins-official) | Без лимита | ✅ |
| Установленные | 2 (context7, github) — оба **disabled** | Без лимита | 🔴 Не используются! |
| Локальные плагины | ❌ | --plugin-dir | ❌ Не используются |
| Custom marketplace | ❌ | Свой для команды | ⚪ Опционально |

### Полезные неустановленные плагины (из official marketplace)

| Плагин | Для чего | Приоритет |
|--------|----------|-----------|
| commit-commands | Git commit/push/PR workflow | ⚠️ Средний |
| code-review | Specialized PR review | ⚠️ Средний |
| claude-code-setup | Automation recommender | ⚠️ Средний |
| claude-md-management | CLAUDE.md improver | ⚪ Низкий |
| typescript-lsp | TS/JS code intelligence | ⚠️ Для frontend |
| pyright-lsp | Python type checking | ⚠️ Для Python |

---

## 8. Memory (Память)

| Аспект | Текущее | Максимум | Статус |
|--------|---------|----------|--------|
| Auto-memory (global) | ✅ ~/.claude/projects/*/memory/ | Всегда включена | ✅ |
| Memory files | 5: MEMORY.md, feedback, user_profile, project_goals, archcode_audit, reference_guide | Без лимита | ✅ |
| Memory templates | ✅ 7 шаблонов | Без лимита | ✅ |
| Project memory (.claude/memory/) | ❌ В текущем проекте нет | activeContext + decisions + patterns + goals | 🔴 Не используется |
| Agent memory | Настроено в frontmatter | Per-agent persistent | ✅ |
| /dream | ❌ | Консолидация памяти | ⚠️ Не используется |

---

## 9. Прочие настройки

| Аспект | Текущее | Максимум | Статус |
|--------|---------|----------|--------|
| Status line | ✅ statusline.py | Custom scripts | ✅ |
| Spinner tips | ✅ 21 custom tip | Без лимита | ✅ |
| Auto updates | stable | stable/beta/canary | ✅ |
| Sandbox | ❌ Не включён | macOS Seatbelt / Linux bubblewrap / WSL2 | 🔴 Windows — нет нативного sandbox |
| Vim mode | ❌ | /vim | ⚪ Опционально |
| Voice mode | ❌ | Push-to-talk | ⚪ Опционально |
| Chrome extension | ❌ | Browser automation | ⚪ Опционально |
| Remote control | ❌ | Управление с mobile | ⚪ Опционально |
| Scheduled tasks | ❌ | /schedule (cloud) | ⚠️ Не используется |
| Worktree sessions | ❌ | claude -w name | ⚠️ Не используется |
| Fast mode | ❌ | /fast | ⚪ Опционально |
| Extended thinking | По умолчанию | /effort max + ultrathink | ⚠️ Не оптимизировано |

---

## 10. СВОДНАЯ ОЦЕНКА

### Процент использования по категориям

| Категория | Используется | Доступно | Процент | Оценка |
|-----------|-------------|----------|---------|--------|
| **CLAUDE.md + Rules** | 9 файлов | 9 | 100% | ✅✅✅ |
| **Hooks** | 20 событий, 30 скриптов | 26 событий | 77% | ✅✅ |
| **Deny rules** | 27 правил | best-in-class | 95% | ✅✅✅ |
| **Agents** | 9 + 3 teams | 12 | 100% | ✅✅✅ |
| **Skills** | 19 (8+5+6) | — | 90% | ✅✅ |
| **Memory** | Auto + templates | Full system | 70% | ✅ |
| **MCP серверы** | 8 (cloud) | 400+ | 2% | 🔴 |
| **Плагины** | 2 (disabled) | 50+ official | 0% | 🔴🔴 |
| **Sandbox** | 0% (Windows) | Ограничен | 0% | ⚠️ Platform limit |
| **Scheduling** | 0% | /schedule + /loop | 0% | 🔴 |
| **Worktrees** | 0% | claude -w | 0% | ⚠️ |
| **CI/CD headless** | 0% | claude -p | 0% | ⚠️ |

### Общая оценка: ~60% потенциала

---

## 11. ТОП-10 РЕКОМЕНДАЦИЙ (по приоритету)

### 🔴 Критические (наибольший impact)

| # | Что | Почему | Действие |
|---|-----|--------|----------|
| 1 | **Включить плагины** | 2 установлены, но disabled. Ноль пользы. | `/plugin enable context7@claude-plugins-official` + github |
| 2 | **Настроить GitHub MCP** | Нет прямого доступа к repos/PRs/issues | Добавить в .mcp.json или использовать plugin |
| 3 | **Project memory** | activeContext.md + decisions.md в каждом проекте | Создать .claude/memory/ в рабочих проектах |
| 4 | **PostToolUseFailure hook** | Ошибки MCP/tools остаются без обработки | Добавить error recovery hook |

### ⚠️ Важные (заметное улучшение)

| # | Что | Почему | Действие |
|---|-----|--------|----------|
| 5 | **Auto mode** | Сократит permission prompts в разы | Настроить `defaultMode: "auto"` или использовать `--enable-auto-mode` |
| 6 | **Worktree sessions** | Изолированные эксперименты без risk | `claude -w experiment-name` |
| 7 | **LSP плагины** | Code intelligence (go-to-def, type errors) | Установить pyright-lsp для Python |
| 8 | **/schedule** | Автоматизация рутинных проверок | Ночные code review, dependency audits |

### ⚪ Полезные (приятные бонусы)

| # | Что | Почему | Действие |
|---|-----|--------|----------|
| 9 | **PreToolUse input modification** | Transparent secret redaction, auto dry-run | Обновить hooks для v2.0.10+ |
| 10 | **Prompt/Agent hooks** | LLM-based verification вместо regex | Добавить для сложных проверок безопасности |

---

## 12. QUICK WINS (5 минут каждый)

```bash
# 1. Включить плагины
/plugin enable context7@claude-plugins-official
/plugin enable github@claude-plugins-official

# 2. Попробовать auto mode
claude --enable-auto-mode

# 3. Worktree эксперимент
claude -w test-feature

# 4. Extended thinking для сложных задач
/effort max

# 5. Побочный вопрос без засорения контекста
/btw what does this error mean?

# 6. Массовые изменения
/batch rename all snake_case to camelCase in src/

# 7. Визуализация контекста
/context

# 8. Консолидация памяти
/dream
```
