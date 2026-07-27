# Reference-Grade Architectural Coupling Assessment

Дата: 2026-07-16 · Субъект: repo-fresh @ `3f2807beb13ea134255baa5f3d1860d0ad99b3f1`
(канонический клон sergeeey/Claude-cod-top-2026) · Режим: research-first, read-only.

## 1. Executive Summary

См. [00-executive-summary.md](00-executive-summary.md). Кратко: structural coupling уже
near-reference (0 циклов, 3 production межмодульных ребра, направление к стабильному ядру);
стоимость изменений сосредоточена в change- и data-каналах (дубли счётчиков, общий mutable
store, god-utility). Вердикт: **proceed_with_caution**, Option A → B, C — reject.

## 2. Environment Passport

См. [01-environment-passport.md](01-environment-passport.md). Python 3.11+ хуки (91) +
Markdown-знания (123 skills); event-driven (25 событий, 88 регистраций); 1 deployment unit;
файловые контракты вместо сети; single developer.

## 3. Определение эталонной связности

Для данного проекта reference-grade означает: <gate>(а) 0 циклов (достигнуто, закрепить);
(б) каждое cross-boundary ребро имеет причину, выраженную контрактом (import-linter / schema /
инвариант-тест), а не привычкой; (в) у каждого shared store — один владелец записи;
(г) счётчики/метадата имеют один источник истины; (д) метрики пересчитываемы и трендируются
(fitness №14); (е) изоляция не покупается ценой ненаблюдаемости (общий лог сохраняется).</gate>

## 4. Научные и индустриальные источники

29 источников, все VERIFIED: [03-source-matrix.csv](03-source-matrix.csv);
разбор — [02-research-evidence.md](02-research-evidence.md). Состав: 14 peer-reviewed/seminal,
5 official docs, 5 книг, 5 production case studies. Spot-check 3/3 [VERIFIED-WebFetch].

## 5. Подтверждённые факты

- <fact>215 .py, 238 import-рёбер, SCC>1 = 0 (циклов нет)</fact> [VERIFIED-ast+networkx]
- <fact>utils.py: fan-in 74, 61 клиент, 34 символа, медиана 3 имени/клиента, 1074 LOC</fact> [VERIFIED-ast]
- <fact>Топ co-change: plugin.json↔README 28, README↔architecture.md 24, marketplace↔README 22; исторические инциденты дрейфа счётчиков: «87 vs 88» (docstring test_structure.py) и cf32d7f («88→89 sweep missed header»)</fact> [VERIFIED-git]
- <fact>.claude/memory/ — 32 файла-клиента; activeContext.md: 7 write-capable + 6 читателей</fact> [VERIFIED-grep]
- <fact>Louvain: Q=0.4107–0.4153, 9 кластеров, стабильность 0.981–1.0 по 5 seeds; directory-partition Q≈−0.0008</fact> [VERIFIED]
- <fact>Jaccard(static, co-change) = 0.121; 43 co-change-пары без static-ребра</fact> [VERIFIED-git]
- <fact>10 незарегистрированных не-библиотечных хуков; 88 регистраций на 25 событий</fact> [VERIFIED-json]

## 6. Инженерные выводы

<inference>(1) Изоляция без контрактов не устраняет coupling — перегоняет его в скрытые каналы
(файлы, литералы). (2) Плоский layout прячет 9 устойчивых доменов — структура должна быть
выражена пакетами и контрактами, не памятью maintainer'а. (3) Единственный работающий
fitness-прецедент репо (count-gate) родился из инцидента — остальной набор правил (11) строится
по тому же принципу: правило ← измеренный инцидент/hotspot, не «best practice» из воздуха.</inference>

## 7. Непроверенные гипотезы

<hypothesis>H-a: FP-rate count-gate < 10% (Exp F, требуется прогон по истории).
H-b: file_lock-дисциплина достаточна на NTFS (Exp E).
H-c: split utils по 4 группам даст медиану 1 sublib/клиента (Exp C, gate задан).
H-d: генерация счётчиков снизит co-change plugin↔README минимум вдвое за 10 коммитов (Волна 3).</hypothesis>

## 8. Противоречия источников

Contradiction matrix — [02-research-evidence.md](02-research-evidence.md) §3 (микросервисы
vs консолидация; трактовка Prime Video; валидность cohesion-метрик; monorepo-эффекты).

## 9. Архитектура текущего проекта

Карта и 5 графовых представлений: [04-current-architecture-map.md](04-current-architecture-map.md).

## 10. Baseline Metrics

[05-metrics-baseline.md](05-metrics-baseline.md); машинно:
artifacts/architecture-coupling/coupling-metrics.json.

