# 13 — Risk Register

| Risk | Cause | Detection | Mitigation | Severity |
|---|---|---|---|---|
| Overfitting to graph structure | принятие Louvain C0 (n=41) за домен — это гравитация utils, не семантика | boundary review (07/08); Exp A | DDD-validation обязательна до любого git mv; C0 разбирается вручную | **High** (уже материализовался бы при слепом принятии кластеров) |
| Metric gaming | оптимизация числа рёбер/Q вместо качества | multi-metric review, Pareto (09) | E_arch объявлен эвристикой; решения только по Pareto-таблице | Medium |
| False precision | перенос порогов (I, LCOM, «2.5×») как «стандартов» | source audit (02: порогов в литературе НЕТ) | локальная калибровка; observe→block; правило №11 использует свой p95 | Medium |
| Excessive isolation | стремление к zero shared code/store | рост DuplicationCost, потеря observability (Exp B) | balanced constraints; H7-вердикт; общий логгер сохраняется | Medium |
| Microservice over-decomposition | «6 контекстов = 6 плагинов» | runtime/team-анализ (solo, 1 deployment unit) | Option C = reject; modular monolith first (C1, C2) | Low (отклонено явно) |
| Lost observability | при split utils случайно потерять единственного писателя hook_triggers.jsonl | trace coverage check; правило №12 | log_hook_trigger живёт в lib/state с contract-тестом | Medium |
| Resilience regression | удаление «дублирующих» guard-хуков как «redundancy» | failure tests | guards не считаются дублированием; изменения guard'ов только с тестами | Medium |
| Data inconsistency | миграция 7 писателей activeContext на memory-API с потерей записей | reconciliation-тест: старый vs новый вывод на одном сценарии | волна 6 делается по одному писателю; Exp E до миграции | **High impact / Low prob** |
| Latency regression | новые границы = новые процессы? — нет: пакеты не добавляют процессов | SessionStart budget ≤8s (autonomy-budget.md) | замер времени хуков до/после split | Low |
| Algorithm instability | Louvain недетерминизм | 5 seeds, ARI 0.981–1.0 [VERIFIED] | consensus-границы; Leiden при росте графа | Low |
| Tool bias | кастомный AST-скан мог пропустить динамические импорты/exec | cross-tool сравнение | контрольный прогон Grimp (изолированное окружение) до волны 5; ручная выборка 10 файлов | Medium |
| Repository damage | артефакты исследования попали бы в рабочие копии | `git -C repo-fresh diff --check` = 0; git status clean | research-only mode: записи только в workspace-корень вне git-копий | Low (проверено) |
| Windows-специфика file_lock | Exp E может дать иную семантику блокировок на NTFS, чем на POSIX | Exp E прогоняется на целевой ОС (Windows) | вывод Exp E не переносится между ОС без пере-прогона | Medium |
| Стейл-копии проекта | 3 копии репо в workspace (main / fresh / clean-test) расходятся | diff -rq зафиксировал расхождения | указать канон (repo-fresh); рабочую копию синхронизировать или удалить лишние | Medium |
