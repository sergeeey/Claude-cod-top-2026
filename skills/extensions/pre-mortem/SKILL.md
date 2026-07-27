<!-- BSV — Brief Skill View | поиск: BSV
Скил   : pre-mortem
TL;DR  : Классифицирует риски запуска на Tigers / Paper Tigers / Elephants до старта
Вызов  : `/pre-mortem`, 'что может пойти не так', 'риски запуска'
НЕ для : Пост-фактум анализа провалов (это retro), review кода, архитектурных решений
-->

---
name: pre-mortem
description: >
  USE before launching a feature, major refactor, or release — imagine it failed
  14 days later, then work backward to find what went wrong NOW.
  Classifies risks as Tigers (real, evidence-backed), Paper Tigers (unlikely),
  or Elephants (unspoken assumptions nobody is validating).
  Complements DDD/skeptic (which red-teams design); pre-mortem targets LAUNCH risks.
  Triggers: /pre-mortem, pre-mortem, что может пойти не так, риски запуска,
  launch risks, imagine failure, before we ship, перед релизом.
  [STATUS: confirmed] [CONFIDENCE: high] [REVIEWED: 2026-06-12]
effort: low
tokens: ~300
---

# /pre-mortem — Launch Risk Analysis

## Когда использовать

**До** запуска фичи, рефакторинга или релиза — когда ещё можно исправить:
- Перед крупным PR / merge в main
- Перед публичным анонсом или деплоем
- Перед сложным рефакторингом затрагивающим ≥5 файлов
- Когда команда "уверена что всё хорошо" (Trigger 4 DDD)

**НЕ использовать:** для ревью кода (→ `/code-review`), архитектурных решений
(→ `rules/doubt-driven-development.md`), пост-фактум разбора (→ ретроспектива).

## Разница с DDD Skeptic

| | DDD Skeptic | Pre-Mortem |
|---|---|---|
| Когда | До написания кода | До запуска/деплоя |
| Что атакует | Дизайн и подход | Риски исполнения |
| Контекст | Полный (goal + proposal + alternatives) | Только описание запуска |
| Выход | Уязвимости дизайна | Tigers / Paper Tigers / Elephants |

## Протокол (3 шага)

### Шаг 1 — Сценарий провала

Представить: **через 14 дней после запуска что-то пошло не так.**
Записать 5-10 конкретных причин — что именно произошло?

Фокусироваться на:
- Что ломается первым при нагрузке?
- Какое предположение оказалось неверным?
- Что команда обсуждала но не зафиксировала?
- Какой edge case никто не проверил?

### Шаг 2 — Классификация рисков

**🐯 Tiger** — реальная угроза, подтверждённая evidence:
- Конкретные данные или прецеденты указывают на риск
- Требует mitigation ДО запуска

**📄 Paper Tiger** — поверхностный страх, маловероятный:
- Нет evidence что произойдёт
- Команда переоценивает угрозу
- Можно игнорировать или мониторить

**🐘 Elephant** — непроговорённое предположение:
- Команда предполагает но не валидирует
- Реальность неизвестна
- Требует проверки перед запуском

### Шаг 3 — Action Plan для Tigers

Для каждого Tiger (Launch-Blocking / Fast-Follow / Track):

```
🐯 Tiger: [название риска]
Urgency: Launch-Blocking | Fast-Follow | Track
Evidence: [почему это реальный риск]
Mitigation: [конкретное действие]
Owner: [кто делает]
Done by: [дата]
```

## Пример вывода

```
СЦЕНАРИЙ: через 14 дней после merge большого рефакторинга auth middleware

🐯 Tigers (требуют action):
  [Launch-Blocking] Session invalidation race condition
    Evidence: hooks/auth.py:47 — нет lock при обновлении токена
    Mitigation: добавить asyncio.Lock() перед write
    Done by: до merge

  [Fast-Follow] Rate limit bypass через legacy endpoint /api/v1/login
    Evidence: endpoint существует в routes.py:203, rate limit только на /api/v2/
    Mitigation: deprecate или добавить rate limit
    Done by: +7 дней

📄 Paper Tigers (мониторить):
  - "Новый код медленнее" — нет benchmark данных, предположение
  - "Пользователи запутаются" — изменение только backend, UI не затронут

🐘 Elephants (проверить):
  - Предполагаем что все клиенты используют v2 API — не проверено
    → Action: grep production logs для /api/v1/ вызовов
```

## Интеграция с нашим стеком

- Запускай **после** DDD (design ревью) и **до** merge/деплоя
- Tigers → создать задачи в `.claude/memory/activeContext.md`
- Elephants с неизвестным статусом → проверить через `/intended-vs-implemented`
- Launch-Blocking Tigers заблокированы до fix — не деплоить с открытыми Tiger tasks
- Revisit за 2-3 дня до запуска: прошли ли Tigers через mitigation?
