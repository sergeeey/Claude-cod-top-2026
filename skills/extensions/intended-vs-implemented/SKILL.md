<!-- BSV — Brief Skill View | поиск: BSV
Скил   : intended-vs-implemented
TL;DR  : Ищет разрыв между задокументированным поведением и реальным кодом
Вызов  : `/intended-vs-implemented`, 'docs vs code', 'задокументировано vs реализовано'
НЕ для : Синтаксических ошибок (ruff/mypy), стиля кода, coverage
-->

---
name: intended-vs-implemented
description: >
  USE when you need to find gaps between what documentation claims the system
  does vs what the code actually does. Catches high-value bugs that linters miss:
  permissions documented but unenforced, endpoints marked internal that accept
  external calls, data classified as private that leaks.
  ALWAYS cite both documentation claim AND code evidence — no speculation.
  Triggers: /intended-vs-implemented, docs vs code, intent vs reality,
  задокументировано vs реализовано, docs не совпадают с кодом,
  что обещано vs что делает, audit intent, verify documented behavior.
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-06-11]
effort: medium
tokens: ~600
---

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

Читать: `README.md`, `docs/`, `CLAUDE.md`, docstrings, inline comments с `# WHY:`.

Для каждого claim записать:
```
CLAIM: [что утверждается]
SOURCE: [файл:строка]
TYPE: [security | privacy | access-control | behavior | performance]
```

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

### Шаг 3 — Сравнить Claim vs Evidence

| Claim | Documented in | Evidence in code | Match? |
|---|---|---|---|
| "PII auto-redacted" | README:79 | `hooks/redact_pii.py:45` | ✅ |
| "SQL uses parameterized queries" | rules/security.md:12 | grep → 0 raw string SQL | ✅ |
| "Secrets never committed" | README:206 | `hooks/redact_secrets.py` | ✅ |
| "X feature available" | README:X | ??? | ❌ GAP |

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
