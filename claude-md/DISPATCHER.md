# Adaptive Dispatcher — Methodology per Project Type

First step in any project. The `project_classifier` hook injects a `[dispatcher]`
verdict into context at SessionStart (project type + methodology to load).
**Read it and act before substantive work** — do not apply one-size-fits-all rigor.

## Project type → methodology

| Project type | Load THIS | Do NOT load |
|--------------|-----------|-------------|
| **research** | FL Full-Ladder + EstimandOps L0 gate + skeptic-triggers. Claims → `[VERIFIED]/[HYPOTHESIS]` | — |
| **data-science** | EstimandOps L0 + validation on REAL data (`[VERIFIED-REAL]`). FL Standard | full FL on every fix |
| **production** | reviewer + tester ≥80% + FL Standard. security-audit before release | EstimandOps (no hypotheses) |
| **MVP** | Speed > rigor. Tests optional. FL Micro. builder solo | reviewer/tester gates, full FL |
| **unonboarded** | Onboarding: ask goal/stack → create CLAUDE.md + activeContext.md | any heavy methodology |

## Project × Task matrix (refines the above)

```
research   × hypothesis  → FL Full + EstimandOps + sci-hypothesis + skeptic
research   × quick-fix   → FL Standard (in research even a fix shifts conclusions)
data-sci   × experiment  → EstimandOps L0 + real-data validation + skeptic-triggers
production × feature     → reviewer + tester(≥80%) + FL Standard
production × security    → review-squad + security-audit + FL Full
production × quick-fix   → FL Micro + reviewer
MVP        × feature     → builder solo, tests optional, FL Micro
any        × debug       → hypothesis-arbiter + skeptic (competing hypotheses)
any        × refactor    → architect (Step-Back) + reviewer
```

## Rules

1. If `[dispatcher]` verdict present → announce `Project X × task Y → loading [methodology]` before starting.
2. If verdict is `ambiguous` / missing → read project CLAUDE.md+README, decide type, state it.
3. **Always name what you deliberately SKIP** ("EstimandOps not needed for a prod fix") — prevents silent rigor-creep ("everything always on"). This is the dispatcher's core value.
4. When profile disagrees with reality (hook judged by structure, you see intent in README/goal) → override the verdict, update `project_profile.md` with one line `[LLM-override: reason]`.
5. Full skill with output format: `skills/core/dispatcher/SKILL.md` — invoke `/dispatcher` when unsure.

## Why this exists

One methodology on all projects is either overkill (full FL on a CSS fix) or a
hole (research without EstimandOps). The dispatcher is the "nervous node" that
connects scattered rules/agents/skills into an adaptive organism: **type × task
→ load exactly the needed methodology**, and explicitly skip the rest.

**Source:** `hooks/project_classifier.py` (deterministic signals) + LLM arbitration
(intent from README/goal). Hybrid: hook = fast draft, LLM = final call.
