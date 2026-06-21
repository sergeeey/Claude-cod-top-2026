---
name: conductor
sub_type: guide
version: "1.0"
source: "wshobson/agents (adapted)"
description: >
  Context-Driven Development: управляет документацией проекта в директории conductor/
  (product.md, tech-stack.md, workflow.md, tracks.md) для консистентной AI-assisted разработки.
  Отслеживает фазы проекта, обеспечивает context health, поддерживает командное выравнивание.
  Используй при старте нового проекта, онбординге в существующий, управлении tech-stack документацией.
  Триггеры: /conductor, "context-driven", "project context", "conductor setup",
  "настрой проект", "документация проекта", "track management", "workflow phases".
tokens: ~250
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : conductor
TL;DR  : Context-Driven Development — артефакты проекта в conductor/ для AI-консистентности
Вызов  : /conductor, context-driven development, setup project context, tracks
НЕ для : Генерация кода (→ /builder); архитектурные решения (→ /architect)
-->

# Conductor — Context-Driven Development

## Зачем

Без управляемого контекста каждая AI-сессия начинается с нуля: нет tech stack, нет workflow,
нет активных tracks. Conductor создаёт `conductor/` артефакты которые Claude читает
перед любым действием — обеспечивая консистентность между сессиями и командным членами.

**Принцип:** Каждый артефакт должен информировать решение или поведение.
Если не информирует — удали. Документация ради документации = антипаттерн.

---

## Артефакты (conductor/ директория)

### product.md — Что мы строим
```markdown
# Product Context
## Vision
[1-2 предложения — суть продукта]
## Target Users
[Кто использует, основые сценарии]
## Key Features
[Топ-5 функций, коротко]
## Non-Goals
[Что мы явно НЕ делаем — защита от scope creep]
```

### tech-stack.md — Чем строим
```markdown
# Tech Stack
## Runtime
- Language: Python 3.11+
- Framework: FastAPI
## Database
- Primary: PostgreSQL 15
- Cache: Redis
## Infrastructure
- Cloud: AWS (us-east-1)
- CI: GitHub Actions
## Key Decisions
- [Почему выбрали X вместо Y — ссылка на decisions.md]
```

### workflow.md — Как работаем
```markdown
# Development Workflow
## Phases
1. Explore → Design → Plan → Code → Review → Deploy
## Branch Strategy
- main: production-ready always
- feature/: за PR, squash merge
## Quality Gates
- Tests: pytest ≥80% coverage
- Review: reviewer agent всегда
- Security: sec-auditor для auth/payments
```

### tracks.md — Активные задачи
```markdown
# Active Tracks
## Track 1: [Feature Name]
- Status: in_progress | blocked | review | done
- Owner: [agent/person]
- Files: [основные файлы]
- Blocker: [если есть]

## Completed
- [Track]: done [date]
```

---

## Шаг 1 — Инициализация

```bash
mkdir -p conductor
```

Создай 4 артефакта (шаблоны выше). Принципы заполнения:

1. **Конкретно**: "FastAPI + PostgreSQL" не "modern web framework"
2. **Коротко**: product.md < 1 страница, tech-stack.md < 2 страницы
3. **Actionable**: каждая строка должна помогать принять решение
4. **Living doc**: обновляй при каждом значимом изменении

---

## Шаг 2 — Интеграция с Workflow

**Начало каждой сессии:** Claude читает `conductor/` перед первым действием.

**При изменении tech stack:** Обнови `tech-stack.md` + добавь в `decisions.md` почему.

**При старте нового track:** Добавь в `tracks.md`, обнови status по ходу.

**При завершении фазы:**
```bash
# Переместить завершённые tracks
# Обновить workflow.md если процесс изменился
```

---

## Шаг 3 — Phase Tracking

Conductor отслеживает фазы через `tracks.md`:

| Фаза | Вход | Выход | Артефакт |
|------|------|-------|---------|
| **Explore** | Задача | Понимание проблемы | notes в track |
| **Design** | Понимание | Архитектурное решение | decisions.md |
| **Plan** | Решение | Список задач | tracks.md обновлён |
| **Code** | План | Рабочий код | PR |
| **Review** | Код | Одобренный PR | reviewer agent |
| **Deploy** | Одобрен | Задеплоен | track → done |

**Правило перехода фаз:** Не двигайся вперёд пока текущая фаза не закрыта.
Особенно: не Code без Design, не Deploy без Review.

---

## Context Health Checks

Conductor-артефакты устаревают. Проверяй раз в неделю:

- [ ] `tech-stack.md` соответствует `pyproject.toml` / `package.json`?
- [ ] `tracks.md` отражает реальный статус задач?
- [ ] `workflow.md` соответствует тому как реально работаем?
- [ ] `product.md` не противоречит последним решениям?

Если артефакт врёт — он хуже чем его отсутствие. Удаляй устаревшее.

---

## Связанные скилы

- `navigator` — стратегическое планирование сессии (читает conductor/)
- `architect` — архитектурные решения (пишет в decisions.md)
- `scope-guard` — защита от выхода за bounds product.md
