---
name: codex-solver
description: "Запускает Codex в режиме Triple Solution Finder: находит OBVIOUS (простой/проверенный), NON-OBVIOUS (неожиданный), и BEST (оптимальный) вариант решения любой задачи."
triggers: [codex-solver, найди решение codex, codex варианты, три варианта, codex alternatives, best solution codex]
tokens: ~250
type: directory
---

# Codex Solver — Triple Solution Finder

## Когда использовать
- Есть задача и непонятно как решать
- Нашёл одно решение — хочешь проверить есть ли лучше
- Архитектурный выбор — нужны альтернативы с трейдоффами
- Claude предложил подход — хочешь независимый второй взгляд

## Как запустить

Скажи Claude: **"запусти codex-solver на [задача/проблема]"**

Claude выполнит:
```
/codex:rescue --wait "SOLVER MODE — Triple Solution Finder.

Problem: [описание задачи]
Context: [стек, ограничения, цели]

Find exactly THREE solutions:

━━━ SOLUTION 1: OBVIOUS ━━━
The boring, proven, "everyone does it this way" approach.
- No cleverness, no novelty
- Battle-tested in production
- Easy to understand and maintain
- What a senior engineer would suggest at 11pm on a Friday

━━━ SOLUTION 2: NON-OBVIOUS ━━━
The unexpected angle. What if we:
- Inverted the problem?
- Removed a constraint everyone assumes is fixed?
- Used a tool from a completely different domain?
- Did nothing (is the problem worth solving)?
Search the web for: how do top engineers approach [problem type] in 2026?

━━━ SOLUTION 3: BEST ━━━
Optimal balance of: correctness + maintainability + speed to implement + risk
May combine elements from above or be entirely different.

Output format:
## Solution 1 — OBVIOUS
[implementation approach]
Pros: | Cons: | Time: | Risk:

## Solution 2 — NON-OBVIOUS
[implementation approach]
Why unexpected: [what assumption it breaks]
Pros: | Cons: | Time: | Risk:

## Solution 3 — BEST (recommended)
[implementation approach]
Why best: [specific reasoning]
Pros: | Cons: | Time: | Risk:

## My pick: Solution [N]
[1-2 sentence justification]"
```

## Примеры использования

```
запусти codex-solver: нужно кэшировать результаты API вызовов в хуках
запусти codex-solver: как хранить состояние между сессиями без файлов
запусти codex-solver на проблему медленного wiki поиска в prompt_wiki_inject.py
```

## Интерпретация

- **Если Solution 1 = Solution 3** → задача простая, не усложняй
- **Если Solution 2 = Solution 3** → текущий подход устарел, стоит переосмыслить
- **Если все три разные** → архитектурный выбор, обсуди с командой
