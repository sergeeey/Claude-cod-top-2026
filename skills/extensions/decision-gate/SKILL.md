---
name: decision-gate
description: >
  USE when you need to choose the best option from N candidates and the risk of choosing
  too early OR exploring too long is real. Works across ALL domains: code (bug hypotheses,
  architectures, libraries), science (which experiment to run, which mechanism to test,
  limited GPU/compute budget), research (competing physical frameworks, spectral algorithms,
  preprocessing strategies), founder (which project/feature to invest in, 30-day commercial
  filter). Implements optimal stopping (37% rule) as a 5-gate protocol with mode-specific
  scoring. ALWAYS invoke when: "выбор между N вариантами", "с чего начать проверку",
  "какой эксперимент", "limited compute budget", "несколько механизмов",
  "какую гипотезу тестировать первой", "founder choice", "приоритизировать из N",
  "какой алгоритм выбрать", или /decision-gate typed explicitly.
  Do NOT use for: single candidate, obvious fix, exhaustive audit (security/legal),
  deep analysis of one hypothesis already chosen (→ /hypothesis-arbiter after this).
effort: medium
tokens: ~600
triggers: [decision-gate, /decision-gate, decision, gate]
---

# /decision-gate — Оптимальная остановка для любого выбора из N

> **Проблема:** без структуры либо выбираешь первый подходящий (слишком рано),
> либо исследуешь всё до конца (слишком дорого). Математически обоснованный баланс —
> исследуй 37%, потом выбирай первое что лучше. Работает для кода, науки, бизнеса.

## Когда НЕ использовать

- N < 3 → просто сравни вручную
- Один очевидный вариант → реши напрямую
- Все варианты ОБЯЗАТЕЛЬНЫ (security audit, legal) → exhaustive review
- Гипотеза уже выбрана, нужен глубокий анализ → `/hypothesis-arbiter`
- Планирование задач дня/недели → обычный планировщик, не этот скилл

---

## Режимы — выбрать по контексту

| Режим | Типичные кандидаты | Verification | Primary criterion (< 7 → ESCALATE) |
|-------|-------------------|--------------|-------------------------------------|
| **bugfix** | Root cause гипотезы | failing test → green | Correctness |
| **refactor** | Стратегии переработки кода | no behavior change + tests pass | Correctness |
| **architecture** | Design patterns / подходы | prototype/spike passes | Fit to requirements |
| **dependency** | Библиотеки / инструменты | integration spike | Fit to requirements |
| **optimization** | Bottlenecks / узкие места | benchmark improvement | Correctness |
| **experiment** | Эксперименты при ограниченном GPU/времени/токенах | falsifiable prediction confirmed | Falsifiability |
| **claim** | Физические механизмы / scientific claims к проверке | cheapest falsification test passes | Falsifiability |
| **founder** | Фичи / проекты / пивоты | клиентский сигнал ИЛИ 30-day revenue test | 30-day revenue signal |

`primary_criterion` — это критерий из колонки выше. Используется в алгоритме (Шаг 4 FALLBACK) и в G3/G5.

---

## Алгоритм (ядро — одинаков для всех режимов)

```
Шаг 1: N = количество кандидатов (задай явно)
Шаг 2: exploration_limit = ceil(N × 0.37)
        [deadline/кризис → 0.25; высокая цена ошибки → 0.50]
Шаг 3: Оцени кандидатов 1..exploration_limit → запиши benchmark:
         benchmark_holder = кандидат с max(score)
         threshold = score benchmark_holder
Шаг 4: Продолжай с кандидата exploration_limit+1..N →
         первый кто beats threshold → ВЫБРАН → Gate 4
         если никто не beat → FALLBACK: benchmark_holder если primary_criterion ≥ 7
                              иначе → ESCALATE
Шаг 5: Verification gate → ACCEPT / HOLD / SKIP / ESCALATE
```

**Важно:** в малых пулах (N=4-6) лучший кандидат часто попадает в exploration фазу.
FALLBACK к benchmark_holder — это стандартный путь, не крайний случай.

---

## 5 Gate-ов (пройти по порядку)

| Gate | Проверка | Fail action |
|------|----------|-------------|
| **G1 exploration_gate** | Не выбирать ДО exploration_limit | Продолжай исследование |
| **G2 benchmark_gate** | Benchmark записан ДО selection phase | Вернись, запиши best из фазы 1 |
| **G3 selection_gate** | Кандидат beats benchmark. Если никто → fallback к benchmark_holder если primary_criterion ≥ 7 | SKIP → следующий; ESCALATE если пул исчерпан и primary_criterion < 7 |
| **G4 verification_gate** | Проходит verification для режима (см. таблицу режимов выше) | HOLD → исправить и re-verify |
| **G5 rollback_gate** | Если reversibility присутствует в скоринге режима и < 7 → нужен rollback plan. Для режимов без Reversibility (claim) — проверь: можно ли отменить действие? Если нет → rollback plan обязателен | Зафиксируй rollback перед ACCEPT |
| **G6 sensitivity_gate** | Если разрыв между #1 и #2 < 1.5 балла → запусти weight perturbation: топ-критерий ×1.2 / ×0.8 → winner меняется? ДА → HOLD (нестабильное решение). НЕТ → proceed. Пропустить если разрыв ≥ 1.5 или N=2. | HOLD: уточни приоритеты или собери доп. evidence |
| **G7 voi_gate** | Срабатывает при HOLD из G3 / G4 / Unknown Penalty. Назначь один probe: минимальный тест который (1) differentiates топ-2 кандидатов, (2) стоит < 10% бюджета, (3) даёт чёткий PASS/FAIL → вернись к G3. Пропустить если ACCEPT или ESCALATE на G3-G6. | Назначь VoI probe → выполни → re-evaluate G3 |

