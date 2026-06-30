---
description: >
  Oracle-Aware Evolutionary Mode — turn a fuzzy goal into competing, falsifiable
  variants judged by an oracle that is audited before it is trusted. Never one
  solution; audit the judge first.
argument-hint: "<goal in plain language>"
---

Run the **Oracle-Aware Evolutionary Mode** pipeline on this goal:

> $ARGUMENTS

This command is the live entry point. The full 7-stage pipeline and its mapping
onto existing machinery (estimand-ops, falsification-ladder, skeptic,
validation_theater_guard, promotion_gate_guard, null_results) is the canonical
spec — **read it now and execute its stages in order:**

@commands/evolve-solution.md

The Oracle-Adequacy Gate protocol (stage 2) is here — apply it before any
variant runs:

@docs/oracle-adequacy-gate.md

## Non-negotiable invariants (hold even if the spec read is skipped)

1. **No single solution.** Always ≥3 genuinely different variants — a run that
   produced one candidate did not run a tournament.
2. **Audit the oracle FIRST.** Fill `templates/oracle_audit.yaml`; an INADEQUATE
   oracle → STOP and fix it before evolving. Optimizing against a bad judge
   manufactures false confidence (Goodhart).
3. **Pre-commit falsification.** Fill `templates/falsification_contract.yaml` per
   finalist variant — kill conditions decided *after* results are rationalization.
4. **Evidence or it didn't happen.** No "success" without a baseline, a passing
   positive control, a failing negative control, a real-data measurement, and an
   evidence marker. Synthetic data caps the claim at `[VERIFIED-SYNTHETIC]`.
5. **Remember the dead.** Every killed variant → `null_results/<id>.md` with a
   Kill Analysis (what died, what mechanism survives).

## Templates to fill this run

- `templates/intent_card.yaml` — what we are actually optimizing (+ non-goals)
- `templates/oracle_audit.yaml` — is the judge worth optimizing against?
- `templates/falsification_contract.yaml` — what would prove each variant wrong?
