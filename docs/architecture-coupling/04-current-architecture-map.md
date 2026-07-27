# 04 — Current Architecture Map

HEAD `3f2807b` (repo-fresh). Все числа — [VERIFIED] из artifacts/architecture-coupling/*.json,
воспроизводимо командами из commands.log.

## Топология

```
Claude Code (host, event source)
   │  25 event types, 88 registrations (hooks/settings.json)
   ▼
hooks/*.py (91 файл, независимые короткоживущие процессы; stdin JSON → stdout JSON)
   │            │
   │ import     │ read/write (файловые контракты)
   ▼            ▼
hooks/utils.py + 6 shared libs      Shared file stores:
(hook-protocol, state, logging,       .claude/memory/{activeContext,patterns,decisions}.md
 discovery, security)                 ~/.claude/state/*, ~/.claude/logs/*.jsonl
                                      experiments/, null_results/, pearl_registry/
scripts/*.py (29 CLI-утилит) ──────────┘
tests/*.py (88) ── 749 import-рёбер → hooks, 10 → scripts

Знания (Markdown-плоскость): skills/ (123) · rules/ · agents/ (15+3) · claude-md/ · commands/
   └─ doc_reference-рёбра на hooks/*.py, rules/*.md (граф в dependency-graph.json)
Packaging: .claude-plugin/{plugin,marketplace}.json + marketplace.json (корень, дубль)
```

## Пять независимых представлений (раздел 9 ТЗ)

| Слой | Построен | Узлы/рёбра | Ключевой факт |
|---|---|---|---|
| Static import graph (file-level) | да, AST | 215 .py / 238 import-рёбер | <fact>0 циклов (SCC>1 = 0)</fact>; звезда вокруг utils.py (fan-in 74) |
| Hook registration graph | да, settings.json | 25 events → 75 hook-файлов, 88 регистраций | 16 hook-файлов вне регистрации (7 — библиотеки, 9–10 — orphan/env-хуки) |
| Change coupling graph | да, git history | 635 коммитов; 519 непустых; 311 «нормальных» (2–30 файлов); 11 mass (>30) исключены | топ-пары — документационные: plugin.json↔README (28), README↔architecture.md (24) |
| Data coupling graph | да, path-литералы | 20 store-узлов | `.claude/memory/` — 32 файла-клиента; activeContext.md: 7 писателей + 6 читателей |
| Runtime coupling graph | **unavailable** | — | <unknown>production traces отсутствуют; static analysis не подменяет runtime (правило 9.3 соблюдено)</unknown> |
| Socio-technical graph | вырожден | 1 разработчик | team-границы неприменимы; координация меряется файлами-на-изменение |

## Направления зависимостей (module-level DSM)

Межмодульных import-рёбер всего 3 (см. dependency-structure-matrix.csv):
`tests → hooks` (749), `tests → scripts` (10), `scripts → hooks` (3).
<fact>hooks: Ca=2, Ce=0, I=0.0 — самый стабильный модуль, зависимости направлены К нему; инверсий
направления устойчивости нет.</fact> Содержательная структура — на уровне под-доменов ВНУТРИ hooks/
(см. 07-clustering-analysis.md): плоская директория скрывает 9 устойчивых сообществ.

## Типы рёбер, найденные в коде (9.1 ТЗ)

Присутствуют: import dependency, hook registration (аналог DI-контейнера), shared file store
(аналог shared database), doc_reference, subprocess-вызовы git. Отсутствуют: наследование между
модулями, сетевые API-вызовы между компонентами, message subscription, build dependency
(сборки нет), database access (СУБД нет).

## Особые структурные факты

1. <fact>45 изолированных production-файлов</fact> (ни импортов, ни значимого co-change) —
   standalone-скрипты; для плагин-модели это норма, не дефект.
2. Вендорённые payload'ы `skills/*/scripts/` исключены из lint (pyproject WHY-note) — явная
   quality-граница; контракта «не импортировать вендорённое» пока нет (HS-11).
3. Прецедент fitness function уже в репо: `tests/test_structure.py` — count-consistency gate,
   рождённый из реального дефекта «87 vs 88» (документирован в docstring теста).
