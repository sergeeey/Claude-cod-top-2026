---
name: revive-project
description: >
  Oracle-Aware Revival Mode. Determine whether a stale, abandoned, or
  uncertain project still contains live value, and find the smallest
  experiment that proves it — instead of rebuilding on optimism. Use for:
  deciding whether to resurrect a dead branch, an abandoned prototype, a
  stalled research direction, or a "maybe still useful" repo. Triggers:
  /revive-project, "is this project worth reviving", "should we resurrect
  this", "is there still value here". NOT for: a project that is clearly
  still active, or a known rewrite decision already made.
---

# /revive-project — Oracle-Aware Revival Mode

> Do not revive by rebuilding. Revive by testing for remaining value.

This command does not produce a rebuild plan. It runs the **Oracle-Aware
Core** — the same machinery `/evolve-solution` uses — pointed at a different
question: not "what's the best solution?" but "is there still value here,
and what is the smallest experiment that proves or kills it?"

## Usage

```
/revive-project "<dead/stale project or idea>"
```

Examples:
- `/revive-project "GeoMiro scenario engine — stalled 4 months, unclear if data pipeline still works"`
- `/revive-project "the RAG reranker prototype we shelved after the eval looked bad"`
- `/revive-project "this null_results entry — has anything changed that would unkill it?"`

## The pipeline (Stage 0 + 7 stages = the Oracle-Aware Core)

### 0 — Route  ·  *does this even need a revival experiment?*
Before the autopsy, run the **Strategy Router** (`docs/strategy-router.md`).
For a revival question, the router's own algorithm gives the default:
1. Is reviving it obviously yes/no (e.g. "just restart the service")? → **Mode A**, answer directly, stop.
2. Does it just need fact-gathering (e.g. "check whether the API key expired")? → **Mode B**, autopsy only, stop.
3. Do ≥2 Evolutionary characteristics hold (multiple plausible revival
   mechanisms, real cost to choosing wrong)? → continue.
4. Is the consequence irreversible, security/money/science-relevant? → **Mode D**, else **Mode C**.

Declare the mode in `templates/intent_card.yaml → routing_decision` before
proceeding. **Default when unsure is Mode B** — most "is this still alive"
questions resolve at the autopsy step; escalate to Mode C only when the
autopsy itself reveals genuine structural uncertainty (several plausible
revival mechanisms, none obviously right).

### 1 — Autopsy & Prior-Attempt Check  ·  *what killed it, and was it already re-tried?*
Determine the apparent failure mode (unclear value, weak oracle, fake
validation, missing baseline, dependency rot, scope explosion, abandoned
assumption, unverified claim). Then check whether this exact revival was
already attempted and killed.
- Uses: `null_results/INDEX.md`, `parked/INDEX.md`, `rules/falsification-ladder.md`
  (Kill Analysis, `null_results/` vs `parked/` Protocol, Adaptive Iteration
  Branch Rule).
- **Rule:** a path already in `null_results/` is not retried blindly — it
  requires a stated revival condition (changed assumption, data, oracle, or
  mechanism), same as a user-proposed branch in the falsification ladder.
  A path in `parked/` may already carry its own revival condition — check it
  first (Parked Pearl Rule fields).

### 2 — Intent (Live-Value Hypothesis)  ·  *what claim of remaining value, exactly?*
Fill `templates/intent_card.yaml`: the claim ("this still solves X for Y"),
baseline = last known working state (with a number or a reproducible
artifact), single success metric, MCID, and non-goals — **"no rebuild" and
"no modernization" are explicit non-goals by default.** This is also where
the Stage 0 `routing_decision` lives.
- Uses: `templates/intent_card.yaml`, `rules/estimand-ops.md` (L0 question type).

