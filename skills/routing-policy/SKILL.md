---
name: routing-policy
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-13]
  ALWAYS CHECK before starting ANY task. Decision routing matrix for
  task→skill→agent→tools selection. Determines optimal execution path.
  Triggers: любая задача, начало работы, новый запрос, план, task,
  implement, fix, debug, review, add, create, build, change.
---

# Routing Policy — Матрица маршрутизации задач

## Как использовать

Перед началом ЛЮБОЙ задачи определи её тип и следуй маршруту.

## Матрица маршрутизации

### Тип 1: Исследование / Вопрос
**Сигналы**: «что это», «как работает», «где находится», «почему», explain, find, search

**Маршрут**:
1. Explore subagent → Read/Grep/Glob (локальные инструменты)
2. Если не найдено локально → MCP (Context7, PubMed, WebSearch)
3. Маркировать каждый факт по Evidence Policy

**Жёсткое правило**: сначала локальные инструменты, потом MCP. Не ходи в MCP без попытки найти ответ локально.

### Тип 2: Изменение кода (1-2 файла)
**Сигналы**: «измени», «добавь», «исправь» + конкретный файл/функция

**Маршрут**:
1. Read целевой файл(ы) целиком
2. Краткий план в ответе (не EnterPlanMode)
3. Edit/Write
4. Запустить тесты (`pytest -x -q` или эквивалент)
5. Если тесты упали → Read ошибку, понять причину, ПОТОМ чинить
6. Коммит

### Тип 3: Изменение кода (3+ файлов)
**Сигналы**: «рефакторинг», «новая фича», «миграция», multi-file change

**Маршрут**:
1. EnterPlanMode (plan_mode_guard сработает автоматически)
2. navigator агент (Opus) → декомпозиция на задачи
3. builder агент (Sonnet) → реализация каждого файла
4. tester агент (Sonnet) → тесты
5. reviewer агент (Opus) → code review
6. Коммит

### Тип 4: Написание тестов / TDD
**Сигналы**: «тесты», «test», «coverage», «TDD», «с тестами», «покрой тестами»

**Маршрут**:
1. Загрузить tdd-workflow skill (автоматически по триггеру)
2. RED → GREEN → REFACTOR
3. НИКОГДА не писать реализацию до тестов

### Тип 5: Отладка / Debugging
**Сигналы**: «падает», «ошибка», «не работает», «баг», error, fail, broken, debug

**Маршрут**:
1. Read полный traceback / error message
2. Explore subagent → поиск контекста в кодовой базе
3. Гипотеза [INFERRED] с указанием цепочки
4. Проверить гипотезу инструментом → [VERIFIED]
5. Если 3 попытки провалились → Stuck Detection → СТОП → спросить пользователя

### Тип 6: Security / Compliance
**Сигналы**: «аудит», «безопасность», «security», PII, SQL, auth, payments, .env

**Маршрут**:
1. Загрузить security-audit skill
2. reviewer агент → проверка кода
3. Проверить deny-list (17 паттернов)
4. Если работа с PII → убедиться что redaction hook активен

## Hard Guards — Абсолютные запреты

Эти правила перекрывают ЛЮБУЮ рационализацию:

| Guard | Правило | Предотвращает |
|-------|---------|---------------|
| **Read Before Edit** | НЕ редактировать файл без предварительного Read | Hallucination Loops |
| **Local Before MCP** | НЕ вызывать MCP без попытки найти локально | Лишний расход токенов |
| **Plan Before Multi-Edit** | НЕ делать Edit 3+ файлов без плана | Хаотичные изменения |
| **Test Before Commit** | НЕ коммитить без запуска тестов (если тесты есть) | Broken commits |
| **Evidence Before Claim** | НЕ утверждать факт без маркера Evidence Policy | Галлюцинации |

## Определение типа задачи

Если задача не очевидно попадает в один тип:
- Есть слово «тест/test/coverage» → **Тип 4** (TDD) имеет приоритет
- Есть слово «ошибка/error/баг» → **Тип 5** (Debugging) имеет приоритет
- Есть слово «security/PII/auth» → **Тип 6** (Security) имеет приоритет
- Затрагивает 3+ файлов → **Тип 3** (Multi-file) обязателен
- Остальное → **Тип 2** (Simple change) по умолчанию
