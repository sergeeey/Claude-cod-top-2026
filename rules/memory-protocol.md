# Memory Protocol

## Проектная память (в каждом проекте)
```
<project>/.claude/memory/activeContext.md  — что делаем сейчас
<project>/.claude/memory/decisions.md      — архитектурные решения
<project>/.claude/checkpoints/             — точки сохранения
```

## Глобальная память (~/.claude/memory/)
```
user_profile.md  — КТО Сергей
patterns.md      — ЧТО работает
learning_log.md  — ЧТО освоил
goals.md         — КУДА идём
decisions.md     — ПОЧЕМУ так решили
```

## После каждого git commit
1. Обнови activeContext.md
2. Сложный баг → patterns.md
3. Архитектурное решение → decisions.md

## Context Overflow (70% порог)
1. Обнови activeContext.md
2. /clear
3. Загрузи контекст → продолжай

## Checkpoints — перед рисковыми операциями
- git rebase/merge в main, крупный рефакторинг
- Миграция БД, смена архитектуры, релиз
- checkpoint_guard.py напомнит автоматически
