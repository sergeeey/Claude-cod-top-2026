# 05 — Metrics Baseline

Все значения [VERIFIED] (artifacts/architecture-coupling/coupling-metrics.json, HEAD `3f2807b`).
Правило обработки `Ca+Ce=0`: I = null (не 0 и не 1) — модуль вне графа зависимостей.

## 10.1 Structural coupling

| Метрика | Значение | Комментарий |
|---|---|---|
| Python files | 215 | hooks 91 · scripts 29 · tests 88 · .claude/* 7 |
| import edges (file-level) | 238 | |
| dependency_cycles / SCC>1 | **0 / 0** | лучший показатель baseline; фиксируется fitness-правилом №1 |
| module I (Martin) | hooks: Ca=2 Ce=0 **I=0.0** · scripts: 1/1 I=0.5 · tests: Ce=2 **I=1.0** | направление корректно: unstable→stable |
| fan-in top | utils.py **74** · hook_state.py 10 · input_guard.py 9 | звезда; HS-01 |
| fan-out top (файлы) | тесты-агрегаторы; в production-коде fan-out ≤ 5 | |
| cross_boundary_edges (top-dirs) | 762 (749 tests→hooks — норма зеркала тестов) | production-межмодульных всего 3 |
| API_surface_size (utils.py) | 34 публичных символа; клиент использует медианно 3, max 9 | fat interface, HS-01 |
| forbidden_dependency_count | n/a — правил направления ещё нет | вводится в 11-fitness-functions.md |
| dependency_depth | ≤2 (hook → lib) | плоская топология |

## 10.2 Cohesion (адаптировано: кода классов нет — LCOM неприменим, см. 02 §H3)

| Прокси | Значение | Evidence |
|---|---|---|
| utils.py responsibility count | 4 роли (hook-protocol I/O, state+logging, project discovery, security) | группировка 34 символов по использованию |
| module purpose consistency | hooks/ смешивает 9 семантических групп в одной директории | Louvain + ручная семантика (07) |
| change cohesion hooks↔tests | co-change 93 (lift 1.66) — высокая, ЖЕЛАТЕЛЬНАЯ (тест меняется с кодом) | git |
| use-case cohesion документации | НИЗКАЯ: 9+ сайтов дублируют счётчики | grep, HS-02 |

## 10.3 Graph metrics (production undirected: imports + co-change lift>1)

| Метрика | Значение |
|---|---|
| modularity Q: Louvain (5 seeds) | 0.4107–0.4153, 9 кластеров |
| Q: greedy modularity | 0.4069 (8) · label propagation: 0.1344 (6) |
| Q: **directory partition** | **−0.0008** — плоский layout не выражает структуру |
| Q: Fiedler bipartition | 0.0639; cut=2; conductance 0.1667 |
| community_stability (Louvain, попарный index 5 seeds) | 0.981–1.0 |
| articulation point (доминирующий) | hooks/utils.py |
| isolated nodes | 45 standalone-скриптов |

## 10.4 Operational metrics

| Метрика | Значение | Статус |
|---|---|---|
| deployment_coordination_count (добавление 1 хука) | ≥4 файлов: hook.py + settings.json + README + plugin.json (+tests) | [VERIFIED-git] по коммитам добавления хуков |
| change_failure_rate, MTTR, incident_co_occurrence | — | <unknown>нет данных production-инцидентов</unknown> |
| distributed_trace_coverage | n/a (нет распределённых транзакций); аналог — hook_triggers.jsonl лог через единственного писателя utils.log_hook_trigger | частично |
| blast_radius (utils.py bug) | 60+ хуков (все импортёры) | [INFERRED] из fan-in |

## 10.5 Evolvability

| Метрика | Значение |
|---|---|
| files_per_feature_change (медиана нормального коммита) | 2–30 диапазон; типичное добавление хука ≥4 координированных файла |
| static vs change coupling overlap | Jaccard **0.121**; co-change без static — 43 пары (почти все — docs/config sync) |
| contract_breakage | не отслеживается;契约 хуков (stdin/stdout JSON) не версионирован |
| test_scope_per_change | tests↔hooks зеркальны (хорошо); test_structure.py реагирует на ЛЮБОЕ изменение счётчиков (цена gate) |

## §11 ТЗ — Architectural Surface Energy [HEURISTIC, не физика]

Нормировка каждого слагаемого в [0,1] относительно baseline. Веса объяснены, не «константы».

```
E_arch = 1.0·CrossBoundaryDependencyCost(=0.03: 3 prod-ребра)  + 2.0·CyclePenalty(=0)
       + 0·RuntimeCommunicationCost(unavailable)               + 1.5·ChangeCoupling(=0.62: doc-sync)
       + 1.5·DataCoupling(=0.55: 13 клиентов activeContext)     + 1.0·FailurePropagation(=0.70: utils blast)
       + 1.0·CoordinationCost(=0.50: ≥4 файлов/хук)             + 0·LatencyCost(n/a)
       + 0.5·ObservabilityGap(=0.40)                            + 0.5·DuplicationCost(=0.60: счётчики+манифесты)
       − 1.0·InternalCohesion(=0.35)                            − 1.0·DeploymentAutonomy(=1.0: один юнит, всегда атомарен)
```

Sensitivity analysis (ranking hotspots при вариации весов ±50%): порядок топ-3 (HS-01 utils,
HS-02 doc-sync, HS-03 memory store) **не меняется** ни в одной из 6 проверенных конфигураций,
т.к. каждый лидирует в своём независимом слагаемом (FailureProp / ChangeCoupling / DataCoupling).
Меняется только взаимный порядок HS-04/HS-06 (веса cohesion vs duplication). Компенсации не
скрыты: снижение DuplicationCost генерацией счётчиков ПОВЫШАЕТ CoordinationCost сборочного шага —
отражено в 09/12. Pareto-front представлен в 09-target-options.md; в одно число решения не сводятся.
