# Claude Code Config v11.1

Боевая конфигурация Claude Code: Evidence Policy, 9 hooks, 9 skills, 13 agents, MCP-профили, PII redaction.
Проверена на реальных проектах: фрод-детекция, геномный анализ, спутниковая геологоразведка, финансовые платформы.

## Quick Start — 5 минут до рабочей конфигурации

### Шаг 1: Клонирование
```bash
git clone https://github.com/sergeeey/Claude-cod-top-2026.git
cd Claude-cod-top-2026
```

### Шаг 2: Установка
```bash
# Вариант A: Копирование (стабильно, обновление вручную)
bash install.sh

# Вариант B: Symlinks (авто-обновление через git pull)
bash install.sh --link
```

**`--link` mode**: создаёт символические ссылки вместо копий. Конфиг обновляется одной командой `git pull` в этом репо. SessionStart hook автоматически делает `git pull --ff-only` при старте сессии.
Установщик предложит выбрать профиль:

| Профиль | Что устанавливает | Для кого |
|---------|-------------------|----------|
| **minimal** | CLAUDE.md + integrity.md + security.md | Попробовать Evidence Policy |
| **standard** | + все rules + hooks + skills + agents | Ежедневная работа |
| **full** | + MCP-профили + PII redaction + memory | Полный контроль |

Если у тебя уже есть конфигурация — установщик спросит: заменить (с бэкапом), объединить, или пропустить каждый файл. **Ничего не перезаписывается без подтверждения.**

### Шаг 3: Проверка
```bash
claude
# В Claude Code:
/context
```
Должно показать: CLAUDE.md загружен, rules доступны, skills обнаружены.

**Готово.** Дальше можно адаптировать `~/.claude/CLAUDE.md` (секция IDENTITY) под себя.

---

## Оглавление

