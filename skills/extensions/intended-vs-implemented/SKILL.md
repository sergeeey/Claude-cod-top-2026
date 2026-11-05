---
name: intended-vs-implemented
description: >
  Сверяет, что система реально делает, с тем, что обещают документы, и наоборот.
  Ловит то, что линтеры пропускают: права, заявленные, но не enforce-ятся; внутренние
  endpoints, принимающие внешние вызовы; приватные данные, которые утекают; код, которого
  нет в документации. Каждый вывод цитирует и утверждение, и код. Без догадок.
  Триггеры: /intended-vs-implemented, docs vs code, intent vs reality,
  задокументировано vs реализовано, docs не совпадают с кодом,
  что обещано vs что делает, audit intent, verify documented behavior.
  [STATUS: review] [CONFIDENCE: high] [REVIEWED: 2026-08-11]
effort: medium
tokens: ~600
---
<!-- BSV — Brief Skill View | поиск: BSV
Скил   : intended-vs-implemented
TL;DR  : Ищет разрыв между задокументированным поведением и реальным кодом
Вызов  : `/intended-vs-implemented`, 'docs vs code', 'задокументировано vs реализовано'
НЕ для : Синтаксических ошибок (ruff/mypy), стиля кода, coverage
-->

# /intended-vs-implemented — Audit: Docs vs Code

## Когда использовать

Когда нужно проверить что система **реально делает то что задокументировано**:
- Security review: "permissions enforced" — а они правда enforced?
- API audit: endpoint помечен `internal-only` — принимает ли внешние вызовы?
- Data privacy: поле помечено `private` — утекает ли публично?
- Pre-release gate: README claims feature X — реализована ли X полностью?

Это **третий слой верификации** после синтаксиса (ruff/mypy) и тестов (pytest):
```
ruff/mypy → корректность синтаксиса
pytest    → ожидаемое поведение кода
/intended-vs-implemented → соответствие документированному намерению
```

## Протокол (5 шагов)

### Шаг 1 — Собрать Intent (документация как claims)

Читать: `README.md`, `docs/`, `CLAUDE.md`, docstrings, inline comments с `# WHY:`, ADR, спецификации, схемы, тесты, которые явно фиксируют публичный контракт.

**Авторитет источников (по убыванию):** внешняя спецификация или регуляция → утверждённый ADR или контракт → публичная API-спецификация → документация проекта → README → docstring → inline-комментарий.
Тест считается источником намерения только если он явно фиксирует публичный контракт. Тест, описывающий текущую реализацию, — это свидетельство реализации, а не намерения.

**Конфликт источников:** если два источника с разным авторитетом расходятся или одного уровня противоречат друг другу → статус `CONTRADICTORY_INTENT`. Такой claim не сравнивается с кодом, пока противоречие не разрешено.

Для каждого claim записать:
```
CLAIM: [что утверждается]
SOURCE: [файл:строка]
TYPE: [security | privacy | access-control | behavior | performance]
STATUS: [active | planned | experimental | deprecated | flag:<name>]
VERSION: [версия или условие, при котором claim действует, либо "any"]
```

Если STATUS не `active` или есть условие VERSION/флага: сравнивать с кодом только в этом условии. Вне условия результат — `UNVERIFIABLE` (условие не наступило или не проверяемо), а не `GAP`.

### Шаг 2 — Найти Implementation Evidence

Для каждого claim — найти реальный код который его реализует (или не реализует):

```bash
# Пример: claim "PII never logged"
grep -rn "logger\|logging\|print\|structlog" hooks/ --include="*.py" | \
  grep -iE "email|phone|password|ssn|card"

# Пример: claim "only authenticated users reach /admin"
grep -rn "admin\|auth\|permission" hooks/ --include="*.py"
```

Каждый результат — `[VERIFIED-grep]` или `[VERIFIED-read]`.

**Уровни доказательств** (для каждого claim записывать достигнутый уровень):

| Уровень | Что доказано | Пример |
|---|---|---|
| L0 TEXT_MATCH | найдено слово или символ | `grep redact` дал строку |
| L1 CODE_PRESENT | реализация существует | функция `enforce_permission()` есть |
| L2 WIRED | код достижим из нужной точки входа | функция вызывается из middleware |
| L3 EXECUTED | путь выполняется: тест или запуск показывает поведение | тест «неавторизованный запрос → 403» проходит |
| L4 ADVERSARIAL | негативный тест показывает, что граница не обходится | запрос в обход middleware тоже отклоняется |

