# Falsification Ladder (FL) — Enforcement Protocol

## When this rule applies
Research/experiment context only — skip for routine code changes.
Triggers: `experiments/**`, `research/**`, `**/hypothesis*.md`, `**/claim*.md`, any scientific claim or hypothesis validation task.
For pure code changes (bug fix, refactor, feature) — use Standard dev workflow instead.

---

## Core Principle
**Презумпция ложности любого сгенерированного артефакта.**
Claim is valid ONLY after: estimand defined → controls + baseline + stress-test + caveats + go/no-go.

Source: "Falsification Ladder for AI-Assisted Development" (Popper + TDD + CI/CD synthesis)  
Extended: EstimandOps 2.0 (ICH E9(R1), Binette & Reiter 2024) — design-time estimand layer added.

**Stack order (MANDATORY):**
```
EstimandOps (estimand-ops.md)  ← Step -1: WHAT to measure, for whom, under what assumptions
     ↓
Falsification Ladder (this file) ← Steps 0–11: does the claim hold?
     ↓
Skeptic / Evidence Policy         ← are the claims properly marked and reviewed?
```

---

## Tier Decision — Which Ladder to Use

**Trigger = type of change, NOT file count.**

| Change Type | Ladder | Artifacts Required |
|---|---|---|
| Docs, typos, style, cosmetic refactor | **Micro** | inline in PR description |
| New features, bug fixes, tests | **Standard** | `experiments/<id>/` folder |
| Auth, security, schema, architecture | **Full** | `experiments/<id>/` + stress tests |
| Research, AI claims, hypotheses | **Full** | Full 11-step + `null_results/` entry |

**Rule:** When in doubt → upgrade tier. Downgrading requires explicit justification.

---

## Micro-Ladder (≤30 min, PR inline)

Four lines in PR description (EstimandOps L0 + L7 integrated):
```markdown
**Question type:** [ ] descriptive  [ ] predictive  [ ] causal
**Claim:** [what should be true after this change, for which population]
**Check:** [how verified — command or observation]
**Caveat / What this does NOT mean:** [known limitation or non-interpretation]
```

No folder needed. No separate files.

---

## Standard-Ladder (feature / bug fix)

Create `experiments/<id>/` using the template at `experiments/_template/`.

Minimum required files before marking DONE:
- `claim.md` — falsifiable statement
- `controls.md` — positive control + negative control
- `decision.md` — promote / repeat / reject / archive

Optional but recommended:
- `stress_tests.md`
- `caveats.md`

---

## Full-Ladder (arch / security / research)

All 13 steps (EstimandOps pre-steps added). All files required:

| Step | Action | Artifact |
|---|---|---|
| **-2** | **Classify question type** (descriptive / predictive / causal) | `claim.md` — L0 checkbox |
| **-1** | **Define estimand** (population, intervention, comparator, endpoint, summary measure, MCID, ICE) | `estimand.md` |
| 0 | Define falsifiable claim derived from estimand | `claim.md` |
| 1 | Smallest testable hypothesis | `experiment.yaml` |
| 2 | Build minimal artifact | source diff + `manifest.md` |
| 3 | Positive control (known-good input) | `controls.md` |
| 4 | Negative control (known-bad input) | `controls.md` |
| 5 | Define baseline | `baselines/<id>.json` |
| 6 | Run test | `metrics/run.json` |
| 7 | Stress-test (adversarial / edge cases) | `stress_tests.md` |
| 8 | Classify result (promote/repeat/reject) | `result_summary.md` |
| 9 | Document caveats + "what this does NOT mean" | `caveats.md` |
| 10 | Go/no-go decision | `decision.md` |
| 11 | Update project memory | `null_results/<id>.md` if rejected |

**Additional requirement for question_type = causal:**
- Step -1 must include: DAG attached, 4 identifiability assumptions checked, identification strategy named
- Step -1 artifact: `estimand.md` (full canvas) + optionally `dag.md`
- Causal claim without DAG + identifiability = INVALID regardless of test results

---

## Context Asymmetry Rule (Skeptic Agent)

**When invoking skeptic for FL review:**

```markdown
DO give skeptic:
- claim.md (the falsifiable statement)
- The actual code/artifact being reviewed
- controls.md (if exists)

DO NOT give skeptic:
- Session history / reasoning chain
- Success logs from previous runs
- Agent's own confidence statements
- "Background context" about why approach was chosen
```

**Why:** Agreeableness bias — LLM exposed to reasoning chain tends to validate it.
Asymmetric context = independent falsification = stronger review.

**Skeptic prompt template:**
```
You are a falsification agent. Your job is NOT to confirm but to break.
Given: [claim.md contents]
Given: [code/artifact — raw, no framing]
Task: Generate 3 test cases that would FALSIFY this claim.
Then run them (or specify exact commands). Report: CONFIRMED / FALSIFIED / NEEDS-REAL-DATA.
Do NOT consider how the code was built or why. Only: does the claim hold?
```

---

## null_results/ vs parked/ Protocol

**Verdict routing (critical distinction):**

| Verdict | Where | Meaning |
|---|---|---|
| REJECT | `null_results/<id>-<slug>.md` + `null_results/INDEX.md` | Claim falsified — do NOT retry without fundamentally different approach |
| ARCHIVE | `parked/<id>-<slug>.md` + `parked/INDEX.md` | Valid but deprioritized — revisit when conditions change |
| PROMOTE / REPEAT | stay in `experiments/<id>/` | Active or promoted — no archival |