---

## Unknown Penalty (применять до финального score)

Если по критерию нет данных → не ставь "среднюю 5", а маркируй `[?]` и вычти штраф:

| Неизвестных [?] | Штраф | Статус |
|-----------------|-------|--------|
| 0 | 0 | норм |
| 1 | −0.2 | допустимо |
| 2–3 | −0.5 | HOLD если winner |
| ≥4 | −1.0 | NEED DATA |

**Правило:** кандидат с ≥3 [?] не может получить ACCEPT — статус HOLD до заполнения данных.

---

## VoI Probe (применять когда G7 срабатывает)

Когда решение заблокировано — не "надо подумать", а конкретная проверка.

| Тип неизвестного | Cheapest probe |
|-----------------|----------------|
| Производительность неясна | микробенчмарк (5 мин) |
| Риск библиотеки неясен | минимальный integration spike |
| Причина бага неясна | воспроизводящий failing test |
| Физический механизм неясен | cheapest falsification test (< 4ч) |
| Архитектурная неизвестность | tiny vertical slice |
| Рыночный сигнал неясен | один звонок / лендинг за 24ч |

**Формат (записать в output):**
```
Probe: [что именно проверить — одно действие]
Cost: [время / compute]
Differentiates: [как результат меняет решение — A побеждает или B?]
Decision after probe:
  PASS → ACCEPT [кандидат]
  FAIL → SKIP / ESCALATE
```

**Правило:** если результат probe не меняет решение между топ-2 кандидатами — это не VoI probe, это занятость. Выбери другой probe.

---

## Скоринг — по режиму (10-балльная взвешенная шкала)

### Код: bugfix / refactor / optimization

| Критерий | Вес | Вопрос |
|----------|-----|--------|
| Correctness | 30% | Решает проблему полностью? |
| Simplicity | 20% | Минималистичен и понятен? |
| Testability | 15% | Легко проверить автоматически? |
| Reversibility | 10% | Можно откатить? |
| Performance | 10% | Не создаёт новых bottlenecks? |
| Maintainability | 10% | Легко поддерживать? |
| Security/Risk | 5% | Нет новых уязвимостей? |

**Жёсткое правило:** Correctness < 7 → нельзя ACCEPT даже если остальное отлично.

### Код: architecture / dependency

| Критерий | Вес | Вопрос |
|----------|-----|--------|
| Fit to requirements | 25% | Решает ли задачу в нашем конкретном контексте? |
| Reversibility | 20% | Можно мигрировать обратно если не подойдёт? |
| Testability | 15% | Легко покрыть тестами? |
| Simplicity | 15% | Минимальная ли сложность для нашего use-case? |
| Security/Risk | 15% | Нет известных уязвимостей / abandoned статус? |
| Maintainability | 10% | Активная поддержка, хорошая документация? |

### Наука: experiment (GPU / compute / token budget)

| Критерий | Вес | Вопрос |
|----------|-----|--------|
| Falsifiability | 35% | Есть чёткий PASS/FAIL критерий? |
| Info gain / cost | 25% | Информация на единицу GPU-часа / токена? |
| Cheapest test | 20% | Это минимальный тест для данной гипотезы? |
| Reversibility | 10% | Можно остановить и перенаправить бюджет? |
| Independence | 10% | Не дублирует уже проверенное? |

**Жёсткое правило:** Falsifiability < 7 → не запускай. Сначала сформулируй чёткий FAIL-критерий.
**После ACCEPT:** сформулируй claim и контрольные тесты письменно, затем запусти эксперимент.

### Наука: claim (физические механизмы / scientific claims)

| Критерий | Вес | Вопрос |
|----------|-----|--------|
| Falsifiability | 35% | Конкретный falsification test существует? |
| Impact if true | 25% | Что меняется в модели если подтверждено? |
| Test cost | 20% | Можно проверить за < 4ч / 1 сессию? |
| Independence | 10% | Независим от других одновременно проверяемых? |
| Setup correctness | 10% | Нет ошибок в постановке теста? |

**Интеграция:** claim ACCEPT → подробный анализ выбранной гипотезы или запуск самого дешёвого falsification-теста.

### Бизнес: founder (проект / фича / пивот)

| Критерий | Вес | Вопрос |
|----------|-----|--------|
| 30-day revenue signal | 35% | Можно продать / получить клиентский сигнал за 30 дней? |
| Time to first signal | 25% | Как быстро получишь ответ рынка? |
| Feasibility | 20% | Реально сделать за один спринт? |
| Reversibility | 10% | Можно закрыть без потери всего? |
| Customer pain evidence | 10% | Кто-то уже платит за эту боль? |

