<!-- BSV — Brief Skill View | поиск: BSV
Скил   : research-pipeline
TL;DR  : Сквозной цикл исследования от вопроса до решения: EstimandOps → гипотеза → эксперимент → анализ → вывод
Вызов  : /research-pipeline, исследовательский пайплайн, research pipeline, полный цикл исследования
НЕ для : Одиночного поиска по литературе (→ /literature-review), генерации гипотез без данных (→ /sci-hypothesis)
-->

---
name: research-pipeline
description: >
  Сквозной цикл исследования от вопроса до вывода. Оркестрирует EstimandOps → hypothesis-revival →
  literature-review → sci-hypothesis → experiment-design → анализ → FL decision. Каждый этап питается
  результатом предыдущего — нить не обрывается. Применяй когда нужен полный исследовательский
  маршрут, а не один шаг.
  Triggers: /research-pipeline, исследовательский пайплайн, research pipeline, полный цикл исследования,
  pipeline от вопроса до вывода, сквозное исследование.
  [STATUS: active] [CONFIDENCE: high] [VERSION: 2.0.0]
allowed-tools: Read, Grep, Glob, WebSearch, Bash, Agent
version: "2.0.0"
---

# /research-pipeline — Сквозной исследовательский цикл

> **Принцип:** Ошибка в EstimandOps = потерянный месяц. Ошибка в гипотезе = неверный эксперимент.
> Сквозной цикл ловит эти ошибки на дешёвых этапах, не на дорогих.

```
Вопрос
  ↓
[Feasibility Gate]
  ↓
Step 0: EstimandOps     — что именно измеряем и для кого
  ↓ estimand питает →
Step 1: Поле             — что уже сделано, пробелы
  ↓ пробелы питают →
Step 2: Гипотеза         — что проверяем (revival или новая)
  ↓ гипотеза питает →
Step 3: Дизайн           — как проверить (MCID, controls, power)
  ↓ дизайн питает →
Step 4: Эксперимент      — запуск и сбор данных
  ↓ данные питают →
Step 5: Анализ           — статистика + evidence markers
  ↓ результат питает →
Step 6: Решение          — promote / repeat / reject → null_results/ или paper-assembly
```

---

## Feasibility Gate

Три вопроса до старта:

```
1. Есть конкретный вопрос — не "расскажи о теме", а "X влияет на Y в популяции Z"?
   → НЕТ: сформулируй вопрос, только потом запускай

2. Есть ресурс на полный цикл (≥ несколько дней)?
   → НЕТ: возьми /sci-hypothesis (только гипотеза) или /literature-review (только обзор)

3. Вопрос уже не исследован нами?
   → Проверь: grep -i "keyword" null_results/INDEX.md && grep -i "keyword" parked/INDEX.md
   → НАЙДЕНО: прочти prior decision.md — новая попытка должна объяснять почему предыдущая провалилась
```

---

## Step 0 — EstimandOps (до всего остального)

**Обязателен.** Из `rules/estimand-ops.md`:

```
Тип вопроса:  [ ] Descriptive  [ ] Predictive  [ ] Causal

Population:   [кто именно, inclusion/exclusion criteria]
Intervention: [что именно — версия, конфиг, параметры]
Comparator:   [с чем сравниваем]
Endpoint:     [что измеряем — конкретно, с единицами]
MCID:         [минимальное практически значимое изменение]
ICE:          [intercurrent events — что делать с дропаутами]
```

**Жёсткое правило:** MCID определяется ДО просмотра данных. Если causal вопрос — обязателен DAG + 4 identifiability checks.

**Выход Step 0 → питает Step 1:** список ключевых терминов для поиска + тип estimand.

---

## Step 1 — Поле (что уже сделано)

Два источника параллельно:

### 1a. Наши null_results и parked (сначала)
```bash
grep -i "KEYWORD" null_results/INDEX.md
grep -i "KEYWORD" parked/INDEX.md
```
Если найдено → прочти `decision.md` того эксперимента. Новая попытка должна явно объяснить что изменилось.

### 1b. Литература (OpenAlex + Semantic Scholar)
**→ Делегируй `/literature-review`**

```bash
# OpenAlex: свежие работы по теме
curl -s "https://api.openalex.org/works?search=KEYWORD&filter=publication_year:%3E2020&sort=cited_by_count:desc&per-page=10&select=id,title,publication_year,cited_by_count" \
  | python -c "import json,sys; [print(w['publication_year'], w['cited_by_count'], w['title'][:80]) for w in json.load(sys.stdin).get('results',[])]"
```

### 1c. Sleeping beauties (→ /hypothesis-revival если застряли)
Если проблема известная но решений нет — запусти `/hypothesis-revival` для поиска забытых гипотез pre-2015.

**Выход Step 1 → питает Step 2:** карта пробелов + список кандидатных гипотез.

---

## Step 2 — Гипотеза

На основе пробелов из Step 1 сформулируй фальсифицируемую гипотезу.

