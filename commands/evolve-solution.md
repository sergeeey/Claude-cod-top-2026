---
name: evolve-solution
description: >
  Oracle-Aware Evolutionary Mode. Turn a fuzzy goal into competing, falsifiable
  variants judged by an audited oracle — never a single un-tested "solution".
  Use for: reviving a stalled project with the smallest valuable mutation, finding
  a non-obvious fix (e.g. lowering a RAG hallucination rate), or choosing among
  competing architectures by tournament instead of taste. Triggers: /evolve-solution,
  "evolve a solution", "find the minimal mutation", "tournament of variants",
  "non-obvious way to". NOT for: a known one-line fix, a factual lookup, or any
  task with an obvious single answer.
---

# /evolve-solution — Oracle-Aware Evolutionary Mode

> Search, mutate, compare, select, and remember the evolution of solutions —
> with the judge audited before it is trusted.

This command does not "generate better code". It runs the **Oracle-Aware Core**:
no single solution is accepted without competitors, no oracle is trusted without
audit, no win is claimed without evidence, and no failure is forgotten.

## Usage

```
/evolve-solution "<goal in plain language>"
```

Examples:
- `/evolve-solution "revive this stalled project — find the smallest mutation that returns value"`
- `/evolve-solution "find a non-obvious way to cut our RAG hallucination rate"`
- `/evolve-solution "pick one of N competing architectures via a falsification tournament"`

## The pipeline (Stage 0 + 7 stages = the Oracle-Aware Core)

Each stage maps to machinery this repo already has — this command orchestrates,
it does not reinvent. New hooks: none. New agents: none.

### 0 — Route  ·  *does this task need a tournament at all?*
Before filling the intent card, run the **Strategy Router**
(`docs/strategy-router.md`). Answer 4 questions (≤2 minutes):
1. Is the answer obvious or a simple lookup? → **Mode A** (answer directly, stop)
2. Is the uncertainty factual? → **Mode B** (research, stop)
3. Do ≥2 Evolutionary characteristics hold? → continue
4. Is any consequence irreversible? → **Mode D** (High-Assurance) else **Mode C**

Declare the mode in `templates/intent_card.yaml → routing_decision` before
proceeding. A run with no routing decision is missing its audit trail entry.

### 1 — Intent  ·  *what are we really optimizing?*
Fill `templates/intent_card.yaml`: goal, baseline (with a number), single success
metric, MCID, and ≥3 non-goals. Refuse to continue without a baseline.
- Uses: `rules/estimand-ops.md` (L0 question type), `/estimand-bridge`.

### 2 — Oracle Adequacy  ·  *is the judge worth optimizing against?*
Fill `templates/oracle_audit.yaml` and run the **Oracle-Adequacy Gate**
(`docs/oracle-adequacy-gate.md`). Five checks → ADEQUATE / WEAK / INADEQUATE.
**INADEQUATE → STOP and fix the oracle before any variant runs.**
- Uses: `docs/oracle-adequacy-gate.md`, `hooks/validation_theater_guard.py`,
  `rules/audit-verification-gate.md`.

### 3 — Falsification Contract  ·  *what would prove each variant wrong?*
For every variant that will enter the tournament, fill
`templates/falsification_contract.yaml`: pre-committed kill conditions, a negative
control (known-bad MUST fail) and a positive control (known-good MUST pass).
- Uses: `rules/falsification-ladder.md` (includes the AI-Hypothesis pre-gates),
  `controls.md` pattern.

### 4 — Variant Tournament  ·  *never one solution — always a field*
Generate ≥3 genuinely different variants (diverse mechanisms, not 3 phrasings of
one idea). Score each against the audited oracle from stage 2. Rank by the single
success metric; break ties by simplicity, then reversibility.
- Uses: `/cross-domain` (variant generation from other domains),
  `/combinatorial-creativity`, `/hypothesis-arbiter` (structured selection,
  competing-explanation kill-tests).

### 5 — Red-Team  ·  *attack the survivor, context-blind*
Hand the winning variant + its falsification contract — **and nothing else** — to
an independent skeptic (context asymmetry). It tries to break the claim, not
confirm it.
- Uses: `/skeptic`, `/codex-skeptic`, `rules/doubt-driven-development.md`,
  `hooks/skeptic_auto_trigger.py`.

### 6 — Evidence Gate  ·  *no win without proof*
A variant may be called a win only with: a baseline, a passing positive control, a
failing negative control, a real-data measurement, and an evidence marker. Synthetic
data caps the claim at `[VERIFIED-SYNTHETIC]` — never a validation of the intent.
- Uses: `rules/integrity.md` markers, `hooks/promotion_gate_guard.py`,
  `hooks/validation_theater_guard.py`, `/tester`, `/verifier`, `/reviewer`,
  `/sec-auditor` (run for security-touching variants).

### 7 — Null Result Ledger  ·  *failures are assets*
Every killed or weakened variant is written to `null_results/<id>.md` with a Kill
Analysis (what died, what mechanism survives). Future runs scan it first so the
same dead branch is never re-evolved blindly.
- Uses: `null_results/`, `hooks/reject_gate_guard.py`, `hooks/null_retroscan.py`,
  `hooks/null_results_pre_check.py`.

## Hard rules (the mode's invariants)

1. **No single solution.** A run that produced one candidate did not run a tournament.
2. **Audit the oracle first.** INADEQUATE oracle → STOP. No exceptions.
3. **Pre-commit falsification.** Kill conditions decided after results = rationalization.
4. **Evidence or it didn't happen.** `[VERIFIED-REAL]` for any intent claim; synthetic ≠ validation.
5. **Remember the dead.** Killed variants are recorded, not discarded.

## What this command deliberately does NOT do

- It does not add fitness purely for novelty — novelty without the intent metric is noise.
- It does not promote a winner past the Evidence Gate to `main` automatically;
  promotion stays a human decision (see `rules/integrity.md` Submission Gate).
- It does not replace `/skeptic`, `/decision-gate`, or the falsification ladder —
  it sequences them so the judge is audited before the search trusts it.

## Output of a run

```
intent_card.yaml         (filled)
oracle_audit.yaml        (verdict: ADEQUATE | WEAK | INADEQUATE)
falsification_contract.yaml  (one per finalist variant)
tournament table         (variants × metric × control results)
skeptic verdict          (CONFIRMED-REAL | WEAKENED | FALSIFIED)
decision                 (promote / iterate / reject)
null_results/<id>.md     (for every killed variant)
```
