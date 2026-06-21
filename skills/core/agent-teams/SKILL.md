---
name: agent-teams
description: >
  Паттерны для оптимального состава команд агентов: sizing heuristics, preset configurations,
  agent type selection. Используй когда решаешь сколько агентов запустить,
  какой тип агента выбрать для роли, как организовать Review/Debug/Feature/Security команду.
  Триггеры: /agent-teams, "team composition", "how many agents", "spawn agents",
  "multi-agent team", "сколько агентов", "команда агентов", "parallel agents setup".
triggers: [team, squad, parallel agents, review-squad, build-squad, research-squad, team composition, how many agents, spawn agents, сколько агентов]
tokens: ~350
type: directory
STATUS: confirmed
CONFIDENCE: high
VALIDATED: 2026-06-10
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : agent-teams
TL;DR  : Sizing heuristics + preset teams + agent type selection для multi-agent workflows
Вызов  : /agent-teams, team composition, how many agents, spawn agents, multi-agent
НЕ для : Одиночный агент (прямо используй Agent tool); review кода (→ /reviewer)
-->

# Agent Teams Orchestration

## Sizing Heuristics

**Правило:** Начни с наименьшей команды которая покрывает все нужные измерения.
Каждый дополнительный агент = overhead координации.

| Сложность | Размер | Когда использовать |
|-----------|--------|--------------------|
| Simple | 1-2 | Single-dimension review, изолированный баг, небольшая фича |
| Moderate | 2-3 | Multi-file изменения, 2-3 аспекта, средние фичи |
| Complex | 3-4 | Cross-cutting concerns, большие фичи, глубокий debug |
| Very Complex | 4-5 | Full-stack фичи, comprehensive review, системные проблемы |

## Agent Type Selection

| Тип | Инструменты | Использовать для |
|-----|-------------|------------------|
| `general-purpose` | Все | Implementation, debugging |
| `Explore` | Read-only | Research — НЕ для impl |
| `Plan` | Read-only | Архитектурное планирование |
| `reviewer` | Read + Bash | Code review |
| `builder` | Read + Write + Edit + Bash | Написание кода |
| `tester` | Read + Write + Bash | Написание тестов |

**Критическое:** Read-only агенты (Explore, Plan) НЕ могут изменять файлы.

## Preset Team Compositions

| Команда | Агенты | Измерения | Когда |
|---------|--------|-----------|-------|
| Debug Team (3) | 3x general-purpose | По 1 competing hypothesis каждому | Баг с несколькими причинами |
| Feature Team (3) | 1x lead + 2x builder | Параллельные workstreams | Фича делится на части |
| Fullstack Team (4) | 1x lead + frontend + backend + tests | Full stack | Cross-layer фича |
| Security Team (4) | 4x reviewer | OWASP / auth / dependencies / secrets | Comprehensive audit |
| Migration Team (4) | 1x lead + 2x builder + 1x reviewer | Parallel impl + correctness | Большая миграция |

## Available Teams (наши стандартные)

| Team | Lead | Teammate | Strategy | Use Case |
|------|------|----------|----------|----------|
| **review-squad** | reviewer | sec-auditor | parallel | Code review + security audit |
| **build-squad** | builder | tester | parallel-worktree | Implementation + tests |
| **research-squad** | explorer | verifier | sequential | Search + verify claims |

## Decision Matrix: When to Use Teams

| Situation | Single Agent | Team |
|-----------|:---:|:---:|
| Simple code review (1-2 files) | reviewer | — |
| Review touching auth/payment | — | review-squad |
| New feature with clear spec | builder | build-squad |
| Quick codebase search | explorer | — |
| Research with Evidence Policy | — | research-squad |
| Multi-file refactoring (3+) | — | review-squad |

## SendMessage Pattern (Multi-Turn Agent Conversations)

To continue a conversation with a completed subagent:
```
SendMessage(to: "agent-<id>", message: "Now check edge cases for...")
```

The agent resumes with full context — no reload, no token waste.

**When to use:**
- Explorer found partial results → send follow-up query
- Builder needs to iterate on reviewer feedback
- Verifier needs more context to verify a claim

## Conflict Resolution

When team agents disagree:
1. **Security wins** — if sec-auditor says BLOCKED, the verdict is BLOCKED
2. **Evidence wins** — [VERIFIED] claims override [INFERRED]
3. **Lead decides** — if ambiguous, lead agent makes the final call

## Token Budget Management

| Team | Typical Cost | Budget Cap |
|------|:---:|:---:|
| review-squad | ~1500 tok | 2500 tok |
| build-squad | ~2500 tok | 4000 tok |
| research-squad | ~1200 tok | 2000 tok |

If nearing budget: lead summarizes and stops teammates.

## Anti-Patterns

- **DON'T** use teams for trivial tasks (single file, obvious fix)
- **DON'T** run build-squad without a clear spec (both agents need the same input)
- **DON'T** ignore verifier's HALLUCINATION verdict — it means the claim has no evidence
- **DON'T** run review-squad on MVP code — single reviewer is enough
