# claim.md — 20260912-research-evidence-loop-minimal-extension

## Falsifiable claim

Adding a machine-readable cross-experiment dependency graph (`graph.yaml`), a
sealed-holdout final gate (`sealed_holdout.yaml` + `promotion_gate_guard.py`'s
6th condition), an EXPLORE/DEVELOP/VERIFY stage label, a persisted
per-dimension independence breakdown, and an OBSERVE-only priority-score
logger — implemented as **minimal, additive extensions** of existing
mechanisms rather than a new framework — will:

1. Not regress any existing experiment, hook, or gate (every file lacking the
   new optional fields behaves identically to before).
2. Correctly validate against real, historical cross-experiment relationships
   (not just synthetic fixtures).
3. Correctly detect the specific failure classes each mechanism targets
   (cyclic/dangling graph references, a "re-sealed" holdout, an
   under-specified promotion invariant) when deliberately introduced.

## What this claim does NOT mean

- Does NOT claim the mechanisms improve real research-task outcomes (fewer
  false promotions, less repeated work, better EXPLORE→VERIFY transitions) —
  that requires real-task dogfood against real future tasks, explicitly
  deferred to Cycle 2 (see decision.md).
- Does NOT claim the Adaptive Promotion Score formula is valid — it is named
  an unvalidated heuristic and ships as logging infrastructure only.
- Does NOT claim `/evolve-solution`'s 8 stages or `research-methodology.md`'s
  4-stage protocol are now automated — `mode` is a new, separate, optional
  label on top of both, not a change to either.

## Counterfactual Frame

In what world is this claim true? A world where the real gap in this repo's
research methodology was genuinely narrower than a fresh reading of the
motivating ТЗ suggested (Gate 0 confirmed this: most of the requested
capability — independence dimensions, oracle auditing, branch-state tracking —
already existed under different names). In that world, a small, additive,
backward-compatible extension closes the remaining gaps without needing new
machinery. In the world where this claim is FALSE, either a real regression
appears in existing gates, or the new mechanisms turn out to duplicate
existing state rather than add a genuinely new, queryable layer.