**Жёсткое правило:** 30-day revenue signal < 6 → это не founder-решение сейчас, это research.
**После ACCEPT:** конкретный шаг на 30 минут + дата следующего checkpoint.

---

## Claude Code — специфические улучшения

### Cheapest Test First (bugfix режим)
В exploration фазе тесты дешевеют по лестнице:
1. `grep/Grep` — секунды, 0 compute
2. `git log --follow <file> --oneline -10` — история изменений
3. `git blame <file> -L <line>,<line>` — кто и когда менял строку
4. Minimal reproduction — 5-строчный тест-кейс
5. Full pytest run — только для ACCEPT (G4)

НЕ запускай полный тест-сьют для гипотез exploration фазы.

### Git Blame Integration (bugfix)
Когда гипотеза о регрессии (что-то сломалось после изменения):
- Если гипотеза соответствует последнему коммиту в файле → **+2 к Correctness (max 10/10)**
- `git show <commit>` перед тестированием этой гипотезы

### Config/CI compatibility (architecture/dependency)
Если ACCEPT затрагивает конфигурацию или CI:
- G5 rollback_gate **обязателен** (нет исключений)
- Rollback plan = `git stash` или revert-коммит
- Перед ACCEPT: тесты проекта должны пройти

---

## Обязательный output-формат

```
## Decision Gate — [режим] — [дата]

### Контекст
Задача: [что выбираем]
N кандидатов: [список]
Бюджет/ограничение: [время / GPU / токены / деньги или N/A]

### Фаза 1: Исследование (кандидаты 1..ceil(N×0.37))
| # | Кандидат | Primary criterion | Score /10 | Статус |
|---|----------|-------------------|-----------|--------|
| 1 | ...      | X/10              | Y.Y       | explored |

**Benchmark lock:** кандидат #N — score Z.Z / threshold Z.Z

### Фаза 2: Выбор (кандидаты ceil(N×0.37)+1..N)
| # | Кандидат | Score /10 | beats benchmark? | Статус |
|---|----------|-----------|-----------------|--------|
| 3 | ...      | Y.Y       | ✅/❌            | SELECTED/SKIP |

### Gates
- G1: ✅ (exploration_limit = K)
- G2: ✅ (benchmark = Z.Z)
- G3: ✅/❌ / SECONDARY PATH (fallback к benchmark_holder, correctness=X)
- G4: ✅/❌ ([что проверено])
- G5: ✅/❌ ([rollback plan или N/A])
- G6: ✅/SKIP/HOLD ([разрыв X.X; perturbation: winner стабилен/нестабилен])
- G7: ✅/SKIP/PROBE ([probe: X / cost: Y / PASS→ACCEPT кандидат, FAIL→SKIP])

### Решение: **ACCEPT / HOLD / ESCALATE**
Выбранный: [название]
Причина: [1 строка]
Следующий шаг: [конкретное действие: запустить / передать в FL / hypothesis-arbiter / 30-min action]
Rollback: [как откатить или N/A]
```

---

## Вердикты

| Вердикт | Значение | Следующее действие |
|---------|----------|--------------------|
| **ACCEPT** | Прошёл все 5 gates | Применить + зафиксировать rollback |
| **HOLD** | G4 не пройден, но кандидат перспективен | Исправить blockers, re-verify |
| **SKIP** | Не beats benchmark | Следующий кандидат |
| **ESCALATE** | Все SKIP + primary_criterion < 7 | Расширить пул или пересмотреть критерии |

---

## Связанные скиллы (полная цепочка)

```
/decision-gate       ← "какой из N выбрать?" (этот скилл)
/hypothesis-arbiter  ← глубокий анализ выбранной гипотезы (после ACCEPT в claim/research)
/experiment-design   ← дизайн выбранного эксперимента (после ACCEPT в experiment)
/ab-test             ← "правильно ли выбрали?" — статистика после deployment
/pre-mortem          ← risk analysis перед high-stakes ACCEPT
```

**Интеграция:** claim ACCEPT → письменно зафиксируй claim и контрольные тесты, затем запусти эксперимент.

---

## Примеры по контекстам

**Код — bugfix (N=5 гипотез, exploration_limit=2):**
Гипотезы 1-2 → cheapest test (grep, git blame). Benchmark → с гипотезы 3: первая что beat threshold → minimal reproduction → ACCEPT → pytest.

**Наука — claim (N=4 механизма, exploration_limit=2):**
Скор по falsifiability + test cost. С механизма 3: первый с чётким FAIL-критерием и cheapest test < 4ч → ACCEPT → FL Standard.

**Эксперимент — GPU budget (N=6 preprocessing стратегий, exploration_limit=3):**
Скор по info_gain/GPU-час. Первый что beats threshold → запустить. Если никто → fallback к лучшему из exploration фазы если falsifiability ≥ 7.

**Founder — фича (N=4 идеи, exploration_limit=2):**
Скор по 30-day revenue signal. С фичи 3: первая с клиентским сигналом < 30 дней → спринт.
