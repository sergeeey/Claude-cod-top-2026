---
name: brainstorming
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-13]
  USE when user asks about architecture, design, or alternatives.
  MUST USE before multi-file changes requiring design decisions.
  Triggers: how to best, what are the options, let's think, design, brainstorm,
  alternatives, trade-offs, architecture, approach.
  ESPECIALLY when tempted to jump straight to code without design.
---

# Skill: Socratic Design Brainstorming

## When to Load
- New feature / module without a clear specification
- Architectural decision with non-obvious trade-offs
- User says "let's think", "how to best do this", "what are the options"

## Principle
One question at a time. 2-3 alternatives with trade-offs. Hard gate: "design approved" before code.

---

## Phase 0: Deep Interview (Ambiguity Gating)
<!-- Source: oh-my-claudecode (14K stars) — reduces rework by 40-60% -->

**Goal:** block premature design when the problem space is still unclear.

### Ambiguity Score
Evaluate four dimensions before any design work:

| Dimension | Weight | Question |
|-----------|--------|----------|
| Goal clarity | 0.3 | Is the desired outcome specific? |
| Scope | 0.3 | Are boundaries clear (in/out)? |
| Constraints | 0.2 | Are tech/time/resource limits known? |
| Success criteria | 0.2 | Can we verify when done? |

Score each 0–1. `ambiguity = 1 − Σ(score × weight)`.

### Protocol
- If `ambiguity > 0.20`: ask **ONE** question targeting the weakest dimension → wait → re-score.
- Repeat until `ambiguity ≤ 0.20` or 3 rounds reached.
- After 3 rounds: proceed with assumptions stated explicitly.

### Hard Rules
1. **Explore codebase FIRST** — read code/context before asking anything.
2. **Never ask more than 1 question at a time.**
3. **Max 3 rounds** — then state assumptions and move forward.

---

## 4 Phases

### Phase 1: Problem Framing
**Goal:** make sure we are solving the right problem.

- Ask 1 question: *"What specific problem are we solving? Who is the user and what will they get?"*
- Wait for the answer. Do not jump to a solution.
- Restate the problem in 1 sentence for confirmation.

### Phase 2: Constraint Discovery
**Goal:** identify constraints BEFORE generating solutions.

Check from code/context (do NOT ask what can be found out):
- Existing interfaces and contracts
- Dependencies that cannot be changed
- Performance/security requirements

Ask only what is NOT visible from the code:
- *"Is there a deadline or budget constraint?"*
- *"Is this MVP or production-grade?"*

### Phase 3: Solution Exploration
**Goal:** 2-3 options with explicit trade-offs.

Format for each option:
```
### Option A: [name]
- Summary: [1-2 sentences]
- Pros: [specific]
- Cons: [specific]
- Effort: [low/medium/high]
- When to choose: [context]
```

**Rules:**
- Minimum 2, maximum 3 options (more = decision paralysis)
- One option is always the simplest (80/20)
- If there is a clear best option — say so directly, do not pretend to be neutral
- Show what is lost with each choice, not only what is gained

### Phase 4: Design Decision
**Goal:** lock in the decision before code.

After an option is chosen:
1. Confirm: *"Summary: we choose [option] because [reason]. Correct?"*
2. Wait for an explicit "yes" / "approved" / "do it"
3. Record the decision in `decisions.md` (if architectural)
4. **Hard gate:** do NOT start coding before confirmation

---

## Anti-patterns

| Don't do | Why | Do instead |
|----------|-----|------------|
| Ask a question that can be found in the code | Wastes time | Read/Grep first, ask only what is non-obvious |
| More than 3 options | Decision paralysis | 2-3 with a clear recommendation |
| Ask 3 questions at once | Overload, shallow answers | 1 question → answer → next |
| Brainstorming for trivial tasks | Overhead > value | Bug in 1 file = just fix it |
| Pretend to be neutral | Directness is valued | Recommend the best option explicitly |

---

## Workflow Integration

- **Plan-First Protocol:** brainstorming = Design phase between Explore and Plan
- **Scope Guard:** if brainstorming goes beyond MVP — call scope-guard
- **Architect agent:** for complex architectural brainstorming — delegate to architect
