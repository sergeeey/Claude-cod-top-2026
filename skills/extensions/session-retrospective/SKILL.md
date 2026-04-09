---
name: session-retrospective
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-04-09]
  Post-session analysis skill. Reviews decisions made, what worked,
  what didn't, and captures next steps into activeContext.md.
  Triggers: /retro, retro:, session review, what did we do, wrap up session,
  session summary, end of session.
effort: minimal
tokens: ~800
---

# Session Retrospective

## When to Use

After any meaningful work session — sprint, debugging marathon, feature implementation.
Takes 2-3 minutes, saves 10-15 minutes of re-orienting next session.

Trigger with: `/retro` or `retro:` prefix on any prompt, or explicitly ask "wrap up session".

## Workflow

### Step 1 — Collect session data

Read `activeContext.md` auto-commit log section. Check `git log --oneline -10` for actual
commits made. Never invent commits — [VERIFIED] only.

### Step 2 — Answer 4 questions

**What was decided?**
List architectural/design decisions made this session. Tag each with [VERIFIED] if code was
written, [INFERRED] if discussed only.

**What worked?**
Patterns, approaches, or tools that delivered results faster than expected.
Tag for `patterns.md` with `[REPEAT]`.

**What didn't work?**
Approaches that failed, dead ends, wrong assumptions.
Tag for `patterns.md` with `[AVOID]`.

**What's next?**
Top 3 unfinished items or natural follow-ups. These become the next session's
`## Current Focus`.

### Step 3 — Write output

Present retrospective in the Output Format below.
If significant patterns found → remind user to update `~/.claude/memory/patterns.md`.
Offer to update `activeContext.md` ## Current Focus with next session's top item.

## Output Format

```markdown
### Session Retrospective — [date]

**Decisions made** [VERIFIED / INFERRED]
- ...

**What worked** → [REPEAT] in patterns.md
- ...

**What didn't** → [AVOID] in patterns.md
- ...

**Next session focus** (top 3)
1. ...
2. ...
3. ...

*Duration: ~[N] commits | Files changed: ~[N]*
```

## Integration with Memory Protocol

After retrospective, optionally update:

| File | What to add |
|------|------------|
| `activeContext.md` → `## Current Focus` | Top item from "Next session focus" |
| `activeContext.md` → `## Auto-commit log` | `## Retrospective [date]: [1-line summary]` |
| `~/.claude/memory/patterns.md` | `[REPEAT]` and `[AVOID]` entries with `[×N]` counter |
| `~/.claude/memory/decisions.md` | Architectural decisions tagged [VERIFIED] |

## Gotchas

- Do NOT invent commits — read `git log` to verify actual work done
- If session had 0 commits → still useful to capture decisions and blockers
- Keep output ≤ 30 lines — this is a summary, not a transcript
- Evidence Policy applies: don't present [INFERRED] decisions as [VERIFIED]
- One retrospective per session — don't run mid-session, it will be incomplete
