---
name: thomas
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-05-26]
  Outcome-first coding skill в честь Dr. Thomas Gordon (Win-Win/No-Lose Method).
  Заставляет связывать каждое нетривиальное изменение кода с проверяемым результатом
  через Outcome Card: desired outcome, blocker, smallest useful next step, win-win
  constraint, success check. Используй когда пользователь просит дебажить, рефакторить,
  спроектировать, ревьюить, реализовать, оптимизировать, тестировать или планировать
  изменения кода — особенно когда задача расплывчатая или может разрастись.
  Triggers: /thomas, thomas:, Outcome Card, "что мы хотим получить", outcome first,
  debug, refactor, implement feature, fix bug, code review, architecture decision,
  test plan, performance fix, CI fix, technical debt, "почини баг", "сделай фичу",
  "оптимизируй", "проверь код", "запланируй изменения", "smallest step",
  "what is the desired outcome". Активировать проактивно когда задача coding,
  и пользователь не написал явно желаемый результат.
  НЕ для: тривиальных one-liner (typo, форматирование), интерактивных обсуждений
  без цели изменить код, research/scientific методологии,
  routing задач.
effort: low
tokens: ~500
triggers: [/thomas, thomas:, "Outcome Card", "что мы хотим получить", "outcome first", debug, refactor, "implement feature", "fix bug", "code review", "architecture decision", "test plan"]
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : thomas
TL;DR  : Outcome-first coding — Outcome Card перед каждой нетривиальной правкой
Вызов  : /thomas, "outcome first", "desired outcome", debug/refactor/implement/review/test
НЕ для : Тривиальных правок, интерактивных обсуждений без цели, research methodology
-->

# Thomas — Outcome-First Coding

В честь **Dr. Thomas Gordon** (Win-Win / No-Lose Method, 1970-е) — методология
решения проблем, где обе стороны выигрывают, ничто важное не приносится в жертву.

В коде это значит: **изменение не считается хорошим, если оно помогает одной цели
и молча ломает другую** (correctness vs readability vs performance vs security).

## Зачем

Самая частая ошибка в coding-задачах — начать менять файлы **до того как сформулирован
проверяемый результат**. Получаются ситуации:

- "Починили баг" — но новый баг создан в смежном коде
- "Отрефакторили" — но performance упал и тесты молча сломались
- "Добавили фичу" — но юзер хотел другое
- "Оптимизировали" — но измерения не делали, может стало медленнее

Thomas заставляет **сначала написать Outcome Card** — 5 строк — потом действовать.

## Когда использовать

**ДА:**
- Debug бага (особенно когда причина не очевидна)
- Refactor больше 1 файла
- Архитектурные решения
- Реализация фичи
- Code review
- Test planning
- CI/CD fix
- Performance fix
- Уменьшение технического долга
- Расплывчатый запрос на изменение кода

**НЕТ:**
- Typo, форматирование, переименование переменной
- Read-only вопросы ("где определён X?")
- Research methodology — отдельный инструмент
- Routing — отдельный инструмент

## Outcome Card — обязательный формат

До нетривиальных правок выдай эту карточку. Кратко, без воды:

```markdown
## Outcome Card

**Desired outcome:**
[Конкретный проверяемый результат который нужен пользователю]

**Current blocker:**
[Что мешает прямо сейчас]

**Smallest useful next step:**
[Минимальное действие которое уменьшит неопределённость или продвинет к цели]

**Win-win constraint:**
[Что НЕЛЬЗЯ сломать: тесты, читаемость, обратная совместимость, безопасность,
 performance, maintainability]

**Success check:**
[Как мы поймём что шаг сработал — конкретная команда, тест, метрика]
```

Если задача простая — сожми в одну строку (Compact Mode):
```
Outcome: [результат] | Blocker: [что мешает] | Next: [шаг] | Check: [проверка]
```

## Coding Workflow (после Outcome Card)

### 1. Уточняй только если действительно блокирует
Максимум один уточняющий вопрос, и только если без ответа код будет неверный.
В остальных случаях — сделай безопасное допущение и пометь:
```
Assumption: [безопасный дефолт]
```

### 2. Inspect перед Edit
Прочитай релевантные файлы, тесты, конфиги, логи ошибок **до** правки.
Доказательства > догадки.

### 3. Выбирай smallest useful change
Не переписывай большие куски без необходимости. Предпочитай:
- один сломанный тест починен
- один баг изолирован
- один интерфейс прояснён
- одна функция упрощена
- одна рискованная зависимость убрана
- одно измеримое узкое место performance закрыто

### 4. Сохраняй Win-Win (главный принцип Dr. Thomas)
Правка не хорошая если помогает одной цели и молча ломает другую. Проверь:
- Correctness
- Tests
- Readability
- Backward compatibility
- Security
- Maintainability
- Performance
- Developer ergonomics

### 5. Verify
После изменений запусти самую релевантную доступную проверку:
- unit tests
- type checks (mypy)
- lint (ruff)
- build
- targeted script
- reproduction command

Если проверка невозможна — **скажи об этом явно**. Не утверждай "тесты прошли"
если их не запускал.

### 6. Report в outcome-language

Финальный ответ в этом формате:

```markdown
## Result

**Outcome achieved:**
[Что теперь работает]

**Changed:**
[Файлы или модули которые изменились]

**Verification:**
[Какие тесты/проверки прошли — или явно "не запускалось"]

**Remaining blocker:**
[Только если что-то не доделано]

**Next smallest step:**
[Только если есть продолжение]
```

## Decision Heuristics

Когда есть несколько вариантов — выбирай тот который:
1. Решает конкретный результат пользователя
2. Требует наименьшего безопасного изменения
3. Легче всего проверить
4. Сохраняет существующее поведение
5. Снижает будущую неопределённость

## Anti-Patterns (что НЕ делать)

❌ Начинать с большого предложения архитектуры **до** инспекции кода
❌ Менять много файлов без явного success check
❌ Добавлять абстракции до того как доказана необходимость
❌ Считать "чистый код" важнее результата пользователя
❌ Скрывать неопределённость ("вроде работает")
❌ Утверждать что тесты прошли, если их не запускал
❌ Оптимизировать без измерений
❌ Просить уточнения когда safe default достаточно

## Пример

**Пользователь:** "Почини баг с авторизацией"

**Thomas response:**

```markdown
## Outcome Card

**Desired outcome:**
Пользователи могут логиниться валидными credentials.

**Current blocker:**
Источник падения неизвестен — может быть validation, генерация токена,
session storage, или фронтенд handling.

**Smallest useful next step:**
Инспектировать auth flow, воспроизвести или найти падающий тест/лог,
изолировать failing boundary.

**Win-win constraint:**
Не ослабить security и не обойти валидацию.

**Success check:**
Targeted auth test проходит, или login flow работает с валидными
credentials и всё ещё отклоняет невалидные.
```

Затем инспектирует файлы и работает.

## Companion Skills

- (опционально) TDD-навык: RED-GREEN-REFACTOR, outcome через тесты
- (опционально) brainstorming-навык: design alternatives до multi-file changes

## Почему "Thomas"

Dr. Thomas Gordon — психолог, разработавший **Win-Win / No-Lose Method** для
разрешения конфликтов где обе стороны должны выиграть, иначе решение не считается
хорошим. В коде это работает точно так же: изменение не считается хорошим,
если оно помогает одной цели и ломает другую.

"Win-Win constraint" в Outcome Card — это и есть его метод применённый к коду.
