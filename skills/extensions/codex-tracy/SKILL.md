---
name: codex-tracy
description: "Запускает Codex в режиме Brian Tracy Strategic Clarity: находит A1-приоритет, frog-задачу, что исключить. Для кода, проекта, backlog, застревания в ступоре."
triggers: [codex-tracy, приоритизируй через codex, codex strategy, codex tracy, что важнее codex]
tokens: ~200
type: directory
---

# Codex Tracy — Strategic Clarity

## Когда использовать
- Backlog переполнен — непонятно что делать первым
- Застрял в ступоре — много всего, нет ясности
- Перед началом сессии — определить A1 задачу
- После большого PR — что делать дальше

## Как запустить

Скажи Claude: **"запусти codex-tracy на [проект/задачи/backlog]"**

Claude выполнит:
```
/codex:rescue --wait "TRACY MODE — Strategic Clarity System.

Context: [описание ситуации/backlog/проблемы]

Apply Brian Tracy's full decision framework:

Step 1 — ABCDE Method: categorize every item
  A = Must do (serious consequences if skipped)
  B = Should do (mild consequences)
  C = Nice to do (no consequences)
  D = Delegate
  E = Eliminate

Step 2 — Find the FROG: the most important AND most avoided task
  - If you had to do only ONE thing today, what moves the needle most?
  - What are you avoiding that you know matters?

Step 3 — 80/20 scan: which 20% of tasks deliver 80% of results?

Step 4 — Elimination audit: what looks like work but isn't?

Output format:
## A1 Task (do this first, today):
[single specific action]

## The Frog (most important, most avoided):
[what and why it's being avoided]

## Top 3 by impact (80/20):
1. [task] — [why high impact]
2. [task] — [why high impact]
3. [task] — [why high impact]

## Eliminate immediately:
[list of tasks that look like work but aren't]

## Next concrete action (first 25 minutes):
[exactly what to do, no ambiguity]"
```

## Примеры использования

```
запусти codex-tracy на activeContext.md
запусти codex-tracy: у меня 5 открытых PR и не знаю с чего начать
запусти codex-tracy на список задач этой недели
```

## Связка с tracy-агентом Claude

`/tracy` (Claude) → стратегия на уровне жизни/карьеры
`codex-tracy` → стратегия на уровне кода/проекта прямо сейчас
