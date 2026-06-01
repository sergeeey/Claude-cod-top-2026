---
name: atomize
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-05-30]
  Разбирает проект на 7±2 ключевых атома, строит interface map, находит top-3 bottlenecks,
  выдаёт ОДИН следующий /goal. Минимальная версия из APEX-Project-Refiner — только уникальные
  функции (atomic decomposition + interface map + per-atom DoD), без overlap с /orient,
  /sci-code-audit, /validate, /strategic-analysis, /snr, /proof-ladder.
  ОБЯЗАТЕЛЬНО заканчивается executable /goal — не отчётом.
  Triggers: /atomize, "разбери проект на атомы", "найди bottleneck", "interface map",
  "что улучшить первым", atomic decomposition, project atoms, "на что распадается проект",
  "где узкое место", "покажи атомы проекта", "что тормозит прогресс", "разложи по атомам".
  НЕ для: pitch (/weiss), founder validation (/office-hours), code audit (/sci-code-audit),
  startup audit (/validate), project briefing (/orient).
effort: medium
tokens: ~700
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : atomize
TL;DR  : 7±2 атома + interface map + top-3 bottlenecks → ОДИН /goal на bottleneck #1
Вызов  : /atomize, "разбери на атомы", "найди bottleneck", "interface map"
НЕ для : Брифинг (→ /orient), аудит кода (→ /sci-code-audit), стартап-аудит (→ /validate)
Выход  : ВСЕГДА заканчивается executable /goal, не отчётом
-->

# Atomize — Atomic Decomposition + Interface Map

## Зачем

Проект кажется сложным — потому что его никто не видел целиком. Atomize разбивает его
на 7±2 ключевых атома (модулей ответственности), строит карту их взаимодействий и
находит где именно зажата система. Выход — не отчёт, а один конкретный /goal.

**Уникальное покрытие** (чего нет в других скилах):
- Atomic decomposition с per-atom quality + importance score
- Interface map (atom × atom: контракт, риск, улучшение)
- Bottleneck ranking на основе матрицы — не интуиции
- /goal строго по bottleneck #1, с kill criteria

---

## HARD RULES (non-negotiable)

- Maximum 9 atoms (7±2 — Miller 1956 working memory rule). Больше → collapse.
- Maximum 3 bottlenecks. Больше → это не bottlenecks, это wishlist.
- Maximum 5 actions в roadmap (если нужен). Больше → scope creep.
- Gold standard horizon = 30 days max. Нет "в будущем" и "когда-нибудь".
- No new architecture unless removing old complexity. Добавить = последний выбор.
- Read-only first: analyze phase — никаких правок файлов до вывода результата.
- Output MUST end with ONE executable /goal. Не список, не "варианты" — один /goal.

---

## Mode Flags

| Flag | Что делает | Когда |
|---|---|---|
| (default) | Full pipeline: 5 шагов, все секции | Первый запуск на проекте |
| `--scan` | 15-мин аудит: 7 атомов + 3 bottlenecks + 1 quick win | Нужен быстрый ответ |
| `--deep` | Все атомы с детальным разбором кода + тестов | Перед большим рефактором |
| `--interface` | Только таблица atom × atom взаимодействий | Отлаживаешь интеграцию |
| `--feature <name>` | Один атом: deep dive до gold standard | Конкретная фича под лупой |
| `--gold30` | 30-day gold standard target (constraint: no new hires, no new deps) | Планирование квартала |

---

## Pipeline (5 Steps — Default)

### Step 1 — Read (read-only, no edits)

Читать в порядке приоритета:
```
CLAUDE.md           → цели, стек, ограничения
README.md           → что проект делает публично
source tree (ls)    → реальная структура папок
tests/              → что тестируется (= что важно)
.claude/memory/activeContext.md  → текущий фокус
.claude/memory/decisions.md      → архитектурные решения
git log --oneline -20            → последние изменения
```

Если файл отсутствует → пропустить, не fabricate. Отметить как [UNKNOWN].

### Step 2 — Atomic Decomposition

Разбить проект на 7±2 атома. Атом = единица ответственности с чёткой границей.

**Типы атомов:**
- `Core` — бизнес-логика, алгоритм, domain model
- `Infra` — хранение, конфиги, CI/CD, деплой
- `Interface` — API, CLI, UI, hooks
- `Test` — тест-сьют, фикстуры, smoke tests
- `Docs` — документация, onboarding, CLAUDE.md
- `Integration` — внешние зависимости, MCP, webhooks
- `Memory` — state, кэш, персистентность между запусками

**Таблица атомов:**

| Atom | Type | Purpose | Evidence | Quality (1-5) | Importance (1-5) |
|---|---|---|---|---|---|
| ... | ... | ... | file:line | ... | ... |

**Правила scoring** (NO composite multiplication — скрывает tradeoffs):
- Quality: 1=broken/missing, 2=partial, 3=works, 4=solid, 5=gold
- Importance: 1=nice-to-have, 3=blocks progress, 5=project fails without it
- Сортировка: Importance DESC, затем Quality ASC (worst-first = highest ROI)

**Granularity check:**
- >9 atoms → collapse похожие (например, два Core → один)
- <5 atoms → проект слишком маленький для atomize, предложить /orient