### 3 — Oracle Adequacy  ·  *can "still has value" be measured without self-deception?*
Fill `templates/oracle_audit.yaml` and run the **Oracle-Adequacy Gate**
(`docs/oracle-adequacy-gate.md`). **INADEQUATE → STOP** before any
experiment runs — the same hard stop `/evolve-solution` uses.
- Uses: `docs/oracle-adequacy-gate.md`, `hooks/validation_theater_guard.py`,
  `rules/audit-verification-gate.md`.

### 4 — Minimal Revival Experiment  ·  *smaller than a rewrite, always*
Fill `templates/falsification_contract.yaml` for the smallest experiment
that can validate or kill the live-value hypothesis: reproduce the last
known success, run one real-data sample, isolate one valuable module,
exercise one user workflow end-to-end, or build a thin read-only demo.
Pre-commit kill criteria and a negative control.
- Uses: `templates/falsification_contract.yaml`, `templates/verification_plan.yaml`.
- **Rule:** if the smallest experiment you can define is "rewrite it and see"
  — you don't have an experiment yet, you have a rebuild. Go smaller.
- If more than one plausible revival path exists (conservative repair vs.
  minimal vertical slice vs. high-novelty re-approach), run them as a
  tournament instead of picking one on taste — `docs/variant-tournament.md`.
  No winner is a valid outcome.

#### 4b — Stop-Condition Gate  ·  *only when running the tournament sub-step*
If Stage 4 runs more than one revival path as a tournament, pre-declare stop
conditions before round 1 — **`docs/stop-condition-gate.md`**. At least one
Category B (budget) condition is mandatory; never let a revival tournament
drift indefinitely.
- Uses: `docs/stop-condition-gate.md`, `templates/stop_gate_report.yaml`.
- Verdicts feed the Stage 7 decision: `STOP-PROGRESS` → advance finalist to
  Red-Team as usual. `STOP-BUDGET` → finalist advances but caps at
  `REVIVE-CONDITIONALLY`/`[WEAK]`. `STOP-ORACLE` → halt, return to Stage 3
  and fix the oracle. `STOP-EMPTY` → no survivors, route straight to `KILL`.

### 5 — Red-Team  ·  *attack the revival claim, context-blind*
Hand the surviving live-value hypothesis + falsification contract — and
nothing else — to an independent skeptic.
- Uses: `/skeptic`, `rules/doubt-driven-development.md`,
  `hooks/skeptic_auto_trigger.py`.

### 6 — Evidence Gate  ·  *"runs locally" ≠ "revived"*
A project may be called revived only with: a baseline, a passing positive
control, a failing negative control, a real-data measurement, and an
evidence marker. "Old tests still pass" or "it compiles" is at most
`[VERIFIED-SYNTHETIC]` — never proof the project still delivers value.
- Uses: `docs/evidence-policy.md`, `rules/integrity.md`,
  `hooks/promotion_gate_guard.py`, `hooks/validation_theater_guard.py`.

#### 6b — Evidence Judge  ·  *a marker says what was done, not whether it's enough*
A marker alone does not say whether the evidence is *sufficient* for the
revival claim's scope. Score the surviving hypothesis on the four
Evidence Judge dimensions (strength, scope alignment, independence,
reproducibility) — **`docs/evidence-judge.md`** — and fill
`templates/evidence_report.yaml`.
- Uses: `docs/evidence-judge.md`, `templates/evidence_report.yaml`,
  `templates/verification_plan.yaml` (stage_6 checklist feeds the scope and
  strength dimensions).
- Verdict maps onto the Stage 7 decision: `PROMOTE` → `REVIVE`.
  `PROMOTE-QUALIFIED` → `REVIVE-CONDITIONALLY` with the narrowed scope from
  `evidence_report.yaml → if_promote_qualified`. `ITERATE` → `NEEDS-REAL-DATA`
  (name the gap). `REJECT` → `KILL`.

### 7 — Decision & Ledger  ·  *every outcome is recorded, not just wins*
Return one of:

