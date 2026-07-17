# MANIFEST — Architecture Coupling Research Package

Дата: 2026-07-16 · Субъект: repo-fresh @ 3f2807b · Режим: research-only (production-код,
manifests, lockfiles, git-копии — не изменялись; `git -C repo-fresh diff --check` = exit 0).

## docs/architecture-coupling/ (этот каталог)

| Файл | Содержание |
|---|---|
| 00-executive-summary.md | Вердикт, топ-hotspots, 5 первых действий |
| 01-environment-passport.md | Стек, топология, ограничения данных |
| 02-research-evidence.md | Ответы на RQ 7.1–7.4, вердикты H1–H8, contradiction matrix |
| 03-source-matrix.csv | 29 верифицированных источников (полные поля §6.2) |
| 04-current-architecture-map.md | 5 графовых представлений, направления зависимостей |
| 05-metrics-baseline.md | Structural/cohesion/graph/operational/evolvability + E_arch (эвристика) |
| 06-hotspots.md | 11 hotspots с evidence/root cause/falsification |
| 07-clustering-analysis.md | Протокол Louvain/LP/greedy/spectral, стабильность, вердикты границ |
| 08-ddd-boundary-analysis.md | Glossary, 6 bounded contexts, context map, data ownership |
| 09-target-options.md | Options A/B/C, оценочные таблицы, Pareto-сводка |
| 10-experiment-plan.md | Эксперименты A–F (A, D выполнены; B, C, E, F — спроектированы с gates) |
| 11-fitness-functions.md | 14 CI-ready правил, baseline, observe→block, import-linter черновик |
| 12-refactoring-roadmap.md | 10 волн с verification/rollback/stop-conditions |
| 13-risk-register.md | 14 рисков |
| 14-final-verdict.md | Итоговый отчёт (структура §21 ТЗ), verdict + confidence |
| MANIFEST.md | этот файл |

## artifacts/architecture-coupling/

| Файл | Содержание |
|---|---|
| dependency-graph.json | Все рёбра 5 слоёв (import/registration/data/doc/…) с evidence и location |
| dependency-graph.graphml | Import-граф (215 узлов) для Gephi/yEd |
| dependency-structure-matrix.csv | Module-level DSM |
| coupling-metrics.json | Полный baseline метрик (источник чисел отчёта) |
| communities.json | Полные составы кластеров всех запусков (seeds зафиксированы) |
| hotspots.json | Машинно-читаемые hotspots |
| commands.log | Все выполненные команды (воспроизводимость) |
| tool-versions.txt | python 3.12.7, networkx 3.5, scipy 1.15.3, git 2.47.0.windows.1 |

## Не создано

<unknown>
Артефакт: runtime coupling graph. Причина: нет production-телеметрии (хуки — локальные
короткоживущие процессы; OTel endpoint не поднят). Что требуется: включить scripts/otel_exporter
или hook_metrics на живой машине. Как создать позднее: собрать ≥2 недели hook_triggers.jsonl +
тайминги, повторить arch_analyze с runtime-слоем.
</unknown>
