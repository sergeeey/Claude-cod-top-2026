---
tags: [pareto-leverage-scan]
max_turns: 6
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep]
---

У нас 4 микросервиса, p95 латентность за неделю (мс): orders 480, checkout 420, catalog 60, profile 35. Какой оптимизировать первым? Надо ли тут делать Pareto-скан или хватит простого сравнения?
