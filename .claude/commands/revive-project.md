---
description: >
  Oracle-Aware Revival Mode — determine whether a stale or abandoned project
  still has live value, and find the smallest experiment that proves or
  kills it. Never a rebuild plan first; route, audit the oracle, then test.
argument-hint: "<dead/stale project or idea>"
---

Run the **Oracle-Aware Revival Mode** pipeline on this project:

> $ARGUMENTS

This command is the live entry point. The full Stage 0 + 7-stage pipeline
and its mapping onto existing machinery (strategy-router, falsification-
ladder, oracle-adequacy-gate, stop-condition-gate, skeptic,
validation_theater_guard, promotion_gate_guard, evidence-judge,
null_results, parked) is the canonical spec — **read it now and execute its
stages in order:**

@commands/revive-project.md

The Strategy Router (stage 0) decides whether this even needs a revival
experiment — apply it first:

@docs/strategy-router.md

The Oracle-Adequacy Gate protocol (stage 3) is here — apply it before any
revival experiment runs:

@docs/oracle-adequacy-gate.md

If Stage 4 runs a tournament across multiple revival paths, the
Stop-Condition Gate (stage 4b) governs when to stop:

@docs/stop-condition-gate.md

The Evidence Judge (stage 6b) scores whether the surviving evidence is
sufficient for the revival claim's scope — apply it before the final
decision:

@docs/evidence-judge.md

## Non-negotiable invariants (hold even if the spec read is skipped)

1. **Route before autopsy.** Most revival questions are Mode B (gather
   evidence, stop) — escalate to Mode C only when the autopsy itself
   reveals genuine structural uncertainty. Record `routing_decision` in
   `templates/intent_card.yaml`.
2. **No rebuild first.** Refactor, modernize, and new features wait until
   live value is proven — they belong in `intent_card.yaml` as non-goals.
3. **Audit the oracle FIRST.** Fill `templates/oracle_audit.yaml`; an
   INADEQUATE oracle → STOP and fix it before any experiment runs.
4. **The minimal experiment must be smaller than a rewrite.** If the
   smallest test you can name is "rewrite it and see" — that's not an
   experiment yet.
5. **A known dead path needs a revival condition.** Check `null_results/INDEX.md`
   and `parked/INDEX.md` first; blind retry of a killed branch is not a
   fresh attempt.
6. **A tournament needs a pre-declared stop condition.** Fill
   `templates/stop_gate_report.yaml` if Stage 4 runs more than one revival
   path — no open-ended search.
7. **A marker is not a sufficiency judgment.** Score the surviving evidence
   with the Evidence Judge (`templates/evidence_report.yaml`) before
   deciding — `[VERIFIED-REAL]` alone does not mean the evidence is enough
   for the claim's scope.
8. **STOP/KILL/PARK are valid outcomes.** Record them — don't treat a
   non-revival as a failed run.

## Templates to fill this run

- `templates/intent_card.yaml` — what claim of remaining value, exactly
  (+ `routing_decision` from stage 0, + "no rebuild" as an explicit non-goal)
- `templates/oracle_audit.yaml` — can "still has value" be measured honestly?
- `templates/falsification_contract.yaml` — what would prove the revival
  claim wrong?
- `templates/stop_gate_report.yaml` — only if Stage 4 runs a multi-path
  tournament
- `templates/evidence_report.yaml` — Evidence Judge verdict before the
  final decision
- `templates/null_result_entry.yaml` — if the verdict is `KILL`
