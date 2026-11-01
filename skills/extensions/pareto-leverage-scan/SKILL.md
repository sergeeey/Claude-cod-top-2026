---
name: pareto-leverage-scan
description: >-
  [STATUS: review] [CONFIDENCE: medium] [REVIEWED: 2026-11-01]
  USE when you need to find WHERE in a system most of the impact, problems or value is
  concentrated, before choosing what to fix or build first. Separates two questions that
  are often confused: concentration (where the raw impact sits) and leverage (where a
  controllable intervention buys the most impact per unit of cost). Makes the decision
  falsifiable: ranking must survive a reversal check, and overlap, double counting and
  long tails are checked before any "80/20" claim. Triggers: /pareto-leverage-scan,
  /pareto, "где 80% эффекта", "где концентрация багов", "что оптимизировать первым",
  "топ причин падений", "leverage scan", "impact concentration", "найди узкое место в
  системе", "where should I focus", "найди рычаг". НЕ для: выбора одного варианта из N
  (→ /decision-gate), фильтрации задач дня (→ /snr), security/compliance/safety как
  единственного фильтра (там нужен полный охват).
effort: low
triggers: [/pareto-leverage-scan, /pareto, "где 80% эффекта", "где концентрация багов", "что оптимизировать первым", "топ причин падений", "leverage scan", "impact concentration", "найди узкое место в системе", "where should I focus", "найди рычаг"]
---

# /pareto-leverage-scan

> Не улучшай всё равномерно. Найди малую часть системы, которая даёт большую часть
> результата, проверь это на данных, и только потом действуй там.

## Когда использовать

- Баги: где сконцентрированы падения тестов или инциденты?
- Производительность: какие операции дают основную задержку?
- Рефакторинг: какие модули создают основную часть проблем?
- Research: какие эксперименты дают основную часть информации?
- Продукт: какие фичи или каналы дают основную часть выручки?
- AI-агенты: какие хуки или промпты дают основную часть качества?

## Когда НЕ использовать

- Предметов меньше пяти: сравни вручную.
- Нужно выбрать один вариант из N: `/decision-gate`.
- Нужно понять, что делать сегодня: `/snr` или `/tracy`.
- Security, compliance, safety: Pareto не может быть единственным фильтром, нужен полный охват.

## Определения

- **Метрика (impact_metric)** фиксируется до анализа: numerator, denominator, unit,
  observation window, aggregation. Без неё анализ не начинается.
- **Concentration** — ранжирование по raw unique impact по убыванию. Отвечает на вопрос,
  где сейчас лежит эффект.
- **Leverage** = addressable impact / intervention cost. Addressable impact — та часть
  raw impact, которую можно изменить вмешательством, с учётом controllability и ожидаемой
  эффективности. Отвечает на вопрос, куда вложиться.
- Concentration и leverage не взаимозаменяемы. Самая большая доля не обязательно самая
  выгодная для вмешательства.

## Алгоритм

1. **Зафиксируй систему и метрику.** target_system и impact_metric с полями из раздела
   «Определения». Если метрику нельзя записать так, чтобы её мог проверить другой человек,
   остановись и попроси данные.
2. **Декомпозиция.** Перечисли предметы (модули, фичи, эксперименты, клиенты, хуки).
   Проверь, что они не пересекаются: если один и тот же сбой засчитан в двух предметах,
   impact задвоен. Общую первопричину (upstream cause) выдели отдельным предметом или
   отметь как ограничение.
3. **Измерь raw impact** на каждом предмете. Сумма должна соответствовать total unique
   impact. Если сумма больше, есть double counting; если меньше, есть непокрытый хвост.
4. **Concentration.** Ранжируй по raw impact. Найди минимальный набор, который даёт
   примерно 70–80% total unique impact. Если такого набора нет (эффект равномерный или
   хвост тяжёлый), так и напиши: паттерна концентрации нет.
5. **Leverage** — только для приоритетных предметов из шага 4. Оцени addressable impact и
   intervention cost. Если величины несопоставимы (например, часы и число пользователей),
   не делай численного отношения: используй ordinal HIGH / MEDIUM / LOW и объясни,
   почему число было бы ложной точностью.
6. **Interaction.** Если вмешательства на двух предметах влияют друг на друга, отметь
   уровень взаимодействия LOW / MEDIUM / HIGH. При HIGH ранжирование по отдельности
   недостаточно.
7. **Reversal check.** Для каждого приоритетного предмета найди минимальное правдоподобное
   изменение cost, controllability, effectiveness или attribution, которое меняет порядок
   ранжирования. Если такое изменение мало (порядка ошибки оценки), ранжирование
   неустойчиво, и статус не может быть ACT.
8. **Long tail.** Проверь редкие, но тяжёлые сбои. Предмет с малой долей может быть
   главным риском.
9. **Статус.** Один из четырёх:
   - **ACT**: concentration устойчива, reversal check пройден, evidence HIGH.
   - **VERIFY**: паттерн вероятен, но нужна проверка конкретного предположения.
   - **NEED DATA**: данных не хватает для ранжирования; назови одно измерение, которое
     различит варианты.
   - **SKIP**: концентрации нет или вмешательство не окупается.

## Evidence levels

| Уровень | Источник | Допустимый статус |
|---|---|---|
| HIGH | логи, метрики, тесты, мониторинг | ACT |
| MEDIUM | экспертная оценка с частичными данными | VERIFY |
| LOW | интуиция, единичный сигнал | NEED DATA |
| UNKNOWN | данных нет | NEED DATA, не действовать |

Если evidence ниже MEDIUM или attribution ненадёжна, результат не называется Pareto.

## Формат результата

1. Impact metric (numerator, denominator, unit, window, aggregation)
2. Decomposition validity (пересечения, double counting, upstream, interaction LOW/MEDIUM/HIGH)
3. Impact concentration table (raw impact, доля, ранг)
4. Intervention leverage table (addressable impact, cost, ordinal leverage, evidence level)
5. Reversal check (какое минимальное изменение меняет порядок)
6. Long-tail risk
7. Decision (ACT / VERIFY / NEED DATA / SKIP)
8. First high-leverage action
9. Verification metric (как понять, что стало лучше, и через сколько)
10. Evidence Ledger

## Evidence Ledger

Для каждого существенного вывода:

| Поле | Значение |
|---|---|
| Claim | формулировка вывода |
| Source | файл, лог, команда или тест, из которого взято |
| Level | HIGH / MEDIUM / LOW / UNKNOWN |
| Raw impact | сырое значение или "нет" |
| Addressable impact | значение или "не оценим" |
| Critical assumption | предположение, без которого вывод не держится |
| Reversal condition | что должно измениться, чтобы вывод перевернулся |
| Status | ACT / VERIFY / NEED DATA / SKIP |

## Guardrails

| Guardrail | Зачем |
|---|---|
| Без данных (evidence < MEDIUM) не называть Pareto | иначе это предвзятость в форме анализа |
| Long tail не игнорировать | редкий тяжёлый сбой может быть главным риском |
| Громкость ≠ impact | частая жалоба может не быть главной проблемой |
| Метрику фиксировать до действия | иначе меряем то, что удобно |
| Security, compliance, safety не фильтровать только Pareto | там нужен полный охват |

## Проверка скилла

Перед использованием: ranking должен выдержать reversal check, иначе статус не ACT.
Пример хорошего вывода: «Метрика — failed integration tests за 30 дней, два модуля дают
72% падений при HIGH evidence, reversal check: изменение cost в 2 раза не меняет порядок,
статус ACT, первое действие — тест на таймаут платежа, проверка — число падений за 30
дней после фикса».
