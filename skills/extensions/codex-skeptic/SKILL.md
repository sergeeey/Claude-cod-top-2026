---
name: codex-skeptic
description: "Запускает Codex в режиме falsification-first: ломает идею/код/архитектуру ДО реализации. Ищет hidden assumptions, failure modes, edge cases. Возвращает confidence score и конкретные условия провала."
triggers: [codex-skeptic, сломай через codex, codex red-team, codex falsification, проверь идею codex]
tokens: ~200
type: directory
---

# Codex Skeptic — Falsification Engine

## Когда использовать
- Перед реализацией новой фичи — проверить идею
- После написания кода — найти что сломается
- Архитектурное решение — оспорить assumptions
- Когда Claude одобрил, но есть сомнения

## Как запустить

Скажи Claude: **"запусти codex-skeptic на [идея/файл/архитектура]"**

Claude выполнит:
```
/codex:rescue --wait "SKEPTIC MODE — falsification-first analysis.

Target: [описание цели]

Your mission: BREAK THIS before it costs time or money.

Step 1 — List every hidden assumption (min 5)
Step 2 — For each assumption: what happens if it's wrong?
Step 3 — Find the single most likely failure mode
Step 4 — Find the non-obvious failure mode (the one no one checks)
Step 5 — Search web for: has this approach failed before? why?

Output format:
## Confidence Score: X/10
## Hidden Assumptions: [list]
## Most Likely Failure: [specific scenario]
## Non-Obvious Failure: [the one everyone misses]
## Verdict: SHIP / FIX FIRST / ABANDON
## If FIX FIRST: exactly what to fix (1-3 items max)"
```

## Примеры использования

```
запусти codex-skeptic на hooks/moc_autolink.py
запусти codex-skeptic на идею добавить Redis кэш
запусти codex-skeptic на архитектуру async_wrapper паттерна
```

## Интерпретация результата

| Score | Значение |
|-------|----------|
| 8-10 | Шипи — Codex не нашёл серьёзных проблем |
| 5-7 | Исправь сначала — есть реальные риски |
| 0-4 | Стоп — фундаментальная проблема |

## Связка со скептик-агентом Claude

Для максимального эффекта: сначала `/skeptic` (Claude red-team), потом `codex-skeptic` — два независимых взгляда с разными моделями.
