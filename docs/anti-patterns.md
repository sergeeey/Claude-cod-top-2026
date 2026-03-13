# Anti-Patterns: 8 критических ошибок при работе с Claude Code

Каждый anti-pattern содержит: проблему, пример плохого и хорошего workflow,
и ссылку на элемент нашей конфигурации, который защищает от этой ошибки.

---

## 1. Context Overflow — Переполнение контекста

**Проблема**: длинная сессия без `/clear` — Claude начинает «забывать» ранние
инструкции, путается, повторяет ошибки.

**Плохо**:
```
50 сообщений подряд без очистки.
К концу Claude не помнит что мы используем PostgreSQL и предлагает MySQL.
Инструкции из CLAUDE.md вытеснены из «окна внимания».
```

**Хорошо**:
```
/clear после каждой завершённой задачи.
/compact с фокусом на 50% заполнения.
Важные решения записаны в memory-файлах, не только в чате.
```

**Наше решение**:
- `rules/memory-protocol.md` — правила `/clear` дисциплины и context overflow на 70%
- Per-project `activeContext.md` — критичный контекст хранится вне сессии
- `hooks/pre_compact.py` — автосохранение контекста перед сжатием
- CLAUDE.md ограничен 70 строками — максимум свободного контекста для работы

---

## 2. Hallucination Loops — Циклы галлюцинаций

**Проблема**: Claude выдумывает несуществующие API/методы и зацикливается
на попытках их вызвать.

**Плохо**:
```
Claude пробует user.getAuthToken(), user.fetchAuthToken(),
user.retrieveToken() — ни одного не существует.
5 попыток подряд, каждая с новым выдуманным методом.
```

**Хорошо**:
```
"Read the User class and list all available methods.
Do NOT write code until you've confirmed the API."
→ Claude находит user.authenticate() → пишет рабочий код.
```

**Наше решение**:
- **Evidence Policy** — маркер `[VERIFIED]` обязывает проверить факт инструментом (Read/Grep)
- **Stuck Detection** — 3 неудачных попытки → СТОП, доложить что пробовал
- **Plan-First** — Explore → Design → Plan → Code (исследование перед кодированием)
- `rules/integrity.md` — 4 жёстких запрета (NO FABRICATION, NO PHANTOM REFERENCES...)

---

## 3. Vague Prompts — Размытые промпты

**Проблема**: нечёткий запрос → Claude интерпретирует по-своему → результат не тот.

**Плохо**:
```
"fix the tests"
→ Claude чинит не тот тест, или «чинит» подгоняя expected values.
```

**Хорошо**:
```
"Fix the failing test in auth.spec.ts line 45.
The mock returns undefined instead of a user object.
Expected: { id: 1, role: 'admin' }."
→ Claude чинит конкретную проблему за 1 итерацию.
```

**Наше решение**:
- **80/20 правило** — Claude фокусируется на конкретном, измеримом результате
- `skills/brainstorming/` — Socratic Design с уточняющими вопросами перед реализацией
- **Autonomy + Plan-First** — при неясности Claude спрашивает, а не гадает

---

## 4. Trusting Without Verification — Доверие без проверки

**Проблема**: принимаешь код Claude без проверки → накапливаются баги.

**Плохо**:
```
"implement the payment flow" → "Done!" → commit → production breaks.
Код ни разу не запускался, тесты не написаны.
```

```
8 шагов плана → BUILD SUCCESSFUL → "Волна 1: 100%, Волна 2: 100%".
На устройстве ни один экран не открывался, ни один API не вызывался.
BUILD SUCCESSFUL проверяет типы, не runtime.
```

**Хорошо**:
```
implement → write tests → run tests → subagent review → commit.
Каждый шаг верифицирован, каждый факт промаркирован.
```

```
8 шагов: implemented. BUILD SUCCESSFUL [VERIFIED compile].
PeopleScreen: [UNKNOWN] не проверен на устройстве.
MirrorScreen: [UNKNOWN] ни один из 4 API не тестирован.
Общий прогресс: implemented 100%, verified 0%.
```

**Наше решение**:
- **Evidence Policy** — культура проверки: каждый факт промаркирован уровнем доказательности
- **Progress Honesty** — implemented ≠ tested ≠ verified; "done" = verified
- `agents/reviewer.md` (Opus 4.6) — code review перед коммитом
- `skills/tdd-workflow/` — формализованный TDD-процесс (RED → GREEN → REFACTOR)
- `hooks/pre_commit_guard.py` — блокировка опасных команд
- `rules/testing.md` — запрет удалять/подгонять тесты

---

## 5. Monolithic CLAUDE.md — Монолитная конфигурация

**Проблема**: все инструкции в одном файле на 300+ строк → Claude игнорирует
правила, «утонувшие» в середине файла.

**Плохо**:
```
CLAUDE.md на 515 строк: changelog, матрица агентов, style guide,
история проектов, security checklist, MCP конфигурация.
→ К 40-му сообщению Claude перестаёт следовать Evidence Policy
  (она была на строке 287).
```

