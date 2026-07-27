# Evidence-Safe Loop Coding

> **Don't just prompt agents. Build loops that audit them.**

---

## The Problem with Vanilla Loop-Coding

Modern AI development is moving from one-shot prompts to **recurring agent loops**:
an agent gets a task, executes it on a schedule, reports back, repeats.

This is powerful. It is also dangerous.

A loop amplifies whatever is inside it. If the agent produces good, verified output — the loop
scales that. If the agent produces **Validation Theater** — synthetic tests, circular evidence,
self-confirmed success — the loop scales *that* too, silently, on autopilot.

```
Without evidence gates:

  Every 30 min → Agent runs → Agent creates synthetic data
              → Agent tests itself → Agent reports SUCCESS ✅
              → Loop repeats → You never see the gap
```

This is not automation. It is automated self-deception.

---

## What Evidence-Safe Loop Coding Adds

Every agent loop needs three things that vanilla loop-coding frameworks skip:

| Layer | What it does | Without it |
|---|---|---|
| **Evidence classification** | Labels every claim: `[VERIFIED-REAL]` vs `[VERIFIED-SYNTHETIC]` | Agent reports success on mock data |
| **Audit gate** | Blocks action if evidence is synthetic, round numbers, or self-authored | Deployed hallucination |
| **Memory update** | Records what the loop found, so next cycle doesn't repeat known-bad paths | Infinite retry of dead branches |

---

## Architecture

```
Loop Trigger (schedule / event / condition)
        ↓
  Agent Task (scoped, bounded)
        ↓
  Evidence Classification
  ├── [VERIFIED-REAL]   → proceed
  ├── [VERIFIED-SYNTHETIC] → block, require real data
  └── [UNKNOWN]         → escalate to human
        ↓
  Audit Gate
  ├── F1=1.000 or "100% success"? → Skeptic auto-trigger
  ├── Self-authored test? → [VERIFIED-SYNTHETIC], not valid
  └── Round numbers on real data? → flag
        ↓
  Human Approval  ←  (only when gate flags ambiguity)
  Auto Action     ←  (when gate passes clean)
        ↓
  Memory Update
  ├── Record what was found
  ├── Record what was NOT found (null results count)
  └── Update recurring mistake register
        ↓
  Next Cycle
```

---

## The Loop Spec Template

Before building any recurring agent workflow, fill this spec:

```markdown
# Loop Spec: [Name]

## Trigger
- Interval or event:
- Stop condition (required — loops must have exits):
- Max iterations before human review:

## Agent Task
- Input source (must be external, not self-generated):
- Allowed actions:
- Forbidden actions:

## Evidence Rules
- What counts as [VERIFIED-REAL] in this domain:
- What is automatically [VERIFIED-SYNTHETIC] (mock, seed, inline data):
- What must be marked [UNKNOWN] and escalated:

## Audit Gate
- Skeptic auto-trigger conditions (suspicious perfection, round numbers):
- What requires human approval before action:
- What can auto-proceed when evidence is clean:

## Memory Update
- What to record on success:
- What to record on failure (null results are data, not noise):
- Where results live (.claude/memory/ or project-specific):
```

---

## How This Repo Implements It

| Loop requirement | This repo's mechanism |
|---|---|
| Evidence classification | `rules/integrity.md` — evidence markers, `[VERIFIED-REAL]` hard rule |
| Synthetic detection | `hooks/validation_theater_guard.py` — detects inline synthetic test data |
| Skeptic auto-trigger | `hooks/skeptic_auto_trigger.py` — fires on F1≥0.9, round numbers, "all passed" |
| Audit gates | `hooks/pre_commit_guard.py`, `hooks/promotion_gate_guard.py` |
| Null result tracking | `null_results/INDEX.md` + `hooks/null_retroscan.py` |
| Memory update | `hooks/knowledge_librarian.py`, `hooks/session_save.py` |
| Human escalation | `rules/falsification-ladder.md` § Step 8a (skeptic gate before promote) |

---

## Relation to Langflow and Other Platforms

Platforms like [Langflow](https://github.com/langflow-ai/langflow) make it easy to **build** agent
workflows visually. They handle the loop mechanics well: triggers, routing, tool calls, API
deployment.

What they do not provide: **evidence discipline inside the loop**.

```
Langflow (or any loop platform) = where the agent runs
This repo = how to stop the agent from lying to itself while running
```

If you use Langflow or a similar platform, this methodology layers on top:
- Add evidence markers to your component outputs
- Wire the Audit Gate before any "action" node
- Add a null-result branch to capture what the agent did NOT find
- Require human approval when the gate flags suspicious perfection

---

## Anti-patterns

| Pattern | Why it breaks loops |
|---|---|
| Agent creates test data, then tests itself | Circular: every loop will succeed by construction |
| "100% success" with no external data source | Skeptic auto-trigger fires — flag immediately |
| No stop condition on the loop | Infinite retry of dead branches; null results accumulate silently |
| Memory not updated on null results | Loop loses the knowledge that path X is dead |
| Human approval only on failure | Gates only catch what you expected to fail; misses the unknown-unknowns |

---

## Quick Reference

```
Building a recurring agent loop?
  1. Write the Loop Spec (above) before touching code
  2. Confirm input source is EXTERNAL (not self-generated)
  3. Wire evidence classification before any action node
  4. Set skeptic auto-trigger thresholds (F1 > 0.9, "all passed", round numbers)
  5. Add null-result branch — null results ARE outputs
  6. Add stop condition — all loops must have exits
  7. Test the gate with a known-synthetic input: it must BLOCK
```

---

**See also:**
- [`rules/integrity.md`](../rules/integrity.md) — evidence markers and the Submission Gate
- [`rules/audit-verification-gate.md`](../rules/audit-verification-gate.md) — HIGH/MEDIUM claim verification protocol
- [`docs/anti-hallucination.md`](anti-hallucination.md) — standalone paste-in standard
- [`rules/falsification-ladder.md`](../rules/falsification-ladder.md) — full claim lifecycle
