# 11 — Architectural Fitness Functions

Инструмент: pytest (уже в CI) + import-linter (P1, spot-checked; ставится в изолированное окружение,
manifests репо не трогаются до решения владельца). Все НОВЫЕ правила стартуют в
`observe → warn → calibrate → block`; ни одно не блокирует CI по непроверенному порогу.
Прецедент в репо уже есть: count-gate в tests/test_structure.py (родился из инцидента 87-vs-88).

| # | Rule | Measurement | Baseline (2026-07-16) | Initial mode | Blocking threshold | Exception process |
|---|---|---|---|---|---|---|
| 1 | Нет новых dependency cycles | import-linter acyclic contract / networkx SCC в тесте | **0 циклов** | **block сразу** (baseline чист — регресс однозначен) | SCC>1 = fail | нет исключений |
| 2 | Запрещённые направления: `hooks ↛ scripts`, `hooks/scripts ↛ tests`, `* ↛ skills/**/scripts` (vendored) | import-linter forbidden | 0 нарушений | block | ≥1 | ADR + waiver c owner/expiry |
| 3 | Новая cross-boundary зависимость между доменными пакетами (после Option B) требует ADR | independence contract diff vs allowlist | n/a до B | observe | нарушение без ADR-ссылки | ADR в decisions.md |
| 4 | Счётчики (N hooks/skills/agents) во всех метадоках = факту на диске | существующий test_structure gate + генерация | 9+ сайтов дублей | уже block (gate) | mismatch | правка генератора, не текстов |
| 5 | Критические модули не зависят от менее стабильных | I(importer) ≥ I(importee) по module-графу | выполняется (tests I=1.0 → hooks I=0.0) | observe | инверсия против I | ADR |
| 6 | Запись в `.claude/memory/*` только через memory-API (после B §8) | grep/AST: open-with-write вне API-модуля | 7 прямых писателей activeContext | observe → warn | новый прямой писатель | waiver + expiry |
| 7 | Каждый write-путь к общим store — через file_lock/atomic_write | AST-скан вызовов | 11 файлов с lock, полнота не 100% | warn | новый unlocked writer | — |
| 8 | Глубина синхронной цепочки hook→subprocess ≤ 2 | AST subprocess-скан | max 2 (git-вызовы) | observe | >2 | ADR |
| 9 | Hook I/O контракт (stdin/stdout JSON) проходит schema-check | contract-тест на emit_hook_result/parse_stdin | схема не версионирована | observe | breaking change схемы | версия схемы |
| 10 | Изменение hooks/settings.json запускает schema-валидацию + структурные тесты | pytest trigger по пути | есть частично (test_structure) | block | invalid JSON/регистрация несущ. файла | — |
| 11 | Новый файл с fan-in > p95 (сейчас p95≈8; utils=74 grandfathered) требует review | networkx метрика в тесте | utils.py единственный выброс | observe | 2-й файл >p95 | ADR |
| 12 | Каждый hook-запуск логируется с correlation (session id) в hook_triggers.jsonl | наличие log_hook_trigger вызова | 1 writer (utils) — OK | observe | — | — |
| 13 | Каждый waiver имеет owner и expiration date | линт waiver-файла | waiver-механизма нет | вводится вместе с №2 | просроченный waiver | автозакрытие |
| 14 | Значения метрик (coupling-metrics.json) пересчитываются и коммитятся для regression-анализа | CI-джоб повторяет arch_analyze | этот отчёт = первая точка | observe | ухудшение тренд-метрик 3 замера подряд → warn | — |

## Мини-конфиг import-linter (черновик, observe)

```ini
[importlinter]
root_packages = hooks, scripts

[importlinter:contract:no-cycles]
name = Acyclic hooks
type = acyclic_siblings
containers = hooks

[importlinter:contract:no-vendored]
name = No vendored imports
type = forbidden
source_modules = hooks, scripts
forbidden_modules = skills
```

## Backtest-статус (Exp F)

Правило 4: два исторических инцидента поймано бы 2/2; FP-rate — <hypothesis>оценка требуется
прогоном по 20 doc-коммитам</hypothesis>. Правила 1/2: baseline чист → false positives
структурно невозможны до первого нарушения. Правила 6/7: baseline «7 писателей» — блокировка
включается ТОЛЬКО после миграции на memory-API, иначе правило заведомо красное (анти-паттерн
«блокировать CI по непройденному baseline» исключён).
