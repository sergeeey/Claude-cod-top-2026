# 07 — Clustering Analysis

Граф: production .py (без tests), undirected; веса = import weight + co_change_count/2 (пары с lift>1).
Полные составы кластеров: artifacts/architecture-coupling/communities.json.

## Протокол запусков (§12 ТЗ)

| algorithm | graph_type | edge_weights | parameters | seed | n_clusters | modularity | прочее |
|---|---|---|---|---|---|---|---|
| Louvain | undirected weighted | import+cochange | resolution=1 | 1,2,3,100 | 9 | 0.4107 | |
| Louvain | — » — | — » — | resolution=1 | 42 | 9 | **0.4153** | выбран как репрезентативный |
| Label propagation | — » — | — » — | — | determin. | 6 | 0.1344 | нестабильный класс алгоритмов, контроль |
| Greedy modularity (CNM) | — » — | — » — | — | — | 8 | 0.4069 | согласуется с Louvain |
| Spectral (Fiedler) | — » — | — » — | bipartition | 42 | 2 | 0.0639 | cut=2, conductance 0.167 |
| Directory partition (baseline) | — » — | — » — | — | — | 2 | **−0.0008** | layout не несёт структуры |

Stability: попарный index Louvain по 5 seeds = 0.981–1.0 → результат устойчив.
Resolution limit (Fortunato-Barthélemy): кластеры n=2 (C6–C8) ниже разрешающей способности —
не интерпретируются как модули.

## Семантическая расшифровка Louvain seed42

| Кластер | n | Содержимое (примеры) | Семантика | Годится как граница? |
|---|---|---|---|---|
| C0 | 41 | agent_lifecycle, checkpoint_guard, evidence_guard, mcp_circuit_breaker, project_classifier… | «всё, что импортирует только utils» — гравитация вокруг god-lib | **НЕТ** — артефакт HS-01, не домен |
| C1 | 9 | auto_capture, knowledge_librarian, vector_store, session_save, cogniml_client, wiki_reminder | Knowledge/Vault pipeline | ДА |
| C2 | 6 | validation_theater_guard, commit_test_gate, iteration_guard, weakened_test_guard, hook_state | Test-integrity guards | ДА |
| C3 | 5 | doc_bridge, doc_registry, expert_registry, file_auto_parser, pre_vault_write | Document ingestion (env-зависимый) | ДА (совпадает с coverage-omit) |
| C4 | 5 | learning_tips, learning_tracker, pattern_extractor, post_commit_memory, session_start | Memory/Learning | ДА |
| C5 | 4 | input_guard, mcp_response_guard, web_response_guard, severity_calibrator | Security guards | ДА |
| C6–C8 | 2×3 | пары | ниже resolution limit | не интерпретировать |

## Сравнение способов определения границ (≥3 по ТЗ)

| Candidate boundary | Structural evidence | Semantic evidence | Runtime evidence | Risks | Verdict |
|---|---|---|---|---|---|
| Louvain as-is (9 кластеров) | Q=0.4153, стабильно | C1–C5 осмысленны; C0 — мусорный гигант | n/a | принять C0 = оверфит на граф | **reject** (as-is) |
| Directory status quo (flat hooks/) | Q≈0 | не выражает домены | n/a | сохраняет когнитивную нагрузку | reject как целевое, остаётся допустимым временно |
| **DDD-informed: Louvain C1–C5 + разбор C0 по событию/назначению (08)** | наследует Q кластеров + registration graph | словарь доменов совпадает (guard/gate/memory/vault/research) | события settings.json как независимое свидетельство | требует ручной сверки C0 | **pilot** |
| Fiedler bipartition | cut=2 | бессмысленна семантически | n/a | — | reject (подтверждает H1-поправку) |
| Co-change clusters (docs+manifests) | сильнейшие пары вне .py | «packaging» — реальный скрытый домен | n/a | — | **adopt** как отдельный контекст Packaging/Docs |

<inference>Главный урок кластеризации: C0 — эмпирическая демонстрация того, что minimum-cut/modularity
без семантики выдаёт «границу», проходящую по линии наименьшего сопротивления (общая утилита),
а не по бизнес-смыслу. Это прямое локальное подтверждение поправок к H1/H5.</inference>
Один запуск кластеризации НЕ выдан за единственно правильную архитектуру (§12 соблюдён).