| Decision | Meaning |
|---|---|
| `REVIVE` | Minimal experiment passed with sufficient real evidence (Evidence Judge: `PROMOTE`). |
| `REVIVE-CONDITIONALLY` | Signal exists, but confidence is capped or scope is narrow (Evidence Judge: `PROMOTE-QUALIFIED`, or Stop Gate: `STOP-BUDGET`). |
| `PARK` | Potential exists, but required evidence/data/resources are unavailable now. |
| `KILL` | Repeats a known dead path, the minimal experiment failed, or Stop Gate fired `STOP-EMPTY` / Evidence Judge returned `REJECT`. |
| `NEEDS-HUMAN` | Depends on strategy, money, ethics, or domain judgment. |
| `NEEDS-REAL-DATA` | Only synthetic/local evidence exists, or Evidence Judge returned `ITERATE` — insufficient to decide. |

`KILL` → fill `templates/null_result_entry.yaml` (Kill Analysis: what died,
what survives) and add the index line to `null_results/INDEX.md`. `PARK` →
write `parked/<id>.md` with an explicit, measurable revival condition
(Parked Pearl Rule fields if the project carries a transferable insight).
- Uses: `templates/null_result_entry.yaml`, `null_results/`, `parked/`,
  `hooks/reject_gate_guard.py`, `hooks/null_retroscan.py`,
  `hooks/null_results_pre_check.py`.

## Hard rules (the mode's invariants)

1. **No rebuild first.** Refactor, modernize, and new features all wait
   until live value is proven — they are non-goals in `intent_card.yaml`,
   not the first move.
2. **Route before autopsy.** Most revival questions are Mode B (gather
   evidence, stop) or even Mode A — escalate to Mode C only when the
   autopsy itself reveals genuine structural uncertainty.
3. **Audit the oracle first.** INADEQUATE oracle → STOP. No exceptions.
4. **The experiment must be smaller than a rewrite.** If it isn't, it's not
   a minimal experiment.
5. **A known dead path needs a revival condition.** Blind retry of a
   `null_results/` entry is a Falsification Ladder anti-pattern, not a fresh
   attempt.
6. **A tournament needs a pre-declared stop condition.** Running multiple
   revival paths without a budget cap (Stage 4b) is drift, not a search.
7. **A marker is not a sufficiency judgment.** `[VERIFIED-REAL]` says what
   was measured; Stage 6b (Evidence Judge) says whether it's enough for the
   claim's scope.
8. **STOP/KILL/PARK are valid, complete outcomes.** A revival assessment
   that ends in "not worth it, here's why" did its job.

## What this command deliberately does NOT do

- It does not produce a rebuild, migration, or refactor plan by default —
  that is a separate, later decision once `REVIVE` is reached.
- It does not treat "the code still runs" or "old tests still pass" as
  revival evidence.
- It does not override a prior `KILL` in `null_results/` without a stated
  revival condition.
- It does not replace `/evolve-solution` — once a project is `REVIVE`d, the
  actual mutation/improvement work goes back through the standard tournament.

## Output of a run

```
intent_card.yaml             (filled — routing_decision + non-goals include "no rebuild")
oracle_audit.yaml            (verdict: ADEQUATE | WEAK | INADEQUATE)
falsification_contract.yaml  (one per revival path)
stop_gate_report.yaml        (only if Stage 4 ran a tournament across revival paths)
skeptic verdict               (CONFIRMED-REAL | WEAKENED | FALSIFIED)
evidence_report.yaml         (Evidence Judge verdict: PROMOTE | PROMOTE-QUALIFIED | ITERATE | REJECT)
decision                      (REVIVE | REVIVE-CONDITIONALLY | PARK | KILL | NEEDS-HUMAN | NEEDS-REAL-DATA)
null_results/<id>.yaml        (for KILL — templates/null_result_entry.yaml, with Kill Analysis)
parked/<id>.md                (for PARK, with revival condition)
```
