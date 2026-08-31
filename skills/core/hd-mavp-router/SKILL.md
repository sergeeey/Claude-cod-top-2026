---
name: hd-mavp-router
sub_type: guide
version: "1.0"
last_tested: "2026-06-10"
description: >
  Роутер для комплексного аудита: выбирает run_mode и оркестрирует нужные скиллы.
  Не повторяет логику скиллов — делегирует. Уникальный вклад: claim-decomposer +
  правила когда нужен полный pipeline vs лёгкий режим.
  Триггеры: /hd-mavp, /audit-full, /hd-mavp-router, "полный аудит утверждения",
  "комплексная проверка", "глубокий аудит проекта", "выбери режим аудита".
tokens: ~200
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : hd-mavp-router
TL;DR  : Роутер аудита: выбирает режим и оркестрирует claim-decomposer + нужные скиллы
Вызов  : /hd-mavp, /audit-full, полный аудит, комплексная проверка
НЕ для : Одиночный шаг (→ соответствующий скилл напрямую); простой вопрос без claim
-->

# HD-MAVP Router — Оркестратор Аудита

## Зачем

Сложный аудит требует нескольких скиллов в правильном порядке. Этот роутер:
1. Классифицирует запрос
2. Выбирает run_mode
3. Запускает скиллы в нужном порядке, передавая контекст

Все claim graph / contradiction работы — в `/claim-decomposer`.
Всё остальное — делегируется специализированным скиллам.

---

## Шаг 0 — Classify

Прежде чем выбирать mode: ответь на три вопроса.

```
Q1: Claim содержит ≥4 суб-утверждений, формулы или код?  yes / no
Q2: Есть конкурирующие гипотезы (несколько объяснений)?  yes / no
Q3: Нужен evidence roadmap (план доказательства)?        yes / no
Q4: Отправная точка — известный провал/null result/аномалия,
    а НЕ уже сформулированный claim?                     yes / no
```

→ Выбери mode из таблицы ниже.

---

## Run Modes

| Mode | Когда | Pipeline |
|------|-------|----------|
| **quick** | Простой claim, ≤3 атома, нет формул | `/claim-decomposer` → gate |
| **full** | Сложный research claim | `/claim-decomposer` → `/sci-evidence falsify` → `/consilience` → `/proof-ladder` |
| **math_code** | Формулы + код + paper | `/claim-decomposer` (с Math-Code Trace) → gate |
| **contradiction** | Conflicting evidence, messy project | `/claim-decomposer` → `/skeptic` → `/hypothesis-arbiter` |
| **decision_record** | Финальный статус / запись в память | `/claim-decomposer` → `/proof-ladder` → `decisions.md` |
| **negative_space** | Q4=yes: нет claim, есть только известный провал/null result/аномалия | `/negative-space-miner` → `/hypothesis-arbiter` (если >1 survivor-гипотеза) → `/novelty-assessment` |

---

## Правило оркестрации (критично)

`claim-decomposer` **всегда** запускается первым и в одном контексте —
**кроме режима `negative_space`**: там по определению (Q4=yes) ещё нет claim'а
для декомпозиции, только провал/аномалия. `negative-space-miner` сам строит
claim (Repair Hypothesis, Этап 4) — именно ЭТОТ claim, если хочешь его
формально декомпозировать позже, идёт в `claim-decomposer` уже ПОСЛЕ, отдельным
циклом, не внутри режима `negative_space`.
Только после Recomposition + Gate Decision — параллельный fan-out по независимым проверкам.

```
ЕДИНЫЙ КОНТЕКСТ (нельзя распараллеливать):
  Context Lock → Claim Register → Atomic Decomposition
  → Contradiction Map → Recomposition → Gate Decision

ПАРАЛЛЕЛЬНЫЙ FAN-OUT (только независимые атомы):
  math consistency | code trace | statistical validity
  empirical support | adversarial critique | literature check
```

Нарушение этого порядка = потеря cross-atom contradictions.

---

## Выход каждого mode

**quick:**
```
ATOMS: [список]
BLOCKERS: [список]
STATUS: HOLD / WEAKEN / PIVOT / KILL
NEXT: [одно действие]
```

**full:**
```
DECOMPOSE_RESULT: [из claim-decomposer]
FALSIFICATION: [из sci-evidence]
CONSILIENCE_SCORE: X/10
EVIDENCE_LEVEL: [из proof-ladder]
FINAL_VERDICT: [Go / Conditional / Stop]
```

**math_code:**
```
ATOM_MAP: [список атомов с типами]
MATH_TRACE: [шаги для каждого формульного атома]
DIVERGENCES: [где теория ≠ код]
VERDICT: CONSISTENT / DIVERGENT / NEEDS_CHECK
```

**contradiction:**
```
CONTRADICTION_MAP: [матрица]
BLOCKING_CONTRADICTIONS: [список]
RESOLUTION: [варианты для каждого]
ARBITER_RESULT: [из hypothesis-arbiter если нужен]
```

**decision_record:**
```
CLAIM_STATUS: [из claim-decomposer]
EVIDENCE_LEVEL: [из proof-ladder]
DECISION: [Go / Conditional / Stop + обоснование]
RECORD_TO: .claude/memory/decisions.md
```

**negative_space:**
```
CONFLICT_MAP: [из negative-space-miner Этапа 2]
CLUSTER: [самый информативный кластер провалов]
REPAIR_HYPOTHESES: [до 5, из Этапа 4]
ARBITER_RESULT: [из hypothesis-arbiter, если survivor-гипотез > 1]
NOVELTY_STATUS: [из novelty-assessment]
```

---

## Полная методологическая архитектура

Детали: `docs/methodologies/HD-MAVP_REFERENCE.md`

Там хранятся: CEVA, EGTS, Anti-Failure Layer, Pearl Registry,
Human Agency Gate, Evidence-Gated synthesis, local-valid/global-fail.

Используй как reference при проектировании новых скиллов или ручном аудите сложных проектов.
