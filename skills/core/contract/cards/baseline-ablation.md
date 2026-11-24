---
id: baseline-ablation
catalog: 26
title: Проверка новизны: baseline и ablation
family: science-audit
triggers: [baseline, ablation, абляция, превосходит, сравнение методов, новизна, лучше чем]
phrases: [лучше чем baseline, проверь новизну метода, ablation study, превосходит ли]
risk_tier: Green
budget_turns: 45
skills: [sci-evidence, hypothesis-arbiter, stat-validate]
agents: [skeptic, verifier]
verifier: skeptic
statuses: [SUPPORTED, REJECTED, INCONCLUSIVE]
baseline_first: true
gap: нет отдельного скилла; ablation-матрицы нет в Falsification Ladder
---
## Задание
Проверь, действительно ли метод превосходит существующие. Найди сопоставимые baseline, обеспечь одинаковые условия, отключай компоненты по одному и измеряй вклад каждого на независимых запусках.

## Done when
- Матрица «метод x компонент x метрика» с оценкой неопределённости.
- Простейший baseline включён обязательно, потолок (верхняя граница) назван.
- Указано, какие компоненты дают измеримый вклад, а какие нет.
- Вывод «лучше» формулируется только при разнице больше шума независимых запусков.

## Evidence
Таблица результатов, число запусков, интервалы, конфигурации.

## Ловушки
Сложный метод против слабого baseline. Эффект одной детали выдаётся за заслугу всей конструкции.
