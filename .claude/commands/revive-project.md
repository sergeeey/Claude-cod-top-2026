---
description: >
  Oracle-Aware Revival Mode — determine whether a stale or abandoned project
  still has live value, and find the smallest experiment that proves or
  kills it. Never a rebuild plan first; audit the oracle, then test.
argument-hint: "<dead/stale project or idea>"
---

Run the **Oracle-Aware Revival Mode** pipeline on this project:

> $ARGUMENTS

This command is the live entry point. The full 7-stage pipeline and its
mapping onto existing machinery (falsification-ladder, oracle-adequacy-gate,
skeptic, validation_theater_guard, promotion_gate_guard, null_results,
parked) is the canonical spec — **read it now and execute its stages in
order:**

@commands/revive-project.md

The Oracle-Adequacy Gate protocol (stage 3) is here — apply it before any
revival experiment runs:

@docs/oracle-adequacy-gate.md

## Non-negotiable invariants (hold even if the spec read is skipped)

1. **No rebuild first.** Refactor, modernize, and new features wait until
   live value is proven — they belong in `intent_card.yaml` as non-goals.
2. **Audit the oracle FIRST.** Fill `templates/oracle_audit.yaml`; an
   INADEQUATE oracle → STOP and fix it before any experiment runs.
3. **The minimal experiment must be smaller than a rewrite.** If the
   smallest test you can name is "rewrite it and see" — that's not an
   experiment yet.
4. **A known dead path needs a revival condition.** Check `null_results/INDEX.md`
   and `parked/INDEX.md` first; blind retry of a killed branch is not a
   fresh attempt.
5. **Evidence or it didn't happen.** No `REVIVE` without a baseline, a
   passing positive control, a failing negative control, real-data
   measurement, and an evidence marker. Synthetic data caps the claim at
   `[VERIFIED-SYNTHETIC]`.
6. **STOP/KILL/PARK are valid outcomes.** Record them — don't treat a
   non-revival as a failed run.

## Templates to fill this run

- `templates/intent_card.yaml` — what claim of remaining value, exactly
  (+ "no rebuild" as an explicit non-goal)
- `templates/oracle_audit.yaml` — can "still has value" be measured honestly?
- `templates/falsification_contract.yaml` — what would prove the revival
  claim wrong?