- [Принципы](#принципы)
- [Что внутри](#что-внутри)
- [Архитектура](#архитектура)
- [Evidence Policy](#evidence-policy)
- [Hooks](#hooks)
- [Skills](#skills)
- [Agents](#agents)
- [MCP Profiles](#mcp-profiles)
- [Сравнение с экосистемой](#сравнение-с-экосистемой)
- [Документация](#документация)
- [Структура файлов](#структура-файлов)

---

## Принципы

1. **Минимализм контекста** — CLAUDE.md < 80 строк. Всё остальное в rules/skills (загружается по запросу)
2. **Модульность** — rules, skills, hooks, agents — независимые компоненты
3. **Доказательность** — Evidence Policy: каждый факт маркируется уровнем уверенности
4. **Детерминизм** — Hooks исполняются 100% времени (в отличие от инструкций в промпте)

## Что внутри

| Компонент | Кол-во | Описание |
|-----------|--------|----------|
| [CLAUDE.md](claude-md/CLAUDE.md) | 70 строк | Ядро конфигурации (грузится всегда) |
| [Rules](rules/) | 5 файлов | Модульные правила (грузятся по контексту) |
| [Hooks](hooks/) | 9 скриптов | Детерминированная автоматизация |
| [Skills](skills/) | 9 навыков | Domain knowledge (Progressive Disclosure) |
| [Agents](agents/) | 13 агентов | Специализированные субагенты |
| [Scripts](scripts/) | 2 файла | PII redaction + тесты |
| [MCP Profiles](mcp-profiles/) | 3 профиля | Переключение наборов MCP серверов |
| [Memory](memory/) | шаблоны | Структура памяти между сессиями |

## Архитектура

```
                    ┌─────────────────────────┐
                    │  CLAUDE.md (70 строк)   │  ← Грузится ВСЕГДА
                    │  Identity, Workflow,     │     ~500 токенов/сообщение
                    │  Evidence Policy         │
                    └──────────┬──────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │   Rules (5)  │  │  Skills (9)  │  │  Agents (13) │
    │ По контексту │  │  По триггеру │  │  По вызову   │
    └──────────────┘  └──────────────┘  └──────────────┘
              │                                 │
              ▼                                 ▼
    ┌──────────────┐                   ┌──────────────┐
    │  Hooks (9)   │                   │ MCP Profiles │
    │ 100% execution│                  │  core/sci/dep│
    └──────────────┘                   └──────────────┘
```

**Красная зона** (грузится всегда): CLAUDE.md — поэтому он максимально сжат.
**Зелёная зона** (по запросу): rules, skills, agents — 0 токенов пока не нужны.
**Бесплатная зона**: hooks, scripts — не потребляют токены вообще.

Подробнее: [docs/architecture.md](docs/architecture.md)

## Evidence Policy

Ключевое отличие от других конфигураций. Каждое фактическое утверждение Claude маркируется:

| Маркер | Значение | Пример |
|--------|----------|--------|
| `[VERIFIED]` | Проверено инструментом | pytest output, Read, Bash |
| `[DOCS]` | Из документации | Официальные docs |
| `[CODE]` | Из исходного кода | Прочитанный файл |
| `[INFERRED]` | Логический вывод | Из verified-фактов |
| `[WEAK]` | Косвенные данные | Аналогия, 1 источник |
| `[CONFLICTING]` | Противоречие | 2+ источника расходятся |
| `[UNKNOWN]` | Не проверено | Требуется проверка |

**Главное правило**: `[UNKNOWN]` всегда лучше, чем ложный `[INFERRED]`.

Подробнее: [docs/evidence-policy.md](docs/evidence-policy.md)

## Hooks

9 hooks обеспечивают детерминированную автоматизацию:

| Hook | Событие | Что делает |
|------|---------|------------|
| `session_start.py` | SessionStart | Загружает activeContext.md проекта |
| `pre_compact.py` | PreCompact | Сохраняет контекст перед сжатием |
| `pre_commit_guard.py` | PreToolUse(Bash) | Блокирует опасные команды |
| `post_format.py` | PostToolUse(Edit/Write) | Автоформатирование |
| `plan_mode_guard.py` | PostToolUse(Edit/Write) | Защита Plan Mode |
| `memory_guard.py` | PostToolUse(Bash) | Напоминание обновить память |
| `checkpoint_guard.py` | PostToolUse(Bash) | Напоминание о checkpoint |
| `post_commit_memory.py` | PostToolUse(Bash) | Обновление памяти после коммита |
| `session_save.py` | Stop | Сохранение состояния при выходе |

Подробнее: [docs/hooks-guide.md](docs/hooks-guide.md)

## Skills

9 навыков с YAML frontmatter и lifecycle-маркировкой:

| Skill | Домен | Триггеры |
|-------|-------|----------|
| **tdd-workflow** | TDD | тесты, TDD, test-driven, coverage |
| archcode-genomics | Геномика | ClinVar, chromatin, variant |
| brainstorming | Дизайн | давай подумаем, brainstorm |
| geoscan | Геологоразведка | Sentinel, spectral, gold |
| git-worktrees | Git | worktree, эксперимент |
| mentor-mode | Обучение | объясни, научи, как работает |
| notebooklm | Документы | NotebookLM, query docs |
| security-audit | Безопасность | аудит, ARRFR, fraud, IIN |
| suno-music | Музыка | Suno, BPM, трек |

Подробнее: [docs/skills-guide.md](docs/skills-guide.md)

## Agents

5 core агентов загружаются по умолчанию, 8 extended — доступны для явного вызова.

**Core (ежедневная работа):**

| Агент | Модель | Роль |
|-------|--------|------|
| **navigator** | Opus | Архитектура, планирование, старт сессии |
| **builder** | Sonnet | Генерация кода по спецификации |
| **reviewer** | Opus | Code review, поиск багов |
| **tester** | Sonnet | Генерация и запуск тестов |
| **explorer** | Sonnet | Исследование кодовой базы |

<details>
<summary><b>Extended (8 агентов для специализированных задач)</b></summary>

| Агент | Модель | Роль |
|-------|--------|------|
| architect | Opus | Проектирование архитектуры |
| verifier | Opus | Проверка утверждений на галлюцинации |
| security-guard | Opus | Security audit финансового кода |
| sec-auditor | Sonnet | PII защита, SQL injection detection |
| scope-guard | Sonnet | Защита MVP от scope creep |
| teacher | Opus | Объяснение технических концепций |
| fe-mentor | Sonnet | Frontend архитектура (React/TS) |
| skill-suggester | Sonnet | Анализ knowledge gaps |

</details>

## MCP Profiles

3 профиля для управления токен-бюджетом (~1000-2000 токенов/сервер):

| Профиль | Серверы | Когда |
|---------|---------|-------|
| **core** | context7, basic-memory, sequential-thinking, playwright, ollama | По умолчанию |
| **science** | core + ncbi, uniprot, pubmed | Геномика, биоинформатика |
| **deploy** | core + vercel, netlify, supabase, sentry | Деплой, CI/CD |

```powershell
# Переключение
~/.claude/mcp-profiles/switch-profile.ps1 science
# После переключения — перезапустить Claude Code!
```

Подробнее: [docs/mcp-profiles.md](docs/mcp-profiles.md)

## Сравнение с экосистемой

| Критерий | Наш v11.0 | superpowers (79k★) | everything-claude-code (35k★) |
|----------|:---------:|:------------------:|:----------------------------:|
| Evidence Policy | **9/10** | 6/10 | 3/10 |
| Workflow discipline | 6/10 | **9/10** | 7/10 |
| Security & PII | **9/10** | 1/10 | 5/10 |
| Hooks automation | **9/10** | 3/10 | 7/10 |
| Memory system | **8/10** | 4/10 | 6/10 |
| Domain skills | **9/10** | 2/10 | 4/10 |
| TDD enforcement | **9/10** | **9/10** | 5/10 |
| Multi-platform | 3/10 | **9/10** | 6/10 |

## Документация

| Документ | Описание |
|----------|----------|
| [docs/architecture.md](docs/architecture.md) | 6 слоёв конфигурации, Progressive Disclosure |
| [docs/evidence-policy.md](docs/evidence-policy.md) | Evidence Policy — защита от галлюцинаций |
| [docs/hooks-guide.md](docs/hooks-guide.md) | Все 9 hooks с примерами |
| [docs/skills-guide.md](docs/skills-guide.md) | Создание skills, lifecycle, CSO |
| [docs/mcp-profiles.md](docs/mcp-profiles.md) | MCP-профили и переключение |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 10-пунктный чеклист + 8 типичных проблем |
| [docs/anti-patterns.md](docs/anti-patterns.md) | 8 критических ошибок и как конфигурация от них защищает |

## Структура файлов

```
Claude-cod-top-2026/
├── README.md                  # Этот файл
├── LICENSE                    # MIT
├── install.sh                 # Интерактивный установщик
├── claude-md/
│   └── CLAUDE.md              # Ядро конфигурации (70 строк)
├── rules/                     # Модульные правила
│   ├── coding-style.md        # Стандарты кода (20 строк)
│   ├── security.md            # Безопасность, PII (17 строк)
│   ├── testing.md             # Тесты, coverage (11 строк)
│   ├── integrity.md           # Anti-hallucination (32 строки)
│   └── memory-protocol.md     # Память, checkpoints (32 строки)
├── hooks/                     # Скрипты автоматизации
│   ├── settings.json          # Конфигурация hooks + permissions (17 deny-patterns)
│   └── *.py                   # 9 hook-скриптов (799 строк)
├── scripts/
│   ├── redact.py              # PII redaction (76 строк)
│   └── test_redact.py         # Тесты redaction
├── skills/                    # 9 навыков
│   ├── tdd-workflow/          # TDD: RED → GREEN → REFACTOR
│   ├── brainstorming/         # Socratic Design
│   ├── security-audit/        # ARRFR compliance
│   └── ...                    # + 6 domain skills
├── agents/                    # 13 агентов
│   └── *.md                   # navigator, builder, reviewer, tester, ...
├── mcp-profiles/              # 3 MCP профиля
│   ├── core.json
│   ├── science.json
│   ├── deploy.json
│   └── switch-profile.ps1
├── memory/
│   └── templates/             # Шаблоны памяти
└── docs/                      # 7 документов на русском
    ├── architecture.md
    ├── evidence-policy.md
    ├── hooks-guide.md
    ├── skills-guide.md
    ├── mcp-profiles.md
    ├── troubleshooting.md
    └── anti-patterns.md
```

## Лицензия

MIT. Используй, адаптируй, расширяй.