## 11. Dependency Structure Matrix

artifacts/architecture-coupling/dependency-structure-matrix.csv. Содержательный уровень DSM —
внутрихуковые домены; top-dir DSM тривиальна (3 ребра) — честно зафиксировано, не имитировано.

## 12. Structural, Runtime, Data and Change Coupling

Structural: near-reference. Change: главный канал (docs/manifests). Data: shared mutable store.
Runtime: **unavailable** — production-телеметрии нет; static analysis не выдаётся за runtime.

## 13. Cohesion Analysis

LCOM отвергнут обоснованно (T4–T6b + отсутствие классов); прокси: change cohesion,
responsibility count utils (4), семантическая согласованность словаря (08). См. 05 §10.2.

## 14. Graph Clustering Results

[07-clustering-analysis.md](07-clustering-analysis.md): 3+ алгоритма, протокол seeds,
стабильность, resolution limit учтён; Louvain C0 = демонстрация недостаточности graph-only.

## 15. DDD and Semantic Boundary Analysis

[08-ddd-boundary-analysis.md](08-ddd-boundary-analysis.md): glossary (термин «memory» перегружен
4 смыслами — документированный источник ошибок), 6 bounded contexts, context map, data ownership
matrix, транзакционные границы.

## 16. Architectural Hotspots

11 hotspots: [06-hotspots.md](06-hotspots.md) + artifacts/architecture-coupling/hotspots.json.

## 17. Target Architecture Options

[09-target-options.md](09-target-options.md): A conservative / B moderate / C aggressive
с полной оценочной таблицей и Pareto-сводкой.

## 18. Recommended Architecture

**A немедленно → B волнами** (modular monolith, package-by-domain, memory-API, env-facade),
**C — reject** при текущей deployment-модели. Основание: каждый пункт A/B бьёт в измеренный
hotspot; C не поддержан ни одним verified-фактом и противопоказан кейсами C2/C4.

## 19. Falsification Experiments

[10-experiment-plan.md](10-experiment-plan.md). Выполнено: A (graph-only — **опровергнут**),
D (static≠change, Jaccard 0.121 — сильная форма **опровергнута**), F частично (2/2 инцидента
поймано бы). Спроектировано с gates: B, C, E, F-FP.

## 20. Architectural Fitness Functions

[11-fitness-functions.md](11-fitness-functions.md): 14 правил, baseline, режимы
observe→warn→calibrate→block, exception process; блокировка по непройденному baseline исключена.

## 21. Refactoring Roadmap

[12-refactoring-roadmap.md](12-refactoring-roadmap.md): 10 волн, каждая с измеримым эффектом,
verification, rollback, stop conditions; big-bang отсутствует.

## 22. Risk Register

[13-risk-register.md](13-risk-register.md): 14 рисков, включая специфичные (Windows file_lock,
стейл-копии в workspace, потеря writer'а лога при split).

## 23. Unknowns and Missing Evidence

- <unknown>Runtime coupling: нет production traces/metrics — все runtime-утверждения design-time. Что требуется: включить hook_metrics/otel_exporter на живой машине владельца ≥2 недели.</unknown>
- <unknown>FP-rate count-gate: нужен backtest-прогон по 20 историческим doc-коммитам (git worktree).</unknown>
- <unknown>Полнота write-детекции: эвристика file-level (write-op где-либо в файле) может завышать число «писателей» activeContext; уточнение — AST data-flow по каждому open/write.</unknown>
- <unknown>Динамические импорты/exec не покрыты AST-сканом; контроль — прогон Grimp в изолированном окружении.</unknown>
- <unknown>Содержание платных книг (B1, B3) подтверждено по TOC/вторичным конспектам — [DOCS], не [VERIFIED-full-text].</unknown>
- <unknown>Расхождение рабочей копии Claude-cod-top-2026-main/ с каноном repo-fresh — владельцу решить, какая копия живая.</unknown>

## 24. Final Verdict

```text
proceed_with_caution
```

Архитектура НЕ объявляется эталонной: подготовлены и верифицированы **рекомендации и baseline**,
рефакторинг не выполнялся (implementation_mode: false). «Caution» = три P1-hotspot'а с
доказанной историей инцидентов (HS-01/02/03) и отсутствующий runtime-слой доказательств.

## 25. Confidence Report

<confidence>
0.78 — источники: 29/29 VERIFIED (3 полных spot-check, остальные — метаданные+агентная
верификация); repository evidence: полное, воспроизводимое (fixed seeds, commands.log,
tool-versions.txt); измерения: детерминированы; понижают оценку: недоступный runtime-слой,
эвристичность write-детекции и оценок E_arch, 6 unresolved unknowns (§23).
</confidence>
