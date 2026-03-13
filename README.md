# Claude Code Config v11.0

Боевая конфигурация Claude Code, прошедшая проверку на реальных проектах:
AI-системы для фрод-детекции, геномный анализ (30 000+ вариантов), спутниковая геологоразведка, мультиагентные финансовые платформы.

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
| [Skills](skills/) | 8 навыков | Domain knowledge (Progressive Disclosure) |
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
    │   Rules (5)  │  │  Skills (8)  │  │  Agents (13) │
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

## Быстрый старт

### Вариант 1: Полная установка
```bash
git clone <this-repo> ~/claude-code-config
cd ~/claude-code-config
bash install.sh full
```

### Вариант 2: Минимальная установка
```bash
bash install.sh minimal
# Устанавливает: CLAUDE.md + rules + hooks (security)
```

### Вариант 3: Ручная установка
```bash
# Скопировать нужные файлы в ~/.claude/
cp claude-md/CLAUDE.md ~/.claude/CLAUDE.md
cp -r rules/ ~/.claude/rules/
cp hooks/settings.json ~/.claude/settings.json
cp -r hooks/*.py ~/.claude/hooks/
```

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

8 навыков с YAML frontmatter и lifecycle-маркировкой:

| Skill | Домен | Триггеры |
|-------|-------|----------|
| archcode-genomics | Геномика | ClinVar, chromatin, variant |
| brainstorming | Дизайн | давай подумаем, brainstorm |
| geoscan | Геологоразведка | Sentinel, spectral, gold |
| git-worktrees | Git | worktree, эксперимент |
| mentor-mode | Обучение | объясни, научи, как работает |
| notebooklm | Документы | NotebookLM, query docs |
| security-audit | Безопасность | аудит, ARRFR, fraud, IIN |
| suno-music | Музыка | Suno, BPM, трек |

Подробнее: [docs/skills-guide.md](docs/skills-guide.md)

## MCP Profiles

3 профиля для управления токен-бюджетом:

| Профиль | Серверы | Когда |
|---------|---------|-------|
| **core** | context7, basic-memory, sequential-thinking, playwright, ollama | По умолчанию |
| **science** | core + ncbi, uniprot, pubmed | Геномика, биоинформатика |
| **deploy** | core + vercel, netlify, supabase, sentry | Деплой, CI/CD |

```powershell
# Переключение
~/.claude/mcp-profiles/switch-profile.ps1 science
```

## Сравнение с экосистемой

| Критерий | Наш v11.0 | superpowers (79k★) | everything-claude-code (35k★) |
|----------|:---------:|:------------------:|:----------------------------:|
| Evidence Policy | **9/10** | 6/10 | 3/10 |
| Workflow discipline | 6/10 | **9/10** | 7/10 |
| Security & PII | **9/10** | 1/10 | 5/10 |
| Hooks | **9/10** | 3/10 | 7/10 |
| Memory system | **8/10** | 4/10 | 6/10 |
| Domain skills | **9/10** | 2/10 | 4/10 |
| Multi-platform | 3/10 | **9/10** | 6/10 |

## Структура файлов

```
claude-code-config/
├── README.md                  # Этот файл
├── LICENSE                    # MIT
├── install.sh                 # Установщик
├── claude-md/
│   └── CLAUDE.md              # Ядро конфигурации (70 строк)
├── rules/                     # Модульные правила
│   ├── coding-style.md        # Стандарты кода (20 строк)
│   ├── security.md            # Безопасность, PII (17 строк)
│   ├── testing.md             # Тесты, coverage (11 строк)
│   ├── integrity.md           # Anti-hallucination (32 строки)
│   └── memory-protocol.md     # Память, checkpoints (32 строки)
├── hooks/                     # Скрипты автоматизации
│   ├── settings.json          # Конфигурация hooks + permissions
│   └── *.py                   # 9 hook-скриптов (799 строк)
├── scripts/
│   ├── redact.py              # PII redaction (76 строк)
│   └── test_redact.py         # Тесты redaction
├── skills/                    # 8 навыков
│   └── <name>/SKILL.md        # С YAML frontmatter
├── agents/                    # 13 агентов
│   └── *.md                   # Определения субагентов
├── mcp-profiles/              # 3 MCP профиля
│   ├── core.json
│   ├── science.json
│   ├── deploy.json
│   └── switch-profile.ps1
├── memory/
│   └── templates/             # Шаблоны памяти
├── docs/                      # Документация
└── examples/                  # Примеры сессий
```

## Лицензия

MIT. Используй, адаптируй, расширяй.
