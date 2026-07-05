<!-- BSV — Brief Skill View | поиск: BSV
Скил   : brainstorming
TL;DR  : Мозговой штурм идей без критики
Вызов  : 'брейншторм', 'придумай варианты', `brainstorm:`
НЕ для : Принятие финального решения
-->

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
2. **Never ask more than 1 open-ended question at a time.** Multiple enumerable
   choices (pick a stack, pick a scope tier, yes/no on a tradeoff) may be
   clustered into a single `AskUserQuestion` call instead of separate turns —
   clustering applies to closed-choice questions, not to open framing questions.
3. **Max 3 rounds** — then state assumptions and move forward.
4. **If goal clarity scores near 0** (the user has "something" in mind but
   can't yet state it), show 2-3 concrete example scenarios from this project's
   domain before the first question — a vague "what do you want" gets a vague
   answer; "here's what this could look like: A, B, C — which is closer, or
   something else?" gives the user something to react to. Skip this when goal
   clarity is merely low-but-nonzero — examples anchor answers unnecessarily
   when the user already has real direction, narrowing them toward the examples
   shown (source: launch-your-agent, Anthropic reference skill).

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

**Credential deferral:** if the design will eventually need a secret/credential
(API key, OAuth token, webhook URL) that isn't available right now, don't stall
the whole design on it. Do every piece of design and staging work that doesn't
need the credential first, then name **exactly** what's needed and **exactly**
where to get it in one line ("you'll need a Slack webhook — create one at
api.slack.com/apps → Incoming Webhooks"), so the user can fetch it in parallel
while the rest proceeds. Never let "we're missing a credential" block work that
doesn't actually depend on it.

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
| Ask 3 open-ended questions at once | Overload, shallow answers | 1 open question → answer → next (enumerable choices may still cluster via `AskUserQuestion`) |
| Brainstorming for trivial tasks | Overhead > value | Bug in 1 file = just fix it |
| Pretend to be neutral | Directness is valued | Recommend the best option explicitly |

---

## Workflow Integration

- **Plan-First Protocol:** brainstorming = Design phase between Explore and Plan
- **Scope Guard:** if brainstorming goes beyond MVP — call scope-guard
- **Architect agent:** for complex architectural brainstorming — delegate to architect

## Gotchas
- Always explore codebase BEFORE asking questions — context before interview
- If ambiguity score stays >20% after 3 rounds — proceed with assumptions stated explicitly
