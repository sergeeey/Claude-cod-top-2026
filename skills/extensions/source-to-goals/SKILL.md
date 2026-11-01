---
name: source-to-goals
sub_type: guide
version: "1.0"
last_tested: "2026-05-30"
description: "Извлекает /goal условия из источника (текст, файл, PR, spec, задача). Конвертирует claims 'должно достичь X' в готовые /goal команды по шаблону ниже. Сохраняет пачку в .distill/goal_pack.md. Triggers: /source-to-goals, make goals from, convert to goals, извлеки цели, сделай /goal из."
allowed-tools: Read, Grep, Bash(git log:*), Bash(cat:*)
triggers: ["/source-to-goals", "make goals from", "convert to goals", "извлеки цели", "сделай /goal из"]
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : source-to-goals
TL;DR  : Текст/файл/задача → набор готовых /goal команд с Turn Budget и Anti-cheating
Вызов  : /source-to-goals, make goals from, convert to goals, извлеки цели, сделай /goal из
НЕ для : Ambiguous outcomes без verifiable exit condition; интерактивных скилов (диалоговых, brainstorming и т.п.)
-->

# source-to-goals — Конвертер источника в /goal пачку

Читай источник. Найди claims. Преобрази в /goal команды по шаблону ниже.

---

## Шаблон /goal

```
/goal <END STATE>. Run <КОМАНДА> and show full output. Output must contain: <СТРОКА>. Do NOT <CONSTRAINT>. or stop after <N> turns.
```

**Обязательные компоненты:**
- **END STATE** — проверяемое финальное состояние (не процесс, а результат)
- **КОМАНДА** — команда которую evaluator запустит для проверки
- **СТРОКА** — точная строка в output подтверждающая успех
- **CONSTRAINT** — что нельзя делать (anti-cheating guard)
- **N turns** — Turn Budget (ориентиры: lint/typecheck=10, TDD=25, coverage=30, CI=70)

---

## Алгоритм (5 шагов)

### Шаг 1 — Прочитай источник
Источник может быть: текст в чате, путь к файлу, URL, git commit, PR description, spec, задача.
- Если путь к файлу → `Read(file_path)`
- Если git → `Bash(git log --oneline -20)` или `Bash(git show HEAD)`
- Если URL → читай через WebFetch

### Шаг 2 — Извлеки "should achieve" claims

Паттерны для поиска (любой язык):
- "должно/должен/должна X"
- "нужно чтобы X"
- "цель: X", "goal: X", "objective: X"
- "acceptance criteria: X", "definition of done: X"
- "тесты должны проходить", "coverage >= N%"
- "CI green", "0 failures", "no errors"
- "X is done when Y"
- глаголы: достичь, обеспечить, реализовать, исправить, добавить, покрыть

### Шаг 3 — Фильтр: проверяемость

**Конвертировать** (есть verifiable exit condition):
- "pytest 0 failures" → проверяется командой
- "coverage >= 80%" → проверяется `coverage report`
- "PR создан и CI green" → проверяется `gh pr view`
- "ruff 0 errors" → проверяется `ruff check .`
- "файл X содержит Y" → проверяется `grep`

**НЕ конвертировать** (ambiguous outcome — anti-pattern):
- "код должен быть чистым" — нет команды проверки
- "пользователь доволен" — нет метрики
- "архитектура правильная" — нет exit condition
- "сделать лучше" — нет baseline

Для ambiguous claims → пометь `[SKIPPED: ambiguous — нет verifiable exit condition]`

### Шаг 4 — Заполни /goal шаблон

Для каждого валидного claim:

1. **END STATE** — сформулируй как факт который либо true, либо false
2. **КОМАНДА** — выбери из таблицы:

| Тип задачи | Команда |
|---|---|
| Python тесты | `python -m pytest tests/ -q --tb=short` |
| Coverage | `python -m pytest --cov=. --cov-report=term-missing -q` |
| Lint | `python -m ruff check .` |
| Type check | `python -m mypy . --ignore-missing-imports` |
| PR создан | `gh pr view --json state,title` |
| CI статус | `gh run list --limit 3` |
| Файл существует | `ls -la <path>` |
| Grep проверка | `grep -r "<pattern>" <path>` |

3. **СТРОКА** — точная строка из ожидаемого output (копируй реальный output если знаешь)
4. **CONSTRAINT** — стандартные anti-cheating guards:
   - `Do NOT modify files in tests/`
   - `Do NOT weaken test assertions`
   - `Do NOT add noqa/type:ignore without justification`
   - `Do NOT delete failing tests`
5. **N turns** — выбери по ориентиру из списка выше

### Шаг 5 — Сохрани в .distill/goal_pack.md

```bash
mkdir -p .distill
# Создай или обнови .distill/goal_pack.md
```

Формат goal_pack.md:
```markdown
# Goal Pack — <источник> (<дата>)

## Source
<краткое описание источника>

## Goals (N total, M skipped)

### G1: <название>
```
/goal <полный /goal текст>
```
**Source claim:** "<оригинальная фраза из источника>"
**Turn budget:** N turns
**Rationale:** <почему именно этот END STATE>

### [SKIPPED] <название>
**Reason:** ambiguous — нет verifiable exit condition
**Original:** "<оригинальная фраза>"
```

---

## Правила вывода

- **Минимум 2, максимум 5 /goal** из одного источника
- Если источник даёт >5 валидных claims → выбери топ-5 по приоритету (критичность × проверяемость)
- Если источник даёт <2 валидных claims → скажи прямо: "источник не содержит verifiable exit conditions"
- Каждый /goal на отдельной строке, в code block
- После списка — краткое объяснение что пропущено и почему

---

## Anti-patterns (не делать)

| Anti-pattern | Почему плохо |
|---|---|
| /goal для "сделать код лучше" | Нет END STATE — нельзя проверить |
| Turn budget не указан | Неограниченный расход токенов |
| CONSTRAINT отсутствует | Модель может "срезать угол" (удалить тесты) |
| СТРОКА слишком общая ("passed") | Evaluator не подтвердит — нужна точная строка |
| /goal для интерактивного скила | /goal не работает с интерактивными скилами (диалоговые, brainstorming и т.п.) |
| Один /goal на весь проект | Слишком широко — разбить на 2-5 конкретных |

---

## Пример

**Источник:** "Нужно чтобы все тесты проходили, coverage был ≥80%, и ruff не ругался"

**Output:**

```
/goal Все тесты passing, 0 failures. Run python -m pytest tests/ -q --tb=short and show full output. Output must contain: passed. Do NOT modify files in tests/, Do NOT delete failing tests. or stop after 25 turns.
```

```
/goal Coverage ≥80% по всей кодовой базе. Run python -m pytest --cov=. --cov-report=term-missing -q and show full output. Output must contain: TOTAL. Do NOT add noqa without justification, Do NOT exclude modules from coverage without explanation. or stop after 30 turns.
```

```
/goal Ruff 0 errors. Run python -m ruff check . and show full output. Output must contain: All checks passed. Do NOT add noqa/type:ignore without justification. or stop after 10 turns.
```
