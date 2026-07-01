# Strategy Router

> The right tool applied to the wrong problem is still the wrong tool.

## The problem this solves

`/evolve-solution` is a 7-stage pipeline. It is powerful precisely because it
is expensive: oracle audit, falsification contracts, multi-variant tournament,
stop gate, evidence judgment. Applying that pipeline to a task with an obvious
single answer is methodology bloat — slower, more artifacts, no better result.

The inverse failure is also real: applying a direct, one-shot answer to a task
that genuinely needs competing variants produces a solution selected by taste
rather than evidence.

The Strategy Router is the **pre-flight check** for `/evolve-solution`:
classify the task first, then select the mode. Two minutes of routing saves
thirty minutes of mis-applied rigor.

## The four modes

### Mode A — Direct

**When:** the answer is known or easily looked up.

Characteristics:
- Single correct answer exists
- Failure is immediately detectable
- Reversible with trivial cost
- No competing reasonable approaches

Examples: fix a known bug, add a field to a schema, explain a command flag,
refactor a function with a clear spec.

**Action:** answer directly. No intent card, no oracle, no tournament.

---

### Mode B — Research

**When:** the answer requires gathering evidence from external sources before a
decision can be made, but the *question itself* is not contested.

Characteristics:
- The question has a single right framing
- The uncertainty is factual, not structural
- Answer quality depends on source coverage, not on competing designs

Examples: "what does the literature say about X", "does library Y support Z",
"what are the failure modes of technique W in domain D".

**Action:** use `/repo-scout`, `/lit-search`, `Agent(explorer)`, or web search.
Produce a sourced answer. Mark claims with evidence markers. No tournament needed.

---

### Mode C — Evolutionary

**When:** there is genuine structural uncertainty — multiple reasonable
approaches exist, the right one cannot be determined without testing, and
the cost of choosing wrong is non-trivial.

Characteristics (need ≥2 of these):
- ≥3 meaningfully different approaches are plausible
- The selection criterion is measurable (there exists an oracle)
- A wrong choice costs more than a tournament round
- The domain has known failure modes that a single approach might miss

Examples: choosing an architecture for a new component, finding a non-obvious
improvement to a metric that resists obvious fixes, reviving a stalled project
where the blocking assumption is unknown.

**Action:** run `/evolve-solution`. Fill `templates/intent_card.yaml` first.

---

### Mode D — High-Assurance

**When:** the task is Evolutionary *and* the consequences of a wrong choice are
irreversible, affect safety, involve money, or will be cited as scientific
evidence.

Characteristics:
- Mode C criteria are met, AND
- Any of: security boundary, financial flow, published claim, production
  database schema, cryptographic primitive, or compliance-relevant output

Examples: choosing an auth architecture, designing a data migration strategy,
selecting a statistical test for a paper claim, choosing a key derivation
scheme.

**Action:** run `/evolve-solution` with these additional requirements:
- `templates/oracle_audit.yaml` verdict must be ADEQUATE (not WEAK)
- Red-Team stage (Stage 5) is mandatory, not skippable
- Evidence Judge verdict must be PROMOTE (not PROMOTE-QUALIFIED) to ship
- A second independent review is required before any irreversible action

---

## Routing algorithm

Answer these four questions in order. Stop at the first match.

```
1. Is the answer known, obvious, or a simple lookup?
   YES → Mode A (Direct). Stop.

2. Is the uncertainty factual — more sources would resolve it?
   YES → Mode B (Research). Stop.

3. Do ≥2 of the Evolutionary characteristics hold?
   NO  → Mode A or B. The task doesn't need a tournament.
   YES → continue to question 4.

4. Does any High-Assurance characteristic hold?
   YES → Mode D (High-Assurance).
   NO  → Mode C (Evolutionary).
```

**Default when unsure:** Mode B. Gather evidence first; escalate to C if
evidence reveals structural uncertainty.

**Never default to C or D** on the basis that "this feels important". Importance
is not a routing criterion. Irreversibility is.

---

## Methodology bloat detection

A task is being over-routed when:

| Signal | What it means |
|---|---|
| Intent card takes >10 min to fill | The goal is not yet clear enough — clarify first, then route |
| Oracle audit returns INADEQUATE on the first pass | Either the task needs Mode B first, or Mode A is correct |
| Only one variant is generated in Stage 4 | This was a Mode A task dressed as a tournament |
| Stop gate fires at round 1 with STOP-PROGRESS | Correct mode, but the baseline was too low to be interesting |
| Verification plan Stage 6 is trivially YES on all checks | Evidence was never in doubt — Mode A would have sufficed |

If ≥2 of these signals appear during a run, document in `decision.md` why
Mode C was chosen over Mode A.

---

## Under-routing detection

A task is being under-routed when:

| Signal | What it means |
|---|---|
| Direct answer is chosen but multiple colleagues would disagree | Structural uncertainty exists — route to C |
| Research answer is accepted without a baseline | Mode B result is being used as a decision without measurement |
| "Obvious" fix is applied but the same problem recurs | The problem space has structure that Mode A misses |
| Answer accepted without specifying what would falsify it | Mode A applied to a Mode C problem |

---

## Integration with `/evolve-solution`

The `/evolve-solution` command is the executor for Modes C and D only.

```
/evolve-solution trigger
       ↓
Strategy Router (this document) — 30 seconds
       ↓
Mode A → answer directly
Mode B → gather evidence, return sourced answer
Mode C → /evolve-solution full pipeline
Mode D → /evolve-solution + high-assurance requirements
```

The route must be declared explicitly at the start of any non-trivial task:

```yaml
# In intent_card.yaml or as a one-line note before proceeding:
routing_decision:
  mode: C                    # A | B | C | D
  reason: "3 architectures plausible, wrong choice costs > 1 sprint"
  bloat_check: "≥2 Evolutionary characteristics confirmed"
```

A Mode C or D run with no documented routing decision is a gap in the
audit trail — the stop gate and evidence judge cannot verify that the
tournament was necessary.

---

## Anti-patterns

| Anti-pattern | Correct action |
|---|---|
| **Tournament for everything** | Route before running. Most tasks are Mode A or B. |
| **"Feels important" as Mode D trigger** | Check irreversibility, not importance. |
| **Mode B without a sourcing plan** | Name the specific sources before starting research. |
| **Skip routing when pressed for time** | Time pressure is a reason to use Mode A, not to skip routing and use Mode C. |
| **Routing to C because Mode A "might miss something"** | "Might miss something" is not measurable. Use the 4-question algorithm. |
| **Routing to D for every security-adjacent task** | D requires irreversibility AND Mode C criteria. A CORS header change is Mode A. |

---

**Status:** ACTIVE — pre-flight check for `/evolve-solution`.
**Position in pipeline:** runs BEFORE Stage 1 (Intent Card).
**Artifact:** one-line `routing_decision` field in `templates/intent_card.yaml`.
**Depends on:** `commands/evolve-solution.md` (the executor), `docs/oracle-adequacy-gate.md` (Mode D oracle requirement).
