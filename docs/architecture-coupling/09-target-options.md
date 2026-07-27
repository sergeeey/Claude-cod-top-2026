# 09 — Target Architecture Options

Оценки: L/M/H = low/medium/high. Evidence strength — насколько вариант опирается на verified-данные.

## Option A — Conservative (контракты поверх текущей структуры)

Состав: (1) split utils.py → hooks/lib/{runtime,state,discovery,security} за стабильным фасадом
(re-export для обратной совместимости); (2) import-linter в observe-режиме: acyclic siblings +
forbidden «hooks ↛ skills/**/scripts»; (3) генерация счётчиков доков из диска (CI-шаг), gate —
backstop; (4) триаж 10 orphan-хуков (register/attic/delete); (5) инвариант-тест на dual manifest;
(6) memory-write дисциплина: обязательный file_lock через единый helper.

| Критерий | Оценка |
|---|---|
| Expected coupling reduction | M (blast radius utils ↓, doc-sync co-change ↓~50% по числу сайтов) |
| Cohesion improvement | M (4 роли lib выделены) |
| Migration complexity | **L** (re-export сохраняет все import-пути) |
| Runtime latency risk | none (те же процессы) |
| Reliability risk | L |
| Observability impact | neutral/+ (schema-валидация settings.json) |
| Data migration risk | none |
| Team coordination impact | n/a (solo) |
| Cost | ~дни |
| Reversibility | H |
| Evidence strength | **H** — каждая мера бьёт в измеренный hotspot (HS-01/02/05/06/03) |

## Option B — Moderate (modular monolith: package-by-domain)

A + : (7) hooks/ → пакеты по 6 контекстам из 08 (runtime-lib, integrity, security, memory,
knowledge, research) с независимостью через import-linter independence-contract;
(8) memory-API: единственный writer-модуль для .claude/memory/* со схемой;
(9) environment-facade для ~/.claude (инъектируемый root — omit-хуки становятся тестируемыми);
(10) контракт hook-протокола (stdin/stdout JSON) как versioned schema + contract-тесты.

| Критерий | Оценка |
|---|---|
| Expected coupling reduction | H (data coupling берётся под контроль — главный остаточный риск A) |
| Cohesion improvement | H (layout = домены; dir-partition Q от ≈0 к уровню Louvain-Q) |
| Migration complexity | M (пути в settings.json, README-дерево, тестовые импорты) |
| Runtime latency risk | none |
| Reliability risk | M (массовое перемещение файлов; смягчается волнами и re-export) |
| Observability impact | + (memory-API логирует записи) |
| Data migration risk | L (формат файлов не меняется) |
| Cost | ~1–2 недели чистого времени |
| Reversibility | M |
| Evidence strength | M-H (границы = Louvain C1–C5 + DDD-сверка; C0 требует ручного разбора — Exp A) |

## Option C — Aggressive (мульти-плагин / отдельные deployment units)

Разделение на устанавливаемые независимо плагины: core-runtime, research-ops, vault-integration;
database-per-service-аналог: раздельные state-каталоги; event-log вместо общих markdown.

| Критерий | Оценка |
|---|---|
| Expected coupling reduction | формально H, фактически **перенос** в координацию версий |
| Migration complexity | H |
| Reliability risk | H (installer, совместимость версий плагинов) |
| Data migration risk | M-H (общая память делится по владельцам) |
| Cost | недели-месяцы |
| Reversibility | L |
| Evidence strength | **L** — ни один verified-факт не показывает выгоду при solo-разработке и одном deployment unit; против — C2 (Segment), C4 (Prime Video), H7 |

## Pareto-сводка и выбор

| Критерий \ Option | A | B | C |
|---|---|---|---|
| Structural | + | ++ | ++ |
| Change coupling | ++ | ++ | + |
| Data coupling | + | ++ | ++ |
| Operability/simplicity | ++ | + | − |
| Cost/risk | ++ | + | −− |

<gate>Рекомендация: **A немедленно, B поэтапно после верификации Exp C/E/F; C — reject** при
текущих владельце и deployment-модели (пересмотр при появлении второй команды/независимых
релизных циклов).</gate> Aggressive не выбирается «из теоретической чистоты» (§16 соблюдён).
