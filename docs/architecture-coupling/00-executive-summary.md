# 00 — Executive Summary

**Субъект:** плагин-репозиторий Claude-cod-top-2026 (Python-хуки + Markdown-знания), HEAD `3f2807b`.
**Вопрос (EstimandOps L0: descriptive):** где реальная архитектурная связность и что довести до
reference-grade. **Вердикт: `proceed_with_caution`.**

## Главный результат

<fact>Классический structural coupling почти эталонный уже сейчас: 0 циклов, 3 межмодульных
production-ребра, зависимости направлены к стабильному ядру (I: tests 1.0 → hooks 0.0).</fact>
<inference>Реальная стоимость изменений живёт в неструктурных каналах: (1) fat-interface
god-utility `hooks/utils.py` (fan-in 74, blast radius 60+ хуков), (2) change coupling через
дублированные счётчики в 9+ док-сайтах (два исторических инцидента дрейфа), (3) data coupling
через общий mutable store `.claude/memory/` (13 хуков, 7 писателей, lock не тотален).
Минимизация числа рёбер ничего бы не дала — подтверждён Pareto-принцип ТЗ.</inference>

## Топ-хотспоты (полный список из 11 — 06-hotspots.md)

1. **HS-01** utils.py — fat interface (медиана: клиент использует 3 из 34 символов).
2. **HS-02** дубли счётчиков README/plugin.json/marketplace.json/architecture.md.
3. **HS-03** activeContext.md — 7 конкурентных писателей без гарантированного lock.
4. HS-04 плоский hooks/ (91 файл) скрывает 9 стабильных Louvain-доменов (Q=0.4153 vs ≈0 у layout).
5. HS-05/06 dual manifest + 10 orphan-хуков.

## Рекомендация

**Option A (контракты поверх текущей структуры) — немедленно; Option B (package-by-domain
modular monolith) — волнами после экспериментов C/E/F; Option C (мульти-плагин) — reject**
для solo-разработки и одного deployment unit (обоснование: Segment C2, Prime Video C4, H7).

## Пять первых действий (max effect/risk)

1. Волна 1: SCC-тест циклов в block (baseline чист — бесплатная защита лучшей метрики).
2. Волна 3: генерация счётчиков доков из диска; существующий count-gate — backstop (убивает HS-02).
3. Волна 2: триаж 10 orphan-хуков (register/attic/delete).
4. Волна 4: инвариант-тест на dual marketplace.json.
5. Волна 5: split utils.py на 4 подбиблиотеки за фасадом (re-export, откат тривиален).

## Ключевые unresolved unknowns

Runtime-телеметрия отсутствует (все runtime-выводы — design-time); FP-rate count-gate требует
backtest-прогона; семантика file_lock на Windows — Exp E. Полный список: 14-final-verdict.md §23.

<confidence>0.78</confidence> — 29 verified источников (3 spot-checked), воспроизводимые
измерения (seeds/commands.log), но: runtime-слой недоступен, write-детекция эвристична,
полные тексты платных книг не перечитывались.
