# Claude Code: Полный гайд по всем возможностям (март 2026)

## Оглавление
1. [Архитектура и платформы](#1-архитектура-и-платформы)
2. [60+ слэш-команд](#2-все-слэш-команды)
3. [CLI флаги](#3-cli-флаги-и-режимы-запуска)
4. [Система настроек](#4-система-настроек)
5. [CLAUDE.md — мозг проекта](#5-claudemd--мозг-проекта)
6. [Система разрешений](#6-система-разрешений-6-режимов)
7. [Хуки (26 событий)](#7-хуки--автоматизация-26-событий)
8. [MCP серверы](#8-mcp-серверы--интеграции)
9. [Субагенты и Agent Teams](#9-субагенты-и-agent-teams)
10. [Skills — навыки по запросу](#10-skills--навыки-по-запросу)
11. [Memory — система памяти](#11-memory--система-памяти)
12. [Горячие клавиши](#12-горячие-клавиши)
13. [Headless/CI-CD режим](#13-headlessci-cd-режим)
14. [Расписание и фоновые задачи](#14-расписание-и-фоновые-задачи)
15. [Git Worktree — изоляция](#15-git-worktree--изоляция)
16. [Скрытые и продвинутые фичи](#16-скрытые-и-продвинутые-фичи)
17. [Лайфхаки для power users](#17-лайфхаки-для-power-users)
18. [Оптимизация контекста](#18-оптимизация-контекста)
19. [Интеграционные workflow](#19-интеграционные-workflow)
20. [Agent SDK](#20-agent-sdk)
21. [Хронология релизов](#21-хронология-релизов)

---

## 1. Архитектура и платформы

Claude Code доступен на 5 платформах:

| Платформа | Особенности |
|-----------|-------------|
| **CLI** (терминал) | Полный контроль, Vim mode, 6 режимов permissions, background tasks |
| **Desktop App** (Mac/Win) | Visual diff, live preview, Computer Use (Mac), PR мониторинг |
| **VS Code Extension** | Inline diff, sidebar panel, @file references |
| **JetBrains Extension** | Все IDE (IntelliJ, PyCharm, GoLand...), remote dev |
| **Web App** (claude.ai/code) | Облачные VM, scheduled tasks, SSH sessions |

### Уникальные фичи по платформам
- **Desktop**: Computer Use (управление экраном Mac), визуальный diff с комментариями, live preview dev-сервера, PR мониторинг с auto-fix
- **CLI**: Vim mode, `Ctrl+B` фоновые задачи, полный контроль разрешений, tmux интеграция
- **Web**: Облачное выполнение, persistent scheduled tasks, teleport в локальный CLI

---

## 2. Все слэш-команды

### Управление сессией
| Команда | Описание |
|---------|----------|
| `/clear`, `/reset`, `/new` | Очистить историю |
| `/resume [session]` | Возобновить прошлую сессию |
| `/rename [name]` | Переименовать сессию |
| `/branch`, `/fork` | Создать ветку разговора |
| `/rewind`, `/checkpoint` | Восстановить до точки |
| `/compact [instructions]` | Сжать контекст с фокусом |

### Работа с кодом
| Команда | Описание |
|---------|----------|
| `/diff` | Интерактивный просмотр изменений |
| `/security-review` | Аудит безопасности изменений |
| `/copy [N]` | Копировать ответ в буфер |
| `/export [filename]` | Экспортировать разговор |
| `/batch <instruction>` | Массовые изменения параллельно |
| `/simplify` | Ревью кода на качество/эффективность |

### Конфигурация
| Команда | Описание |
|---------|----------|
| `/config`, `/settings` | Открыть настройки |
| `/model [model]` | Выбрать модель |
| `/effort [level]` | Уровень мышления (low/medium/high/max/auto) |
| `/fast [on\|off]` | Быстрый режим |
| `/theme [color]` | Тема оформления |
| `/vim` | Vim mode |
| `/keybindings` | Настройка клавиш |
| `/terminal-setup` | Настройка терминала |
| `/permission-modes` | Управление разрешениями |

### Агенты и инструменты
| Команда | Описание |
|---------|----------|
| `/agents` | Управление субагентами |
| `/mcp` | Управление MCP серверами |
| `/plugin` | Управление плагинами |
| `/skills` | Список навыков |
| `/plan [description]` | Войти в режим планирования |

### Память и контекст
| Команда | Описание |
|---------|----------|
| `/memory` | Редактировать CLAUDE.md и auto-memory |
| `/init` | Инициализировать CLAUDE.md проекта |
| `/context` | Визуализация использования контекста |

### Автоматизация
| Команда | Описание |
|---------|----------|
| `/schedule [description]` | Запланировать облачную задачу |
| `/loop [interval] <prompt>` | Повторяющаяся задача (напр. `/loop 5m /babysit-prs`) |

### Интеграции
| Команда | Описание |
|---------|----------|
| `/desktop`, `/app` | Продолжить в Desktop App |
| `/remote-control` | Удалённое управление с claude.ai |
| `/install-github-app` | GitHub Actions интеграция |
| `/install-slack-app` | Slack интеграция |
| `/pr-comments [PR]` | Загрузить комментарии PR |
| `/chrome` | Управление Chrome |

### Информация
| Команда | Описание |
|---------|----------|
| `/status` | Версия, модель, аккаунт |
| `/usage` | Лимиты плана и rate limits |
| `/cost` | Статистика токенов |
| `/stats` | Визуализация использования |
| `/insights` | Отчёт по сессиям |
| `/release-notes` | Changelog |
| `/doctor` | Диагностика установки |

### Специальные
| Команда | Описание |
|---------|----------|
| `/btw <question>` | Побочный вопрос без сохранения в контекст |
| `/dream` | Консолидация памяти (аналог REM-сна) |
| `/sandbox` | Включить OS-изоляцию |
| `/voice` | Голосовой ввод |

---

## 3. CLI флаги и режимы запуска

### Запуск сессии
```bash
claude                              # Интерактивная сессия
claude "query"                      # С начальным промптом
claude -p "query"                   # Print mode (выход после ответа)
claude -c                           # Продолжить последнюю сессию
claude -r "session"                 # Возобновить конкретную сессию
claude -n "name"                    # Назвать сессию
claude -w feature-name              # Изолированный worktree
claude --remote "task"              # Облачная сессия на claude.ai
```

### Модель и мышление
```bash
--model claude-opus-4-6             # Выбрать модель
--effort low|medium|high|max        # Уровень мышления
--fallback-model sonnet             # Fallback при перегрузке
--betas interleaved-thinking        # Бета-фичи
```

### Разрешения
```bash
--permission-mode plan              # Режим разрешений
--enable-auto-mode                  # Auto mode
--dangerously-skip-permissions      # Обход (только для контейнеров!)
```

### Агенты и инструменты
```bash
--agent agent-name                  # Запустить как агент
--agents '{"name":{...}}'           # Динамические агенты
--tools "Bash,Edit,Read"            # Ограничить инструменты
--disallowedTools "Bash(*)"         # Заблокировать инструменты
```

### Ввод/вывод
```bash
--output-format json|text|stream-json  # Формат вывода
--input-format json|text               # Формат ввода
--json-schema '{...}'                  # Валидация JSON-схемой
--include-partial-messages             # Стриминг событий
```

### Системный промпт
```bash
--system-prompt "prompt"            # Заменить весь промпт
--append-system-prompt "text"       # Добавить к дефолтному
--system-prompt-file ./file         # Загрузить из файла
```

### Продвинутые
```bash
--add-dir ../other                  # Добавить рабочие директории
--chrome                            # Browser control
--tmux                              # Создать tmux-сессию
--teammate-mode auto|in-process|tmux  # Режим Agent Teams
--max-turns 3                       # Лимит agentic turns
--max-budget-usd 5.00              # Лимит расходов
--bare                              # Без хуков, skills, MCP
--debug "api,mcp"                   # Debug-логирование
--verbose                           # Полный вывод
```

---

## 4. Система настроек

### 4 уровня приоритета (от высшего к низшему)
1. **Managed** — серверные настройки организации
2. **User** — `~/.claude/settings.json`
3. **Project** — `.claude/settings.json`
4. **Local** — `.claude/settings.local.json` (gitignored, личные)

### Полная структура `.claude/`
```
.claude/
├── settings.json              # Настройки проекта (в git)
├── settings.local.json        # Личные переопределения (gitignored)
├── CLAUDE.md                  # Инструкции проекта
├── .mcp.json                  # MCP серверы
├── memory/                    # Память проекта
│   ├── activeContext.md       # Текущая задача
│   ├── decisions.md           # Архитектурные решения
│   └── goals.md              # Цели спринта
├── agents/                    # Кастомные субагенты
│   └── agent-name.md
├── skills/                    # Кастомные навыки
│   └── skill-name/
│       └── SKILL.md
├── rules/                     # Модульные правила
│   ├── coding-style.md
│   ├── security.md
│   └── testing.md
├── hooks/                     # Скрипты хуков
├── checkpoints/               # Точки сохранения
├── worktrees/                 # Временные worktrees
├── tasks/                     # Фоновые задачи
└── plugins/                   # Локальные плагины
```

### Ключевые настройки settings.json
```json
{
  "permissions": {
    "defaultMode": "default|acceptEdits|plan|auto|dontAsk|bypassPermissions",
    "allow": ["Bash(git status *)", "Read", "Glob"],
    "deny": ["Bash(rm -rf *)", "Edit(.env*)"],
    "autoMode": {
      "environment": {
        "trustedRepos": ["org/repo"],
        "blockRules": ["description"],
        "allowRules": ["description"]
      }
    }
  },
  "hooks": { "...": "..." },
  "model": "opus",
  "effort": "high",
  "fastModeEnabled": true,
  "env": { "VAR_NAME": "value" },
  "sandbox": { "enabled": true },
  "autoUpdatesChannel": "stable|beta|canary"
}
```

---

## 5. CLAUDE.md — мозг проекта

### Что включать
- Идентичность проекта, стек, язык коммуникации
- Стандарты кода (язык, стиль, конвенции)
- Тестовые требования
- Рабочие паттерны (80/20, plan-first, TDD)
- Архитектурные ограничения
- Интеграционные инструкции
- Правила безопасности

### Лучшие практики
- **До 200 строк** — каждая строка стоит токенов каждую сессию
- **Модульность** — выносите правила в `.claude/rules/` (загружаются по контексту)
- **Иерархия** — вложенные CLAUDE.md в поддиректориях имеют приоритет
- **Compaction survival** — добавьте секцию что сохранять при сжатии контекста
- **Reference**: Trail of Bits шаблон (github.com/trailofbits/claude-code-config)

### Что НЕ включать
- То, что Claude и так делает правильно
- Документацию (используйте skills или Context7 MCP)
- Эфемерные данные (используйте tasks или activeContext)

---

## 6. Система разрешений (6 режимов)

| Режим | Промпты | Безопасность | Для чего |
|-------|---------|-------------|----------|
| `default` | На всё кроме чтения | Ревью каждого действия | Чувствительная работа |
| `acceptEdits` | Только на команды | Ревью команд | Итерация кода |
| `plan` | Только на команды (read-only) | Планирование | Исследование кодбазы |
| `auto` | Ничего (fallback при необходимости) | Фоновый классификатор | Длинные задачи |
| `dontAsk` | Ничего (deny если не в allowlist) | Строгий allowlist | CI/CD |
| `bypassPermissions` | Ничего | Нет проверок | Только контейнеры! |

### Синтаксис правил
```json
{
  "allow": ["Bash(npm test)", "Bash(git log *)", "Read", "Edit(src/**/*.ts)"],
  "deny": ["Bash(rm -rf *)", "Bash(git push --force*)", "Edit(.env*)"]
}
```

### Auto Mode классификатор
**Разрешает**: локальные файловые операции, установку зависимостей, read-only HTTP, push в свою ветку
**Блокирует**: код из URL, отправку данных наружу, production deploy, mass deletion, force push в main

---

## 7. Хуки — автоматизация (26 событий)

### Все события

| Событие | Когда срабатывает |
|---------|-------------------|
| `SessionStart` | Начало/возобновление сессии |
| `UserPromptSubmit` | Пользователь отправил промпт |
| `PreToolUse` | Перед выполнением инструмента |
| `PermissionRequest` | Диалог разрешений |
| `PostToolUse` | После успешного инструмента |
| `PostToolUseFailure` | После ошибки инструмента |
| `Notification` | Уведомление отправлено |
| `SubagentStart` | Субагент запущен |
| `SubagentStop` | Субагент завершён |
| `TaskCreated` | Задача создана |
| `TaskCompleted` | Задача завершена |
| `Stop` | Claude закончил ответ |
| `StopFailure` | Ответ с ошибкой API |
| `TeammateIdle` | Агент команды простаивает |
| `InstructionsLoaded` | CLAUDE.md загружен |
| `ConfigChange` | Изменение конфига |
| `CwdChanged` | Смена рабочей директории |
| `FileChanged` | Изменение отслеживаемого файла |
| `WorktreeCreate` | Worktree создан |
| `WorktreeRemove` | Worktree удалён |
| `PreCompact` | Перед сжатием контекста |
| `PostCompact` | После сжатия |
| `Elicitation` | MCP запрашивает ввод |
| `ElicitationResult` | Ответ на MCP запрос |
| `SessionEnd` | Завершение сессии |

### 4 типа хуков
1. **command** — shell-скрипт
2. **http** — POST на endpoint
3. **prompt** — однократное LLM-решение
4. **agent** — многоходовая проверка с инструментами

### Практические примеры
```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Edit|Write",
      "hooks": [{ "type": "command", "command": "ruff format $CLAUDE_FILE_PATH" }]
    }],
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{ "type": "command", "command": "~/.claude/hooks/block-dangerous.sh" }]
    }],
    "Stop": [{
      "hooks": [{ "type": "command", "command": "notify-send 'Claude finished'" }]
    }]
  }
}
```

### Exit codes
- **0** — продолжить; stdout добавляется в контекст
- **2** — заблокировать действие; stderr как обратная связь
- **другие** — продолжить; stderr только в лог

---

## 8. MCP серверы — интеграции

### Настройка
**Файлы**: `~/.claude/.mcp.json` (глобально), `.claude/.mcp.json` (проект)

```json
{
  "mcpServers": {
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["@anthropic-ai/mcp-server-github"],
      "env": { "GITHUB_TOKEN": "ghp_..." }
    }
  }
}
```

### Ключевые MCP серверы (400+ в реестре)

| Категория | Серверы |
|-----------|---------|
| **Dev** | GitHub, GitLab, Bitbucket |
| **PM** | Linear, Jira, Notion |
| **Monitoring** | Sentry (ошибки + auto-fix PR) |
| **Cloud** | Cloudflare (16 серверов), AWS, GCP, Supabase |
| **Browser** | Playwright (навигация, клики, скриншоты) |
| **Design** | Figma (дизайн → код, Code Connect) |
| **DB** | PostgreSQL, SQLite, MongoDB |
| **Docs** | Context7 (актуальная документация любой библиотеки) |
| **Search** | Exa AI (семантический поиск) |
| **Communication** | Gmail, Slack |
| **Science** | bioRxiv (препринты) |

### Оптимизация: Tool Search
Динамическая загрузка только нужных инструментов: с ~72K до ~8.7K токенов (снижение 85%).

---

## 9. Субагенты и Agent Teams

### Встроенные типы субагентов

| Тип | Модель | Инструменты | Для чего |
|-----|--------|-------------|----------|
| `Explore` | Haiku | Read-only | Быстрый поиск по кодбазе |
| `Plan` | Inherit | Read-only | Исследование перед выполнением |
| `general-purpose` | Inherit | Все | Сложные многошаговые задачи |

### Кастомные субагенты
Файл `.claude/agents/agent-name.md`:
```markdown
---
name: my-agent
description: When to use this agent
model: sonnet
tools: [Read, Edit, Write, Bash, Glob]
memory: project
isolation: worktree
maxTurns: 20
---

Instructions for the agent...
```

### Ключевые параметры
- `model` — sonnet|opus|haiku|inherit
- `tools` / `disallowedTools` — allowlist/denylist инструментов
- `memory` — user|project|local (персистентная память)
- `isolation: worktree` — изолированная ветка git
- `permissionMode` — режим разрешений
- `skills` — предзагрузка навыков
- `mcpServers` — доступ к MCP серверам
- `hooks` — lifecycle хуки
- `background: true` — всегда фоновая задача

### Способы вызова
1. **Автоматически** — Claude делегирует по описанию
2. **Естественный язык** — упомянуть агента в промпте
3. **@mention** — `@agent-name` (гарантированный вызов)
4. **CLI** — `claude --agent name`
5. **Настройка** — `"agent": "name"` в settings.json

### Agent Teams (параллельные агенты)
- **review-squad**: reviewer + sec-auditor одновременно
- **build-squad**: builder + tester параллельно
- **research-squad**: explorer + verifier последовательно

Включение: `/agent-teams` или `--teammate-mode auto|in-process|tmux`

---

## 10. Skills — навыки по запросу

### Структура
Файл `~/.claude/skills/skill-name/SKILL.md` или `.claude/skills/skill-name/SKILL.md`:
```markdown
---
name: my-skill
description: When to use
---

Skill instructions...
```

### Ключевое отличие от CLAUDE.md
- **CLAUDE.md** загружается каждую сессию → держите ≤200 строк
- **Skills** загружаются только по запросу → можно больше контекста

### Примеры навыков
- Стандарты бренда, гайдлайны кода
- Чеклисты ревью, процедуры деплоя
- Аудит безопасности, TDD workflow
- Commit formatting, writing style

### Anthropic Skills Repo
github.com/anthropics/skills — 87K+ звёзд, включая `skill-creator` для создания новых навыков.

---

## 11. Memory — система памяти

### 3 уровня памяти
1. **Auto-memory** (`~/.claude/memory/`) — персональная, между разговорами
2. **Project memory** (`.claude/memory/`) — проектная, в git
3. **Subagent memory** (`.claude/agent-memory/`) — память субагентов

### Типы auto-memory
- `user` — роль, цели, предпочтения
- `feedback` — коррекции подхода (WHY + HOW TO APPLY)
- `project` — контекст текущей работы
- `reference` — указатели на внешние системы

### Project memory файлы
- `activeContext.md` — текущий фокус
- `decisions.md` — архитектурные решения (ADR)
- `patterns.md` — паттерны с тегами [REPEAT]/[AVOID]/[×N]
- `goals.md` — цели проекта/спринта

### /dream — консолидация памяти
Аналог REM-сна: консолидирует краткосрочную сессионную память в долгосрочную. Можно запускать вручную или включить auto-dream между сессиями.

---

## 12. Горячие клавиши

### Управление
| Клавиша | Действие |
|---------|----------|
| `Ctrl+C` | Отменить ввод/генерацию |
| `Ctrl+D` | Выйти из Claude Code |
| `Ctrl+L` | Очистить экран |
| `Ctrl+B` | Фоновая задача |
| `Ctrl+T` | Показать/скрыть задачи |
| `Ctrl+O` | Verbose output |
| `Ctrl+R` | Поиск по истории |
| `Ctrl+X Ctrl+K` | Убить все фоновые агенты |
| `Ctrl+X Ctrl+E` | Открыть в текстовом редакторе |
| `Esc` | Остановить Claude |
| `Esc+Esc` | Rewind к checkpoint |
| `Shift+Tab` | Переключить режим разрешений |
| `Alt+P` | Сменить модель |
| `Alt+T` | Extended thinking |
| `Alt+O` | Fast mode |
| `Ctrl+V` / `Alt+V` | Вставить изображение |

### Multiline ввод
| Метод | Клавиша |
|-------|---------|
| Escape | `\` + `Enter` |
| macOS | `Option+Enter` |
| iTerm2 | `Shift+Enter` |
| Control | `Ctrl+J` |

### Vim mode (`/vim`)
Полная поддержка: `h/j/k/l`, `w/e/b`, `dd/yy/p`, `i/a/o`, text objects (`iw`, `i"`, `i(`), `.` repeat

### Специальные префиксы
| Префикс | Функция |
|---------|---------|
| `/` | Слэш-команда или skill |
| `!` | Прямое выполнение bash |
| `@` | Автокомплит файлов и агентов |

---

## 13. Headless/CI-CD режим

```bash
claude -p "task" --permission-mode dontAsk --output-format json
```

### Возможности
- Неинтерактивное выполнение для CI/CD пайплайнов
- Форматы вывода: text, JSON, stream-json
- `--allowedTools` для ограничения инструментов
- `--max-budget-usd` для лимита расходов
- `--max-turns` для лимита итераций

### Статистика
- AI-тесты покрывают ~72% непокрытых ветвей кода
- Автоматизация lint fix сокращает время решения на ~85%
- 60%+ enterprise команд используют headless mode

---

## 14. Расписание и фоновые задачи

### 2 типа
1. **Сессионные** (`/loop`) — живут пока сессия открыта
   ```
   /loop 5m /babysit-prs
   ```
   До 50 параллельных задач, автоудаление через 3 дня.

2. **Облачные** (`/schedule`) — персистентные, выживают перезагрузки
   - Выбор репозитория, cron-расписание, промпт
   - Claude просыпается, выполняет, засыпает

### Кейсы использования
- Мониторинг деплоев
- Babysit PR'ов
- Ночные code review
- Еженедельный аудит зависимостей
- Суммаризация работы агентов за ночь

---

## 15. Git Worktree — изоляция

```bash
claude -w feature-name              # Создать worktree
claude -w feature-name --tmux       # С tmux сессией
```

### Как работает
- Каждый worktree — изолированная копия repo с отдельной веткой
- Общая git история и remotes
- Параллельные сессии без конфликтов
- Автоочистка при выходе

### Паттерны
- **Эксперименты**: несколько подходов параллельно, выбираете лучший
- **Субагенты**: `isolation: worktree` в frontmatter агента
- **`/batch`**: автоматически создаёт worktree для каждого файла

---

## 16. Скрытые и продвинутые фичи

### Extended Thinking
- `/effort max` для глубокого рассуждения (Opus 4.6)
- `Alt+T` для переключения
- "ultrathink" в контенте skill для автовключения

### /btw — побочные вопросы
- Вопрос без добавления в историю
- Использует prompt cache (дёшево)
- Без доступа к инструментам
- Идеален для быстрых уточнений

### /context — визуализация
- Цветная сетка использования токенов
- Предложения по оптимизации
- Предупреждения о раздувании памяти

### Checkpoints (Esc+Esc)
- Прокручиваемое меню всех checkpoint'ов
- Восстановление кода, разговора или обоих
- Автоматическое отслеживание изменений

### Channels (Research Preview)
- MCP серверы пушат уведомления в Claude
- Webhook-based триггеры
- `--channels plugin:name@market`

### Structured Outputs
- JSON schema валидация: `--json-schema '{...}'`
- SDK поддержка для программного использования

### Remote Control
```bash
claude remote-control "project-name"
```
- Управление CLI с claude.ai
- Relay permission промптов
- Гибрид терминал + браузер

### Computer Use (Desktop, Mac)
- Claude управляет экраном Mac
- Клики, ввод текста, навигация
- Research preview (март 2026)

### Voice Mode
- Hold Space — push-to-talk
- 20 языков
- Настраивается через `/keybindings`

---

## 17. Лайфхаки для power users

### HANDOFF.md паттерн
Перед `/clear` создайте HANDOFF.md с прогрессом, решениями, следующими шагами.
Новую сессию начните: "Read HANDOFF.md and continue."

### Compaction survival
```markdown
## Compact Instructions
When summarizing, preserve: modified files list, test status, architectural decisions.
```

### Терминальные alias'ы
```bash
alias c='claude'
alias ch='claude --chrome'
alias cw='claude -w'
```

### Environment variables
```bash
MAX_THINKING_TOKENS=8000           # Cap thinking budget
CLAUDE_CODE_DISABLE_1M_CONTEXT     # Отключить расширенный контекст
CLAUDE_CODE_SKIP_PRECOMPACT_LOAD   # Оптимизация загрузки больших сессий
CLAUDE_CODE_TASK_LIST_ID           # Общий список задач между сессиями
```

### Конкурирующие гипотезы
Запустите несколько агентов с разными подходами к одной проблеме → выберите лучший результат.

### Контейнерная изоляция
Рискованные/экспериментальные задачи → Docker контейнер для защиты системы.

### Голосовой ввод
SuperWhisper / MacWhisper для быстрого промптинга голосом (быстрее набора).

### Custom Status Line
```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/hooks/status.sh"
  }
}
```
Показывает модель, git branch, токены, стоимость в footer терминала.

---

## 18. Оптимизация контекста

### Зоны контекста
| Использование | Действие |
|--------------|----------|
| 0-50% | Работайте свободно |
| 50-70% | Внимание |
| 70-90% | `/compact` обязательно |
| 90%+ | `/clear` обязательно |

### Сокращение расхода токенов
- `/effort low` для простых задач
- `MAX_THINKING_TOKENS=8000` для рутины
- Делегируйте verbose операции (тесты, логи) субагентам — в основной контекст вернётся только summary
- Конкретные промпты > расплывчатые (экономия на уточнениях)
- Skills загружаются по запросу, CLAUDE.md — каждую сессию. Переносите справочные материалы в skills.

### Гигиена сессий
- `/clear` при смене темы
- `/compact focus on X` при продолжении с тяжёлым контекстом
- Новый разговор для каждой отдельной темы

---

## 19. Интеграционные workflow

### Issue → PR (Linear + GitHub)
1. Linear MCP: Claude видит issue
2. Анализирует кодбазу
3. Реализует решение
4. GitHub MCP: открывает PR с документацией
5. Linear MCP: обновляет статус

### Sentry → Auto-fix
1. Sentry MCP: получает контекст ошибки
2. Claude находит источник
3. Предлагает fix
4. Linear: создаёт баг-тикет
5. GitHub: открывает PR с исправлением

### Figma → Code
1. `get_design_context` с nodeId и fileKey
2. Получает код + скриншот + hints
3. Адаптирует под стек проекта
4. Code Connect для маппинга компонентов

### Context7 — актуальные доки
Для любой библиотеки/фреймворка: React, Next.js, Django, FastAPI — актуальная документация вместо устаревших знаний из обучения.

---

## 20. Agent SDK

**Переименование**: Claude Code SDK → **Claude Agent SDK**

### Версии (март 2026)
- Python: `claude-agent-sdk` v0.1.48 (PyPI)
- TypeScript: `@anthropic-ai/claude-agent-sdk` v0.2.71 (npm)

### 4 core концепции
1. **Tools** — Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, Agent...
2. **Hooks** — 18+ lifecycle событий
3. **MCP Servers** — внешние инструменты
4. **Subagents** — дочерние агенты

### Философия
"Give your agents a computer" — агенты работают как люди, используя те же инструменты что и Claude Code.

---

## 21. Хронология релизов

| Период | Ключевые события |
|--------|-----------------|
| **Feb 2025** | Запуск Claude Code (бета) |
| **May 2025** | GA вместе с Claude 4 |
| **Aug 2025** | Chrome extension |
| **Sep 2025** | VS Code extension (бета) |
| **Dec 2025** | Desktop App (v2.0.51) |
| **Jan 2026** | Включение в Team план |
| **Mar 2026** | Computer Use preview, Voice Mode, 74 фичи за месяц |

### Метрики роста
- Использование выросло на **300%** с запуска Claude 4
- Revenue run-rate вырос в **5.5x**
- MCP SDK: **97M** загрузок/месяц (с 2M в ноябре 2025)
- **176** обновлений за 2025 год

---

## Максимальная свобода для Claude Code — чеклист

Чтобы дать Claude Code максимальную свободу для достижения целей:

1. **Permission mode**: `auto` — минимум промптов, фоновый классификатор безопасности
2. **Extended thinking**: `/effort max` для сложных задач
3. **Agent Teams**: `--teammate-mode auto` для параллельной работы
4. **Worktrees**: `-w` для изолированных экспериментов
5. **MCP серверы**: подключить GitHub, Linear, Sentry, Context7, Figma
6. **Hooks**: автоформат, автотест, уведомления
7. **Skills**: вынести справочные материалы из CLAUDE.md
8. **Memory**: настроить auto-memory + project memory
9. **CLAUDE.md**: лаконичный (≤200 строк), модульный (rules/)
10. **Scheduled tasks**: `/schedule` для регулярных проверок
11. **`/batch`**: массовые изменения параллельно
12. **`--max-budget-usd`**: контроль расходов при автономной работе
