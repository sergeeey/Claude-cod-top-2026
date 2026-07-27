---
name: innovation-preservation
description: >
  Protect non-obvious ideas from premature falsification kill. The standard
  skeptic and red-team are calibrated to kill weak claims — which is correct.
  But they can also kill a rare good idea if the formulation was weak while the
  underlying mechanism is sound. Invoke BEFORE writing a null result, when:
  (1) the killed variant felt "almost right" — high score but one blocker;
  (2) the mechanism is novel and the kill condition was a formulation edge case;
  (3) a parked pearl might apply to the current run.
  Triggers: /innovation-preserve, "before writing null result", "resurrection
  review", "almost worked", "pearl check", "formulation vs mechanism". Do NOT
  invoke to rescue ideas that were cleanly falsified — this is for ambiguous
  kills, not motivated resurrection.
---

# Innovation Preservation

> The hardest thing in falsification discipline is distinguishing a dead idea
> from a wrongly-killed one. This skill handles exactly that boundary.

The standard null result pipeline (Falsification Ladder → Null Result Ledger)
is calibrated for safety: when in doubt, kill. This is correct for most claims.
But it creates a systematic failure mode: a genuinely novel mechanism wrapped in
a weak formulation gets killed and filed in `null_results/` before anyone checks
whether the mechanism itself is the casualty or only the phrasing.

This skill adds one gate between "FALSIFIED by skeptic" and "write null result":
the **Formulation/Mechanism Distinction**.

---

## Gate 1 — Formulation vs. Mechanism Kill Analysis

**Run this before writing any null result.**

| Question | What to check |
|---|---|
| Was the kill triggered by an edge case in the formulation? | Narrow condition, specific dataset, specific parameter range |
| Does the kill condition generalize to ALL possible formulations? | If yes → mechanism is dead. If no → formulation is dead. |
| Can the mechanism be stated in a weaker, still falsifiable form? | If yes → consider Resurrection Review |
| Would a different oracle have produced a different verdict? | If yes → the oracle may be the problem, not the mechanism |

**Decision tree:**

```
Kill condition fired
       ↓
Is the mechanism itself contradicted by first principles?
  YES → hard_killed. Write null result. Stop.
  NO  → continue

Did the kill fire on ALL plausible formulations of this mechanism?
  YES → killed. Write null result. Stop.
  NO  → this is a formulation kill. Continue to Resurrection Review.
```

---

## Gate 2 — Resurrection Review

A formulation kill does not automatically kill the mechanism. Resurrection
Review asks: "what is the minimal reformulation that preserves the mechanism
and avoids the kill condition?"

**Required inputs:**
- The original claim (`claim.md` or `falsification_contract.yaml`)
- The specific kill condition that fired
- The mechanism statement (one sentence, no jargon)

**Protocol:**

1. State the mechanism: "The mechanism is [X]."
2. State what the kill ruled out: "The kill ruled out [Y]."
3. Ask: "Is Y the mechanism or a property of this formulation?"
4. If Y ≠ mechanism: propose the minimal narrowing.

**Minimal Narrowing Rule (hard constraint):** change exactly ONE element
of the claim. The narrowing must be:
- More specific (not more general)
- Still falsifiable with a concrete test
- Not motivated by "wanting to save the idea" — motivated by "Y is not X"

If you cannot propose a minimal narrowing without changing the mechanism →
the mechanism is the casualty. Write the null result.

**Evidence level for the resurrected formulation:** `[HYPOTHESIS]`. It does
NOT inherit the prior run's evidence. It starts a new experiment branch.

---

## Gate 3 — Pearl Gate (mandatory scan before any null result)

The Pearl Gate is not about saving the killed variant. It is about capturing
a transferable insight that the failed experiment surfaced as a side effect.

**Three questions:**

1. "Did this experiment reveal anything that was NOT the hypothesis but IS
   independently testable?" → Pearl candidate
2. "Did this experiment constrain a parameter range that is useful for the
   next experiment?" → add to `assumptions_untouched` in null result
3. "Does the kill condition itself reveal something about the oracle?" →
   check oracle adequacy before the next run

**If a pearl candidate is found:**

Add one line to `pearl_registry/INDEX.md`:

```
| <date> | <source_run_id> | <observation> | <falsifiable_prediction> | <trigger_condition> | <next_check> | [CANDIDATE] |
```

`[CANDIDATE]` means `next_check` date is not yet filled. Fill it within 2
weeks or the candidate decays.

---

## Gate 4 — Speculative Branch Register

Some ideas survive their kill technically but are not ready for a new experiment:
too early, wrong context, missing prerequisite data. These are not parked (too
active) and not alive (not promoted). They are **speculative branches**.

**Format (append to `null_results/<id>.md`):**

```yaml
speculative_branch:
  mechanism: ""          # the mechanism that survived
  blocked_by: ""         # what prevents a new experiment now
  revival_signal: ""     # the specific observable event that unlocks this
  next_check: ""         # ISO date — without this the branch decays in 4 weeks
  status: speculative    # speculative | ready | dormant
```

**Rule:** a speculative branch that has not been reviewed by its `next_check`
date is downgraded to `dormant`. Dormant branches are not checked automatically.

---

## Integration with `/evolve-solution`

This skill runs AFTER Stage 5 (Red-Team) when the skeptic returns FALSIFIED,
and BEFORE Stage 7 (Null Result Ledger).

```
Stage 5: Red-Team returns FALSIFIED
       ↓
/innovation-preservation: run Gates 1–4
       ↓
Gate 1 result: hard_killed → Stage 7 (write null result)
Gate 1 result: formulation kill → Gate 2 (Resurrection Review)
               Resurrection: minimal narrowing found → new experiment branch
               Resurrection: no narrowing possible → Stage 7
Gate 3: Pearl found → pearl_registry entry
Gate 4: Speculative branch → append to null result
```

---

## Anti-patterns

| Anti-pattern | Why it is wrong |
|---|---|
| **Resurrection after a clean mechanism kill** | If first principles rule it out, no reformulation helps. Stop. |
| **Resurrection motivated by investment** | "We spent 3 weeks on this" is not a technical argument. |
| **Multi-assumption narrowing** | Minimal relaxation: one element. Two changes = new experiment, not rescue. |
| **Pearl without next_check** | Undated pearls decay into noise within 2 weeks. Always set a date. |
| **Speculative branch without revival_signal** | "When we have more data" is not a signal. Name the specific observable. |
| **Skipping Gate 1 and jumping to Gate 2** | Gate 1 is the filter. Gate 2 is only for formulation kills, not all kills. |

---

**Status:** ACTIVE — optional gate between Stage 5 and Stage 7 of `/evolve-solution`.
**When to invoke:** signal is "almost worked" or "mechanism felt right".
**When NOT to invoke:** clean falsification by first principles; kill was clean
and comprehensive; motivated reasoning is suspected.
**Produces:** narrowed formulation (→ new experiment branch) OR confirmed null
result with pearl + speculative branch entries.
