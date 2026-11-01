---
name: estimand-l0-gate
description: "Лёгкий шаг перед estimand-bridge: классифицирует вопрос (Descriptive/Predictive/Causal) и материализует минимальный estimand.md ПРЯМО ИЗ claim'а, когда готового файла ещё нет. Не дублирует estimand-bridge — тот проверяет ПО estimand.md и генерит вопросы Skeptic'у; этот шаг ЗАПОЛНЯЕТ estimand.md, если он ещё не существует. Используется как шаг workflow scientific-hypothesis.yaml перед claim-decomposer/estimand-bridge, не как самостоятельный вызов пользователем. НЕ для: анализа уже существующего estimand.md (это estimand-bridge), полного Full-tier канваса с DAG (это остаётся за claim-decomposer + estimand-bridge для causal-случая)."
triggers: ["estimand-l0-gate"]
allowed-tools: Read, Write, Glob
tokens: ~700
type: directory
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : estimand-l0-gate
TL;DR  : Классифицирует вопрос + пишет минимальный estimand.md, если его ещё нет
Вызов  : шаг workflow scientific-hypothesis.yaml, перед estimand-bridge
НЕ для : анализа уже существующего estimand.md (→ /estimand-bridge)
-->

# Estimand L0 Gate — материализация estimand ДО моста

## Зачем этот скилл существует

`estimand-bridge` читает `estimand.md` и генерит проверки под него — но сам его не создаёт.
Его собственная инструкция: "Если estimand.md нет или MCID/ICE — плейсхолдеры → **СТОП**".
Для свежего ad-hoc вопроса (только что заданной гипотезы, ещё без папки `experiments/<id>/`)
estimand.md физически не может существовать — значит мост стопорится на первом же реальном
вызове. Найдено живьём 2026-09-06: реальная multi-hypothesis фраза, прогнанная через
`resolve_route.py`, дошла до `estimand-bridge` без единого `estimand.md` на диске.

Это НЕ чинит `estimand-bridge` (он используется другими вызывающими, трогать его контракт
рискованно) — это ставит шаг ПЕРЕД ним, который делает ровно то, что estimand-bridge
предполагает как один из двух вариантов входа в своих preconditions ("estimand.md exists
OR estimand fields are derivable from the claim") — но раньше НИЧТО не выполняло вторую
половину этого OR на практике.

## Шаг 0 — Определить, нужен ли этот шаг вообще

Если `experiments/<id>/estimand.md` уже существует и не placeholder — **пропустить**,
сразу к `estimand-bridge`. Этот скилл — только для случая "файла ещё нет".

## Шаг 1 — Classify (EstimandOps L0)

Классифицируй вопрос по `~/.claude/rules/estimand-ops.md`:

| Тип | Форма | Ограничение |
|---|---|---|
| Descriptive | "что есть X в популяции P" | без каузальной интерпретации |
| Predictive | "каким будет X для нового случая" | без каузальной интерпретации |
| Causal | "что изменится, если сделать A" | нужен DAG + 4 проверки идентификации — это делает `claim-decomposer`/`estimand-bridge` следующим шагом, не этот |

## Смешанные claim-ы (проверить до Шага 2)

Если claim содержит несколько утверждений разного типа (например, «модель лучше по точности, потому что B, и эффект больше при C»), один общий estimand скрывает разные вопросы. Сначала декомпозиция (`claim-decomposer`), затем L0 отдельно для каждого атома, на который опирается вывод.

## Шаг 2 — Минимальный контракт по типу вопроса

Заполняй контракт, соответствующий типу из Шага 1. Опирайся ТОЛЬКО на текст claim'а, без придуманных чисел.

**Descriptive** (что есть X в популяции P):
population · quantity · time_window · measurement_definition · summary_measure · precision_target · scope_limits

**Predictive** (каким будет X для нового случая):
target_population · prediction_time · prediction_horizon · outcome · information_available_at_prediction · target_quantity · performance_target · deployment_context

**Causal** (что изменится, если сделать A):
population · intervention · comparator · outcome · time_horizon · summary_measure · intercurrent_events (ICE + strategy) · causal_contrast

Поля других типов не требуются: для descriptive и predictive ICE и intervention/comparator не заполняются.

### Порог, значимый для решения (вместо универсального MCID)

У descriptive и predictive вопросов может не быть MCID: для них значимы calibration error, Brier score, precision width и т.п. Поэтому поле называется `decision_threshold` и имеет статус:

| Статус | Что значит | Что может делать estimand-bridge |
|---|---|---|
| `QUANTIFIED` | порог задан числом | механически проверяет результат ≥ порог |
| `QUALITATIVELY_DEFINED` | порог описан словами | не проверяет механически; вывод НЕ получает PASS по этому пункту |
| `NOT_APPLICABLE` | порога нет по природе вопроса | требует обоснования в одну строку |
| `UNRESOLVED` | порог не определён | estimand-bridge останавливается |

**Запрещено:** записывать словесный порог («качественный сдвиг X») и считать поле заполненным. Такой текст выглядит полным, но downstream-правило «результат ≥ порог» применить нельзя: это ложная полнота.

**ICE:** только для causal. Для остальных типов поле не заполняется, и это не placeholder.

**Жёсткое правило:** «TBD», «N/A» без обоснования и пустая строка — это placeholder, и estimand-bridge остановится. «ICE не применимо, потому что вопрос не имеет постбейзлайн-фазы» — заполненное поле с обоснованием.

Scope: этот шаг не выбирает estimator и не проверяет гипотезу. Он делает вопрос достаточно определённым для следующего шага.

## Шаг 3 — Natural Language Statement + "что это НЕ значит"

Одно предложение-эстиманд (как в `estimand-ops.md`) + минимум 2 пункта "что результат НЕ будет означать" — пишутся ДО результатов, не после.

**Статус файла:** `draft_l0` до прохождения проверки структуры по типу вопроса. estimand-bridge принимает только материализованный файл, а не `draft_l0`.

## Шаг 4 — Записать estimand.md

Определи `<id>` (дата + короткий слаг из claim'а, тот же формат что `experiments/<id>/`).
Создай `experiments/<id>/estimand.md` с полями из Шагов 1-3. Если папка `experiments/<id>/`
уже существует (например, claim-decomposer уже начал работу и создал её) — писать туда же,
не создавать вторую.

## Чем НЕ является

Не заменяет полный Full-tier канвас `estimand.md` (DAG, идентификация для causal — это
дальше по цепочке). Не решает, GO или NO-GO — это работа `estimand-bridge` дальше. Если
на Шаге 2 честно выясняется, что claim слишком расплывчатый для даже минимальных полей
(нет endpoint, нет направления эффекта) — это Zero-Signal Gate находка, о ней нужно сказать
прямо, а не выдумывать поля лишь бы файл записался.

## Связанные

- `rules/estimand-ops.md` — полный протокол, откуда эти поля
- `estimand-bridge` — следующий шаг, читает то, что этот скилл написал
- `claim-decomposer` — для causal claims сам ожидает "DAG + estimand до шага 1" (см. его Шаг 0)