**Формат (обязательный):**
```
Гипотеза: Если [условие], то [следствие], потому что [механизм].
Подтверждается если: [критерий — конкретный, измеримый]
Опровергается если: [критерий — конкретный, измеримый]
TOY_TEST_1DAY: [что можно запустить за 1 день чтобы проверить жизнеспособность]
```

Если не можешь сформулировать TOY_TEST_1DAY → гипотеза слишком абстрактная, вернись к Step 0.

**→ Делегируй `/sci-hypothesis`** для генерации вариантов, **→ `/hypothesis-arbiter`** для выбора между конкурирующими.

**Выход Step 2 → питает Step 3:** одна приоритетная гипотеза + критерии.

---

## Step 3 — Дизайн эксперимента

**→ Делегируй `/experiment-design`**

Минимум который должен быть определён:

```
Дизайн:          [RCT / observational / simulation / литературный]
Controls:        Позитивный: [known-good input]
                 Негативный: [known-bad input]
Baseline:        [текущий показатель до вмешательства]
Sample size:     [power analysis: n при α=0.05, power=0.80, MCID из Step 0]
Stopping rule:   [когда останавливаем — заранее, не по результату]
```

**Выход Step 3 → питает Step 4:** готовый план с controls и baseline.

---

## Step 4 — Эксперимент

**→ Делегируй `/experiment-code`** для генерации кода.

Перед запуском:
```bash
# Зафиксировать baseline
echo '{"timestamp": "NOW", "baseline_metric": VALUE, "hypothesis": "..."}' > experiments/YYYYMMDD-slug/baselines/baseline.json

# Запустить позитивный control первым
# Если позитивный control не работает → STOP, проблема в тесте, не в гипотезе
```

**Выход Step 4 → питает Step 5:** `metrics/run.json` с сырыми результатами.

---

## Step 5 — Анализ

**→ Делегируй `/ab-test`** (если A/B) или **`/validate`** (если другой дизайн).

Обязательные маркеры на каждый claim:
- `[VERIFIED-REAL]` — результат из реальных данных с источником
- `[VERIFIED-SYNTHETIC]` — синтетические данные (только для unit tests, не для валидации гипотезы)
- `[INFERRED]` — вывод из результатов (с цепочкой рассуждений)

**Degeneracy-чек:** F1 > 0.95 или R² > 0.99 → первый вопрос "что вырождается?", не "как хорошо!"

**Skeptic-триггер:** если "все тесты прошли" или "100% успех" → обязательно `/skeptic` перед Step 6.

**Выход Step 5 → питает Step 6:** `result_summary.md` с evidence markers.

---

## Step 6 — Решение (FL decision)

Заполнить `experiments/YYYYMMDD-slug/decision.md`:

| Результат | Действие |
|---|---|
| Гипотеза подтверждена + MCID достигнут | **PROMOTE** → `/paper-assembly` или в production |
| Гипотеза подтверждена, MCID не достигнут | **REPEAT** с большей выборкой или другим дизайном |
| Гипотеза опровергнута | **REJECT** → `null_results/YYYYMMDD-slug.md` + `null_results/INDEX.md` |
| Результат неоднозначный | **ARCHIVE** → `parked/YYYYMMDD-slug.md` + условие для возврата |

**REJECT → обязательно:**
```bash
# Скопировать decision.md в null_results
cp experiments/YYYYMMDD-slug/decision.md null_results/YYYYMMDD-slug.md
# Добавить строку в INDEX
echo "| YYYYMMDD | $(date +%Y-%m-%d) | slug | REJECT | почему провалилось (10 слов) |" >> null_results/INDEX.md
```

**PROMOTE → если публикация:**
Обязателен **Submission Gate** из `rules/integrity.md` (4 проверки: skeptic + checklist + text↔figures + 24h cooling).

---

## Обязательный выход

```markdown
## Research Pipeline: [название]
Вопрос: [formulated question]
Estimand: [population / intervention / comparator / endpoint / MCID]

### Step 0: [тип вопроса + estimand]
### Step 1: [пробелы в поле + null_results check]
### Step 2: [гипотеза + TOY_TEST]
### Step 3: [дизайн + controls + baseline]
### Step 4: [результаты эксперимента]
### Step 5: [анализ с evidence markers]
### Step 6: [PROMOTE / REPEAT / REJECT / ARCHIVE + обоснование]

### Что этот результат НЕ означает:
1. [non-interpretation 1]
2. [non-interpretation 2]
3. [non-interpretation 3]
```

---

## Связанные скиллы (оркестрация)

| Step | Скилл |
|---|---|
| 0 | `estimand-ops` (rule) |
| 1 | `/literature-review`, `/hypothesis-revival` |
| 2 | `/sci-hypothesis`, `/hypothesis-arbiter` |
| 3 | `/experiment-design` |
| 4 | `/experiment-code` |
| 5 | `/ab-test`, `/validate`, `/skeptic` |
| 6 | `falsification-ladder` (rule), `/paper-assembly` (если PROMOTE) |
