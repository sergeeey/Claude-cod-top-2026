# 12 — Refactoring Roadmap

Порядок соответствует рекомендованной последовательности §18 ТЗ (measurement → cycles →
ownership → contracts → fat interface → data ownership → observability → modularization →
selective extraction → continuous fitness). Big-bang исключён; каждая волна независимо
проверяема и откатываема. Owner всех волн: единственный maintainer.

| Wave | Change | Target hotspot | Expected effect (измеримый) | Verification | Rollback | Dependencies |
|---|---|---|---|---|---|---|
| 0 | Зафиксировать baseline: закоммитить artifacts/architecture-coupling + CI-джоб пересчёта (fitness №14) | все | первая точка regression-ряда | джоб зелёный, метрики совпадают с этим отчётом | удалить джоб | — |
| 1 | Cycle-guard: SCC-тест (fitness №1) в block | — (превентивно) | циклы навсегда = 0 | тест зелёный на HEAD | revert теста | 0 |
| 2 | Триаж 10 orphan-хуков: register / attic/ / delete + правило «hook ⇒ registered ∨ tagged» | HS-06 | unregistered non-lib = 0 | listing-тест | git revert | 0 |
| 3 | Генерация счётчиков доков из диска (CI или pre-commit), gate остаётся backstop | HS-02, HS-09 | сайтов ручной правки счётчиков: 9+ → 1; co-change plugin↔README ↓ (тренд, 10 коммитов) | Exp F FP-замер; gate зелёный | генератор off, тексты руками | 0 |
| 4 | Инвариант-тест dual manifest (root vs .claude-plugin) или устранение root-копии | HS-05 | drift невозможен молча | новый тест | revert | 0 |
| 5 | Split utils.py → hooks/lib/{runtime,state,discovery,security} + фасад utils (re-export) | HS-01 | Exp C gate: медиана sublibs/клиента = 1; blast radius бага локализуется до подбиблиотеки | pytest full + Exp C метрики | фасад сохраняет старые пути — revert тривиален | 1 |
| 6 | Memory-API: единый writer для .claude/memory/* (schema + lock обязательны); миграция 7 писателей | HS-03 | прямых писателей: 7 → 0 (кроме API); Exp E (a) = 0 повреждений | Exp E в sandbox; grep-fitness №6 warn→block | API остаётся, старый код возвращается revert'ом | 5 |
| 7 | Environment-facade для ~/.claude (инъектируемый root) | HS-08 | coverage-omit список сокращается; omit-хуки получают smoke-тест на tmp-env | pytest new smoke | revert | 5 |
| 8 | Package-by-domain hooks/ по 6 контекстам (08) волнами по одному пакету; settings.json пути обновляются на каждый пакет отдельно | HS-04 | dir-partition Q: ≈0 → сопоставимо с Louvain Q (пересчёт arch_analyze); independence-contract observe | fitness №3 observe; полный pytest на каждый пакет | пакет двигается обратно (git mv) | 5, 6 |
| 9 | Contract-версия hook-протокола (schema для stdin/stdout JSON) | HS-07 частично | breaking change протокола детектируем | contract-тесты | revert | 5 |
| 10 | Fitness-функции в block по мере прохождения calibrate (правила 2, 6, 10) | все | регрессии блокируются автоматически | 3 чистых замера №14 подряд | вернуть в warn | 0–9 |

Stop conditions per wave: любой красный полный pytest → волна откатывается, разбор до продолжения;
Evaluator-Optimizer cap = 3 итерации на волну (правило CLAUDE.md), затем эскалация владельцу.

Selective extraction (§18 п.9) — **не планируется**: Option C отклонён (09); пересмотр только
при смене deployment-модели.
