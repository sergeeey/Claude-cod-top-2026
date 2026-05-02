---
name: project-context
description: >
  [STATUS: confirmed] [CONFIDENCE: high]
  Мгновенный загрузчик контекста проекта — читает activeContext.md и возвращает
  текущий фокус, архитектурные решения, последние мержи и состояние тестов.
  Используй когда нужно быстро понять где находится проект без чтения всех файлов.
  Триггеры: /project-context, /ctx, "что сейчас делаем", "текущий контекст",
  "что в работе", "current focus", "project state".
  НЕ использовать для: детального изучения архитектуры — для этого /gitnexus-exploring.
effort: low
tokens: ~200
---

<!-- BSV — Brief Skill View
Скил   : project-context
TL;DR  : Читает activeContext.md → текущий фокус + решения + статус тестов
Вызов  : /project-context, /ctx, "что сейчас делаем"
НЕ для : Детальная архитектура — используй gitnexus-exploring
-->

# Project Context Skill

## Trigger

- `/project-context` или `/ctx`
- Prompt contains: "что сейчас делаем", "current focus", "project state", "где мы"

## Workflow

1. **Read** `.claude/memory/activeContext.md` — Current Focus + Project State
2. **Read** `.claude/memory/decisions.md` (если есть) — последние архитектурные решения
3. **Report** структурированный дайджест:
   - Текущий фокус (1-2 предложения)
   - Open PRs / последние мержи
   - Статус тестов и coverage
   - SCOPE FENCE: что в работе, что НЕ сейчас

## Output Format

```
📍 Current Focus: <из activeContext.md ## Current Focus>
🔀 Branch: <ветка> | PRs: <open count>
✅ Tests: <N> passing | Coverage: <X>%
🚧 Scope: <Goal> | NOT NOW: <out of scope>
📋 Last decisions: <последние 2-3 из decisions.md>
```

## Notes

- Если `activeContext.md` не найден → сообщи что файл отсутствует, предложи создать
- Не обновляй контекст автоматически — только читай
- Для обновления контекста → `post_commit_memory.py` hook делает это сам после коммита