### Step 3 — Interface Map

Таблица взаимодействий atom × atom:

| From | To | Contract | Risk | Improvement |
|---|---|---|---|---|
| hooks | state | env vars + JSON | no schema validation | add Pydantic model |
| ... | ... | ... | ... | ... |

Заполнять только реальные связи (не все 7×7 = 49 пар, только существующие).
Каждая строка: одна связь, один риск, одно улучшение.

### Step 4 — Top-3 Bottlenecks

Bottleneck = атом с высокой Importance И низкой Quality И плохими интерфейсами.

Формула отбора (не score, а критерии):
```
bottleneck_score = (Importance ≥ 4) AND (Quality ≤ 2) AND (риски в interface map)
```

Вывод:
```
#1 Bottleneck: <Atom name>
   Почему: <1-2 предложения с evidence>
   Блокирует: <что именно не работает без этого>
   Размер fix: <small/medium/large>

#2 Bottleneck: ...
#3 Bottleneck: ...
```

### Step 5 — Output ONE /goal

Targeting bottleneck #1. Использовать полный /goal template:

```
/goal <END STATE — измеримое условие завершения>.
Run <КОМАНДА ВЕРИФИКАЦИИ> and show full output.
Output must contain: <СТРОКА ПОДТВЕРЖДЕНИЯ>.
Do NOT <CONSTRAINT 1>.
Do NOT <CONSTRAINT 2>.
or stop after <N> turns.
```

Пример:
```
/goal hooks/post_commit_memory.py проходит все тесты без падений.
Run python -m pytest tests/test_post_commit_memory.py -v and show full output.
Output must contain: "passed" and zero "FAILED".
Do NOT modify test assertions.
Do NOT add noqa or type:ignore без обоснования.
or stop after 20 turns.
```

---

## Output Contract (секции в обязательном порядке)

```
1. Project Identity      — 3 строки: что делает, стек, текущий статус
2. Atomic Decomposition  — таблица 5-9 атомов (Atom | Type | Purpose | Evidence | Quality | Importance)
3. Interface Map         — таблица реальных связей (From | To | Contract | Risk | Improvement)
4. Top-3 Bottlenecks     — пронумерованный список с evidence
5. What NOT to Touch     — 3-5 пунктов (защита от scope creep)
6. NEXT /goal            — один executable /goal по bottleneck #1
```

НЕ добавлять: roadmap на 30 шагов, gold standard fantasy, список идей, рекомендации без /goal.

---

## Режим --scan (15 минут)

Только Step 1 + быстрый Step 2 + Step 4 + Step 6. Без interface map.

Вывод:
```
SCAN: <project name>

Atoms (quick):
1. <name> — Quality X/5, Importance X/5
...

Top-3 Bottlenecks:
#1 ...
#2 ...
#3 ...

Quick win (≤2 hours): <конкретное действие>

/goal <...> or stop after 10 turns.
```

---

## Режим --interface

Только Step 3 (расширенная версия). Строит полную матрицу для всех атомов.

Цель: найти broken contracts и missing validation между модулями.

Добавить колонку `Severity` (HIGH/MED/LOW) к каждой строке.

---

## Режим --gold30

Цель: описать gold standard для проекта через 30 дней.
Constraint: no new hires, no new external dependencies без обоснования.

Структура:
```
Gold30 Target: <что должно работать идеально через 30 дней>
Current state per atom: <quality сейчас vs quality нужна>
Gap analysis: <что нужно закрыть>
/goal targeting biggest gap
```

---

## Антипаттерны (что НЕ делать)

| Антипаттерн | Почему плохо | Что вместо |
|---|---|---|
| >9 атомов | Нарушает Miller 1956, теряется фокус | Collapse похожих |
| Composite score (Quality × Importance) | Скрывает tradeoffs — 4×1 = 4×1 = 4, но это разные ситуации | Держать как tuple |
| "Улучшить все bottlenecks" | Нет фокуса = нет прогресса | Только bottleneck #1 в /goal |
| /goal без kill criteria | Агент работает бесконечно | Добавить `or stop after N turns` |
| Атом без evidence | [INFERRED] хуже [UNKNOWN] | file:line или [UNKNOWN] |
| Roadmap вместо /goal | Отчёт ≠ действие | Один /goal, всё остальное — после |

---

## Companion Skills

| Скил | Когда использовать |
|---|---|
| `/orient` | Сначала — для быстрого брифинга, потом /atomize для глубины |
| `/source-distiller` | Если нужно извлечь external методы для сравнения с атомами |
| `/sci-code-audit` | Если нужен audit научного кода (10 layers) — не atomic decomposition |
| `/snr` | Фильтр задач внутри атома — приоритизация, не декомпозиция |
| `/proof-ladder` | После atomize — если bottleneck = научная гипотеза |

---

💡 TIP: запускай /atomize после /orient — orient даёт свежий контекст, atomize строит структуру поверх него.

╔═ ⚡ УРОК ══════════════════════════╗
  Miller (1956) "7±2" — это про рабочую память, не про архитектуру.
  Atomize использует его как cognitive constraint: если ты не можешь
  удержать все атомы в голове одновременно — система слишком сложная
  и нуждается в упрощении до atomize снова.
╚════════════════════════════════════╝
