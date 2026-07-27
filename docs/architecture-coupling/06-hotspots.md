# 06 — Architectural Hotspots

Ranking по многомерной оценке (structural + change + data + evidence инцидентов из git +
cognitive), НЕ по одному скаляру; машинно-читаемая версия — artifacts/architecture-coupling/hotspots.json.
Sensitivity: топ-3 устойчив к вариации весов (05 §11).

| # | Component | Coupling type | Evidence | Root cause | Impact | Conf. | Candidate action | Falsification test | Prio |
|---|---|---|---|---|---|---|---|---|---|
| HS-01 | `hooks/utils.py` | structural, change | fan-in 74 рёбер / 61 клиент; 1074 LOC; 34 символа; медиана 3 имени на клиента (max 9); 5 символов никем не импортируются | god-utility: 4 роли в одном файле | баг распространяется на 60+ хуков; blast radius максимален | [VERIFIED-ast] | split → hooks/lib/{runtime,state,discovery,security}, интерфейсная сегрегация | Exp C: после split медиана sublibs/клиента = 1 | **P1** |
| HS-02 | Дубли счётчиков в доках (README×7, architecture.md, plugin.json, marketplace.json) | change, semantic | co-change: plugin↔README 28, README↔architecture 24; коммит cf32d7f «sync 89 Hooks header (missed by 88→89 sweep)»; дефект 87-vs-88 в docstring test_structure | copy-paste literals «N hooks» в ≥9 местах | каждое добавление хука = координированная правка 4+ файлов; дважды наблюдался silent drift | [VERIFIED-git+grep] | генерация счётчиков из диска (CI-шаг); gate оставить как backstop | Exp F: backtest gate на истории; FP-rate на doc-коммитах | **P1** |
| HS-03 | `.claude/memory/` shared mutable store | data | 32 файла-клиента; activeContext.md: 7 писателей + 6 читателей; file_lock у 11 файлов (частично) | shared-database интеграция через markdown без владельца | гонки записи, дрейф формата, скрытый контракт 13 хуков | [VERIFIED-grep] (эвристика записи — file-level) | memory-API в lib: единая точка записи + схема + обязательный lock | Exp E: инъекция конкурентной записи с/без дисциплины | **P1** |
| HS-04 | Плоский `hooks/` (91 файл) | structural, semantic, cognitive | dir-partition Q≈0.00 vs Louvain Q=0.4153, 9 сообществ, ARI 0.98–1.0 | layout не выражает латентные домены | нагрузка на понимание; некуда крепить контракты/ownership | [VERIFIED-clustering] | package-by-domain после семантической сверки (07/08) | Exp A: graph-only vs DDD-informed сравнение | P2 |
| HS-05 | Двойной manifest: `marketplace.json` (корень) vs `.claude-plugin/marketplace.json` | change, data | co-change 14; содержимое различается (478B vs 2496B) | дублированная packaging-метадата | drift внешне видимых метаданных | [VERIFIED-git+diff] | один источник + генерация или инвариант-тест | инвариант-тест ловит рукотворный рассинхрон | P2 |
| HS-06 | 10 незарегистрированных не-библиотечных хуков (doc_bridge, expert_registry, smart_model_router…) | structural, operational | нет в settings.json; большинство — в coverage-omit «requires full ~/.claude env» | дремлющий/среда-зависимый код в активном namespace | мёртвый-код-неоднозначность; счётчики доков их включают | [VERIFIED-json+grep] | триаж: register / attic / delete + fitness-правило | правило «hook ⇒ registered ∨ tagged» без исключений | P2 |
| HS-07 | `hooks/settings.json` — центральная регистрация | change, operational | 88 регистраций в одном файле | платформенная модель Claude Code | coordination_count ≥4 файлов на хук | [VERIFIED-json] | принять (constraint) + schema-валидация; снижать через HS-02 | schema-тест ловит битую регистрацию | P3 |
| HS-08 | Env-coupling на `~/.claude` глобальное состояние машины | runtime, data | 9 файлов → ~/.claude/state, 12 → ~/.claude/logs; pyproject WHY: «Obsidian vault, MarkItDown, sandbox» | интеграция с невоспроизводимой на CI средой | поведение зависит от машины; нетестируемое подмножество | [VERIFIED-grep+pyproject] | environment-facade с инъектируемым корнем | facade позволяет прогнать omit-хуки на tmp-окружении | P2 |
| HS-09 | `tests/test_structure.py` count-gate | change | co-change README↔test 15 | НАМЕРЕННЫЙ coupling (fitness function) | плюс: drift→красный тест; цена: churn | [VERIFIED-read] | сохранить; сузить blast через генерацию (HS-02) | Exp F | P3 |
| HS-10 | Dual-scope rules (repo `rules/` vs `~/.claude/rules`) | semantic, change | HEAD-коммиты 4fdfe84/3f2807b «canonical + stub/addendum, no full copies» | один текст в двух scope | было: дрейф копий; сейчас смягчено stub-паттерном | [VERIFIED-git+read] | fitness-правило: project-rule = canonical XOR stub | grep-тест на полнотекстовые копии | P3 |
| HS-11 | Вендорённые `skills/*/scripts/` | structural, quality | pyproject ruff-exclude с WHY | third-party в namespace репо | граница качества есть, контракта импорта нет | [VERIFIED-read] | forbidden-contract: hooks/scripts ↛ skills/**/scripts | import-linter contract падает на нарушении | P3 |

## Сквозной вывод

<inference>Профиль связности репо нетипичен: классический structural coupling почти идеален
(0 циклов, I=0.0 у ядра, 3 межмодульных ребра), а реальная стоимость изменений сидит в
**неструктурных каналах** — дублированных литералах (change coupling), общем файловом сторе
(data coupling) и одном god-utility (failure propagation). Минимизация числа рёбер здесь ничего
не дала бы — подтверждение главного принципа ТЗ (§4): цель — Pareto, не скаляр.</inference>