**Правило:** для claims типа `security`, `privacy`, `access-control` статус `MATCH` требует минимум L3, а для утверждений «нельзя обойти» — L4. L1 и L2 — недостаточно. Наличие символа в коде не означает, что ограничение действует.

### Шаг 2b — Обратный проход: Code → Docs

Шаги 1–2 идут от документов и поэтому не видят поведение, которого в документах нет. Это самый опасный класс drift: реализовано, но не задекларировано.

Найти точки, где код пересекает границу (доверия, данных, стоимости, тенанта): внешние вызовы, запись и отправка данных, обработка внешнего ввода, ресурсоёмкие операции. Для каждой такой точки найти задекларированный контракт.

- Контракт найден → обычная проверка в Шаге 3.
- Контракта нет → finding `UNDOCUMENTED_BEHAVIOR`. Severity определяется границей, которую пересекает поведение.

Без этого прохода аудит проверяет только то, что уже описано, и пропускает самые рискованные отклонения.

### Шаг 3 — Сравнить Claim vs Evidence

| Claim | Documented in | Evidence in code | Match? |
|---|---|---|---|
| "PII auto-redacted" | README:198 | `scripts/redact.py` PATTERNS (national ID/card/IBAN/email/phone) + `clean()` | ✅ |
| "SQL uses parameterized queries" | rules/security.md:12 | grep → 0 raw string SQL | ✅ |
| "Secrets redacted before external MCP calls" | scripts/redact.py:3-5 (module docstring) | same PATTERNS list (API keys/tokens) + `main()` PreToolUse entrypoint | ✅ |
| "X feature available" | README:X | ??? | ❌ GAP |

**Статусы сравнения** (ровно один на каждый claim или точку кода):

| Статус | Значение |
|---|---|
| `MATCH` | claim подтверждён на уровне, требуемом Шагом 2 |
| `UNDER_IMPLEMENTED` | claim есть, реализация неполная или отсутствует |
| `OVER_IMPLEMENTED` | код делает больше, чем заявлено, и это значимо для границы |
| `UNDOCUMENTED_BEHAVIOR` | код пересекает границу, контракта нет (Шаг 2b) |
| `CONTRADICTORY_INTENT` | источники намерения противоречат друг другу (Шаг 1) |
| `CONDITIONALLY_MATCHED` | совпадает при выполнении условия (флаг, версия), условие не проверено во всех случаях |
| `UNVERIFIABLE` | доказательств недостаточно или условие не наступило |

### Шаг 4 — Классифицировать Gaps

Оставлять только gaps которые **пересекают реальную границу**:
- Trust boundary: непроверенный внешний ввод достигает логики
- Data boundary: private данные утекают в logs/response
- Cost boundary: неограниченный ресурс доступен без проверки
- Tenant boundary: данные одного пользователя видны другому

**Не считать finding'ом:** косметическое расхождение docs vs code без реального риска.

### Шаг 5 — Отчёт с Evidence Markers

Каждый finding обязательно содержит:

```markdown
## FINDING: [название]
Severity: HIGH | MEDIUM | LOW
Type: [security | privacy | behavior]
Status: [MATCH | UNDER_IMPLEMENTED | OVER_IMPLEMENTED | UNDOCUMENTED_BEHAVIOR | CONTRADICTORY_INTENT | CONDITIONALLY_MATCHED | UNVERIFIABLE]
Evidence level: [L0 | L1 | L2 | L3 | L4]

CLAIMED (docs):
  > "[точная цитата]"
  Source: [файл:строка] [VERIFIED-read]

IMPLEMENTED (code):
  > "[что реально делает код]"
  Evidence: [файл:строка] [VERIFIED-grep]

GAP: [конкретное расхождение — одно предложение]
FIX: [минимальное исправление]
```

**Запрещено:** `[HYPOTHESIS]` без tool-verified evidence на HIGH/MEDIUM findings.
**Запрещено:** статус `MATCH` для security/privacy/access-control claim на уровне L0–L2.
Правило из `rules/audit-verification-gate.md`.

## Интеграция с нашим стеком

- Используй **после** `ruff` + `pytest` — они должны быть зелёными
- Findings HIGH/MEDIUM → передать в `sec-auditor` агент для подтверждения
- Findings → записать в `.claude/memory/decisions.md` как `[AVOID]` паттерн
- Для security gaps → запустить `/threat-modeling` для оценки вектора атаки

## Пример быстрого запуска

```
"Проверь что README-claim 'PII auto-redacted before external MCP calls'
 реально реализован в hooks/"
```

Claude: читает README claim → grep hooks/ → читает redact_pii.py →
        сравнивает → отчёт с [VERIFIED-grep] / [VERIFIED-read] маркерами.
