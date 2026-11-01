---
tags: [pareto-leverage-scan]
max_turns: 6
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep]
---

У нас 6 сервисов, у каждого p95 латентность за неделю (мс): gateway 820, search 610, billing 140, auth 95, notifications 60, reports 40. Сумма 1765. Мы хотим понять, какой сервис оптимизировать первым. Нужен ли здесь Pareto-скан или хватит простого сравнения? Если нужен, сделай его по всем правилам.