**On REJECT:**
1. Copy filled-in `decision.md` to `null_results/<id>-<claim-slug>.md`
2. Add entry to `null_results/INDEX.md`: `| <id> | <date> | <slug> | REJECT | <why falsified in 10 words> |`
3. Never delete

**On ARCHIVE:**
1. Copy filled-in `decision.md` to `parked/<id>-<claim-slug>.md`
2. Add entry to `parked/INDEX.md` with: why parked + what would trigger revival

**Pre-work check:**
```bash
grep -i "keyword" null_results/INDEX.md  # falsified — don't repeat
grep -i "keyword" parked/INDEX.md        # valid but deferred — might resume
```

---

## Experiment ID Format

```
<YYYYMMDD>-<short-slug>
Example: 20260514-prompt-injection-detection
```

---

## Anti-Patterns (FL violations)

| Violation | Detection | Fix |
|---|---|---|
| "All tests passed" without controls.md | → SKEPTIC-TRIGGER (skeptic-triggers.md rule 3) | Add controls first |
| F1=1.000 or 100% | → SKEPTIC-TRIGGER (rule 1 + 4) | Rerun on real data |
| decision.md written before controls.md | → invalid — regenerate in order | Follow step sequence |
| Micro-ladder for security change | → upgrade to Full, no exceptions | No downgrade |
| Skeptic given session history | → asymmetry violated, re-run skeptic clean | Strip context |
| **claim.md written before estimand** | → estimand not defined, claim is unmeasurable | Fill estimand.md first |
| **Causal claim without DAG** | → identifiability unknown | Draw DAG or downgrade to descriptive |
| **ICE handled as missing data** | → imputation of post-baseline event | Reclassify as ICE, choose strategy |
| **Descriptive result interpreted causally** | → "X is associated with Y → X causes Y" | Remove causal language or add causal layer |
| **Summary measure is HR or OR in heterogeneous pop** | → noncollapsible, drifts with covariates | Switch to risk difference or RMST |
| **MCID not defined** | → "statistically significant" without practical threshold | Define MCID before analysis |

---

## Relationship to Existing Rules (conflict resolution)

### FL vs Doubt-Driven Development (DDD)

DDD Step 1 requires passing to skeptic: Goal + Proposal + Reasoning + Alternatives.
FL Context Asymmetry says: do NOT give skeptic reasoning or context.

**Resolution:** These serve different purposes — use both in sequence:

```
1. DDD first: Red-team the DESIGN before building (skeptic gets full DDD context)
2. FL after:  Validate the ARTIFACT after building (skeptic gets only claim.md + code)
```

DDD skeptic = "Is this the right approach?" (design review, context-heavy)
FL skeptic   = "Does this artifact do what it claims?" (falsification, context-blind)

They are complementary, not contradictory. Both are required for Full-Ladder.

### FL vs integrity.md Submission Gate

integrity.md Submission Gate = external publication (preprints, releases, public posts).
FL decision.md = internal go/no-go (merge to main / deploy).

**Resolution:** FL decision.md is a prerequisite BEFORE Submission Gate, not a replacement.

```
FL decision.md (PROMOTE) → then → integrity.md Submission Gate (if external release)
```

For internal merges only: FL decision.md is the final gate. Submission Gate is not required.

### FL vs skeptic-triggers.md

stress_tests.md is "optional" in Standard-ladder, BUT:
**If Standard-ladder result shows ≥90% success OR "all tests passed" → stress_tests.md becomes REQUIRED.**
Skeptic-triggers Trigger 3 overrides the "optional" label.

| Existing rule | FL relationship |
|---|---|
| `integrity.md` — [VERIFIED] markers | FL adds physical artifact requirement on top |
| `skeptic-triggers.md` — auto-triggers | FL adds context asymmetry + Trigger 3 overrides optional stress_tests |
| `audit-verification-gate.md` — HIGH/MEDIUM gate | FL go/no-go is upstream of this gate |
| `doubt-driven-development.md` — DDD | DDD = design review (before build), FL = artifact validation (after build) |

---

## Quick Reference Card

```
Routine change?          → Micro (PR inline: question_type + claim + check + caveat/not-mean)
Feature / bugfix?        → Standard (claim.md + experiment.yaml + controls + decision)
Auth/arch/research?      → Full (all 13 steps incl. estimand.md)
Research + causal?       → Full + estimand.md with DAG + 4 identifiability checks
>90% success on Standard → stress_tests.md required (overrides "optional")
Skeptic for design?      → DDD protocol (give full context: reasoning + alternatives)
Skeptic for artifact?    → FL protocol (give ONLY claim.md + code, NO history)
Estimand for design?     → EstimandOps protocol (Step -2/-1 BEFORE claim.md)
Experiment REJECT?       → null_results/<id>.md + null_results/INDEX.md
Experiment ARCHIVE?      → parked/<id>.md + parked/INDEX.md
External release?        → FL decision first → then integrity.md Submission Gate

EstimandOps refs:
  Full protocol:         rules/estimand-ops.md
  Estimator lookup:      docs/estimand-to-estimator-map.md
  Canvas template:       experiments/_template/estimand.md
```