**Хорошо**:
```
CLAUDE.md на 70 строк — только ядро.
5 rules-файлов — загружаются по контексту задачи.
8 skills — Progressive Disclosure, грузятся по триггеру.
→ Evidence Policy в верхней трети CLAUDE.md, всегда в фокусе.
```

**Наше решение**:
- CLAUDE.md: 70 строк (ядро) — Identity, Workflow, Evidence Policy, указатели на rules
- `rules/` (5 файлов, 112 строк суммарно) — загружаются когда нужны, 0 токенов иначе
- `skills/` (8 навыков) — Progressive Disclosure, ~100 токенов на все при старте
- **Результат**: 70 строк вместо 515, -86% при сохранении функциональности

**Цифры**:
| Подход | Строк в CLAUDE.md | Токенов/сообщение | Внимание модели |
|--------|-------------------|-------------------|-----------------|
| Монолитный | 515 | ~3500 | Размытое |
| Наш модульный | 70 | ~500 | Сфокусированное |

---

## 6. MCP Overload — Перегрузка серверами

**Проблема**: 16 MCP-серверов подключены одновременно → ~20 000 токенов tool
definitions → медленный tool selection, ранний compaction.

**Плохо**:
```
Подключены: Figma, Linear, Netlify, Vercel, Sentry, Supabase,
4 научных, 3 Context7 варианта.
→ 20 000 токенов мёртвого груза на каждое сообщение.
→ Compaction наступает на 30% быстрее.
```

**Хорошо**:
```
CORE-профиль: 5 серверов для 80% задач.
Переключение на SCIENCE или DEPLOY по необходимости.
→ ~5000 токенов tool definitions, экономия 75%.
```

**Наше решение**:
- `mcp-profiles/core.json` — 5 серверов (context7, basic-memory, sequential-thinking, playwright, ollama)
- `mcp-profiles/science.json` — core + ncbi, uniprot, pubmed
- `mcp-profiles/deploy.json` — core + vercel, netlify, supabase, sentry
- `mcp-profiles/switch-profile.ps1` — переключение одной командой
- `settings.local.json` — 11 серверов явно отключены

---

## 7. PII Leakage — Утечка персональных данных

**Проблема**: чувствительные данные (ИИН, API-ключи, номера карт) попадают
в контекст LLM при работе с финансовыми документами.

**Плохо**:
```
Claude читает файл с ИИН клиентов.
Вызывает Ollama для анализа — ИИН уходит во внешний процесс.
Данные оседают в логах, кеше, контексте.
```

**Хорошо**:
```
Redaction hook перехватывает вызов к MCP-серверу.
ИИН заменён на [REDACTED:IIN] до отправки.
В контексте внешнего сервера — только маскированные данные.
```

**Наше решение**:
- `scripts/redact.py` — PreToolUse hook с паттернами для ИИН, email, телефонов, API-ключей
- Исключения: ClinVar ID, dbSNP, геномные координаты, git SHA (не трогаем легитимные данные)
- `rules/security.md` — PII Policy, приоритет локальному инференсу (Ollama)
- `hooks/settings.json` — deny-list из 17 паттернов: блокировка чтения .env, .ssh, .aws
- Matcher: `mcp__ollama|mcp__ncbi|mcp__uniprot|mcp__pubmed` — только внешние серверы

---

## 8. Dead Skills — Мёртвые навыки

**Проблема**: skills создаются, но не проверяются на актуальность → устаревшие
инструкции → Claude даёт неверные рекомендации.

**Плохо**:
```
Skill описывает API v2, проект уже на v3.
Claude генерирует код для несуществующих endpoints.
Skill не обновлялся 4 месяца, никто не заметил.
```

**Хорошо**:
```
Каждый skill имеет STATUS, CONFIDENCE, VALIDATED в frontmatter.
Еженедельный ревью: обновить VALIDATED у актуальных.
Не использовался 60+ дней → статус review.
```

**Наше решение**:
- YAML frontmatter с lifecycle: `[STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-12]`
- Жизненный цикл: draft → confirmed → review → deprecated
- Правило: skill без обновления 60+ дней → статус `review`
- CSO (Claude Search Optimization): description = триггеры, НЕ summary workflow

---

## Маппинг: Anti-Pattern → Защитный элемент

| # | Anti-Pattern | Элемент конфигурации |
|---|-------------|---------------------|
| 1 | Context Overflow | memory-protocol.md, pre_compact.py, activeContext.md |
| 2 | Hallucination Loops | Evidence Policy, Stuck Detection, integrity.md |
| 3 | Vague Prompts | 80/20, brainstorming skill |
| 4 | Trusting Without Verification | Evidence Policy, reviewer agent, tdd-workflow skill |
| 5 | Monolithic CLAUDE.md | Модульная архитектура: 70 строк + rules + skills |
| 6 | MCP Overload | MCP-профили (core/science/deploy) |
| 7 | PII Leakage | redact.py, security.md, deny-list |
| 8 | Dead Skills | Skill Lifecycle (STATUS/CONFIDENCE/VALIDATED) |
