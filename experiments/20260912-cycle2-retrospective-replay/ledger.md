# Cycle 2, Part 2 — prospective Harness Change Ledger

Part 1 (`decision.md`) established that the ТЗ's causal question — *did the system become
less likely to promote false results and repeat dead ends?* — is **not identifiable
retrospectively**. This file is the prospective half: recorded predictions, each with a
falsifier and a real check-after threshold, per `meta-loop.md` § Harness Change Ledger.

**Deviation from that rule's own format, stated rather than silently taken.** The rule
says four lines "recorded in the PR body … no new file". That assumes one change in one
PR. This cycle spans five merged PRs (#444, #446, #447, #448, #449) and asks a question
that spans all of them; a ledger split across five already-merged PR bodies cannot be
read at the check-after date. So: one file, inside the experiment folder that already
exists, containing exactly the prescribed four-line entries. No gate enforces it — adding
one would be the over-engineering that rule warns against.

---

## Entry 0 — the precondition nobody had measured

**This is the most important entry, and it is not about any mechanism.**

The ТЗ's success criterion is a *reduction*: fewer false promotions, fewer repeated dead
ends. A reduction requires a baseline. Searching this repository's entire history:

| Event named by the criterion | Times recorded |
|---|---|
| a promotion later found false | **0** |
| a dead end re-entered after being killed | **0** |

The single "**this verdict was WRONG and was overturned**" in the corpus
(`20260903-memory-retrieval-repair/decision.md:514`) is a *within-experiment review-round
correction* — a self-review judged a formula correct, a later round with a broader corpus
overturned it, all **before** promotion. That is the process working, not a false
promotion.

So the baseline is not merely unmeasured: **neither event has ever been recordable as a
category.** Any future claim that the mechanisms reduced these rates would be a reduction
from zero-known to zero-known — exactly the unsourced-baseline failure
`skeptic-triggers.md` § "Trigger 2 requires a baseline PROVENANCE" already names
(`baseline_source: NOT "seems about right"`).

```
Change:        nothing yet — this entry records that the measurement does not exist
Prediction:    until a false promotion and a repeated dead end are DEFINED as recordable
               events with a place to record them, no later measurement can support or
               refute the ТЗ's causal claim, in either direction
Falsified if:  someone produces a pre-2026-09-12 record of either event in this
               repository — which would mean the baseline existed and I failed to find it
Check after:   before any future cycle claims the mechanisms improved anything
```

**Consequence for sequencing:** the next real step for the causal question is *not* more
mechanism. It is defining the two events and where they land. Until then every entry
below measures **adoption and behaviour**, not effectiveness — and says so.

---

## Entry 1 — sealed holdout: is it used at all?

Part 1 measured 0/12 retrospective reach; the gate is prospective by construction. Before
asking whether it prevents Goodharted promotions, the prior question is whether anyone
creates the file.

```
Change:        experiments/_template/sealed_holdout.yaml + hooks/sealed_holdout_guard.py
               + promotion_gate_guard.py's 6th condition (PR #444)
Prediction:    of the next 5 experiments reaching a PROMOTE-class verdict, >=1 creates a
               sealed_holdout.yaml without being prompted to
Falsified if:  0 of 5 — the mechanism is infrastructure nobody reaches for, and its
               value is 0 regardless of how correct its logic is
Check after:   5 new PROMOTE-class verdicts, or 2026-12-31, whichever comes first
```

## Entry 2 — DAG: is it used at all?

Both existing `graph.yaml` files were written retroactively by Cycle 1 itself. Zero have
been authored by an experiment in flight.

```
Change:        experiments/_template/graph.yaml + graph.schema.json +
               scripts/check_experiment_graph.py (PR #444, wired into CI by PR #449)
Prediction:    of the next 5 new experiments, >=1 authors a graph.yaml while the
               experiment is running, not retroactively
Falsified if:  0 of 5 — the cross-experiment DAG is unused, and PR #449's index invariant
               is doing the discoverability work the DAG was proposed for
Check after:   5 new experiments, or 2026-12-31
```

## Entry 3 — verdict vocabulary: does the drift continue?

PR #447 found 3 of 13 records using verdict tokens outside the four-word vocabulary
(`RESOLVED`, `NEEDS-HUMAN`, `NEEDS-MORE-DATA`) and deliberately reported them as
`UNKNOWN_TOKEN` rather than normalising. PR #448 declined to widen the vocabulary on 1/13
evidence.

```
Change:        hooks/lib/verdicts.py reports KNOWN / UNKNOWN_TOKEN / UNPARSEABLE,
               vocabulary pinned to the template's four checkboxes (PR #447, #448)
Prediction:    of the next 5 experiments, <=1 uses a verdict token outside the four-word
               vocabulary
Falsified if:  >=3 of 5 do — the vocabulary is descriptively wrong, not the authors, and
               PR #448's restraint about a second axis should be revisited with that
               evidence rather than the 1/13 that justified deferring it
Check after:   5 new experiments, or 2026-12-31
```

## Entry 4 — Rescue Review: was the coverage argument right?

PR #448 declined to add a second status axis specifically because the Rescue Review table
is filled in 1 of 13 experiments. That argument is itself a testable claim.

```
Change:        PR #448 deferred splitting graph.yaml's `status` into claim-level and
               branch-level axes, on the grounds that Rescue Review coverage is ~8%
Prediction:    of the next 5 experiments, <=1 fills a Rescue Review table
Falsified if:  >=3 of 5 fill it — the coverage argument was wrong, and the second axis is
               justified by usage rather than by symmetry
Check after:   5 new experiments, or 2026-12-31
```

## Entry 5 — index invariant: does the gate actually hold?

PR #449 took orphans from 5 to 0 and put `check_experiment_graph.py --check` into CI.

```
Change:        check_index_integrity() + the CI step gating it (PR #449)
Prediction:    zero new orphan experiments reach main
Falsified if:  any experiment directory lands on main with no INDEX.md row — which would
               mean the gate has a hole, most likely its `if: matrix.python-version ==
               '3.12'` condition skipping a run, not the check's logic
Check after:   10 merged PRs, or 2026-12-31
```

---

## What this ledger deliberately does NOT predict

The ТЗ's own headline question. Entries 1–5 measure **adoption and behaviour**, because
Entry 0 shows the effectiveness question has no baseline to move against. Writing a
prediction like *"false promotions will drop"* would produce a number at the check-after
date that no one could interpret — the precise failure this whole cycle has spent five
PRs learning to avoid.

That is not a postponement dressed up as rigour: Entry 0 names the concrete next action
(define the two events and where they are recorded), and it is cheap. What it is not is
another mechanism.
