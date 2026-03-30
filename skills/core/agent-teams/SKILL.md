---
name: agent-teams
description: "Orchestration patterns for Agent Teams — parallel review, build, and research"
triggers: [team, squad, parallel agents, review-squad, build-squad, research-squad]
tokens: ~200
type: directory
STATUS: confirmed
CONFIDENCE: high
VALIDATED: 2026-03-30
---

# Agent Teams Orchestration

## Available Teams

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
