---
name: Feature Request / Запрос фичи
about: Suggest a new feature / Предложите новую функцию
title: "[FEATURE] "
labels: enhancement
assignees: ''
---

## Problem / Проблема

What problem does this solve? Why is it needed?
Какую проблему это решает? Почему это нужно?

## Proposed Solution / Предлагаемое решение

Describe the feature you'd like.
Опишите желаемую функциональность.

## Which layer? / Какой слой?

- [ ] CLAUDE.md (core config, must stay under 60 lines)
- [ ] Rule (contextual instruction in `rules/`)
- [ ] Hook (deterministic Python guard in `hooks/`)
- [ ] Skill (domain knowledge in `skills/`)
- [ ] Agent (specialized subagent in `agents/`)
- [ ] MCP Profile (server grouping in `mcp-profiles/`)
- [ ] install.sh (installer logic)
- [ ] Documentation (docs/)
- [ ] Other

## Token Impact / Влияние на токены

Estimated token cost of the feature:
- Always loaded (CLAUDE.md): ~___ tokens
- On-context (rules): ~___ tokens
- On-trigger (skills): ~___ tokens
- Zero (hooks): 0 tokens

## Alternatives Considered / Рассмотренные альтернативы

What other approaches did you consider?
Какие ещё подходы рассматривали?

## 80/20 Check

Does this feature deliver 80% of the value with 20% of the effort?
Эта фича даёт 80% результата за 20% усилий?
