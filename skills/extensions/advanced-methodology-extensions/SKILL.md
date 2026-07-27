---
name: advanced-methodology-extensions
description: >
  Specialized technique extensions for the Oracle-Aware Core — for when the standard
  Variant Tournament needs a more powerful tool in one slot. Invoke when:
  (1) tournament variants are structurally similar and you need to force diversity;
  (2) the evaluation oracle produces binary pass/fail but you need gradient signal;
  (3) a second model is needed to catch shared Claude blind spots before promotion;
  (4) the variant must survive an adversary's attack, not just a quality review.
  Triggers: /advanced-methodology, "extend the tournament", "cross-model review",
  "PRM scoring", "fraud attack", "structural diversity". NOT a replacement for the
  Core — adds one specialized tool per slot, not a new pipeline.
---

# Advanced Methodology Extensions

These techniques extend specific stages of `/evolve-solution` when the standard
tool in that slot is insufficient. Each maps to exactly one stage. Use one
extension at a time — stacking multiple extensions on a single run risks
methodology theater.

## When to use this skill

Do not invoke by default. Check first:

| Signal | Extension indicated |
|---|---|
| Tournament variants all share the same core mechanism | Structural Diversity Enforcer (Stage 4) |
| Oracle is binary; can't tell WHY a variant fails | PRM-lite intermediate scoring (Stage 4) |
| Skeptic is Claude; Claude wrote the variant | Cross-Model Critic (Stage 5) |
| Finalist touches security, fraud, or financial flow | Fraud Attack Simulator (Stage 5) |
| Simulation produces results but you need an equation | Simulation-to-Equation extraction (Stage 6) |

---

## Extension 1 — Structural Diversity Enforcer (Stage 4 add-on)

**Problem:** five variants that all use the same mechanism but with different
parameters are not a tournament — they are a parameter sweep. Structural
diversity means different causal paths to the goal, not different settings.

**How it works:**

Before scoring begins, build a Mechanism Map:

```yaml
variant_id: V1
mechanism: "cache the embedding, reuse on re-query"   # causal path
assumption_set: [embeddings are stable, queries repeat]
independent_of: [V2, V3]   # yes/no: does this variant's mechanism differ from Vn?
```

If any two variants share the same mechanism and assumption_set → merge them
into one, or replace one with a genuinely different causal path.

**Minimum diversity requirement:** ≥2 mechanism axes must differ across the
finalist field. Mechanism axes: computational path, data structure, timing,
scope (local/global), direction (push/pull), trust assumption.

---

## Extension 2 — PRM-lite Intermediate Scoring (Stage 4 add-on)

**Problem:** tournament oracle gives a final score but not intermediate
credit. A variant that gets 70% of the way to the goal looks identical to
one that fails at step 1. You can't steer the field from a scalar output.

**PRM-lite protocol:**

Decompose the task into N reasoning steps (3–7). For each step, score the
variant's intermediate output on that step alone:

```yaml
variant: V2
steps:
  - step: "retrieve relevant context"
    score: 0.85   # 0.0–1.0
    signal: "top-3 contains the answer 85% of the time"
  - step: "generate candidate answer"
    score: 0.40
    signal: "correct format but factual error in 60% of cases"
  - step: "verify answer against source"
    score: 0.10
    signal: "verification is skipped in 90% of traces"
final_score: 0.40
bottleneck_step: "verify"
```

The bottleneck step is the priority for the next mutation, not the final score.

**Constraint:** PRM-lite requires a decomposable oracle. If you cannot define
intermediate steps before running the variant, this extension does not apply.

---

## Extension 3 — Cross-Model Critic (Stage 5 replacement)

**Problem:** the standard Red-Team (Stage 5) uses a Claude skeptic to review a
Claude-generated variant. Shared training data creates shared blind spots.
High-confidence claims that both generate AND verify should face a model with
different training.

**Protocol:**

Route the finalist + falsification contract to a different model for adversarial
review. The prompt is context-blind (FL asymmetry rule):

> "You are a falsification agent. Your only inputs are the claim and the code.
> Generate 3 test cases that would falsify this claim. Report: CONFIRMED /
> FALSIFIED / NEEDS-REAL-DATA. Do not consider how the code was built."

**Required:** the review model must be architecturally different from the
generating model (different training corpus, different architecture family).
Same-family variants of the same model do not satisfy the cross-model
requirement.

**When NOT to use:** if the alternative model cannot run code or inspect
the artifact type (e.g., a text-only model reviewing compiled output), use
the standard Claude skeptic with an explicit limitation noted in `caveats.md`.

---

## Extension 4 — Fraud Attack Simulator (Stage 5 add-on)

**Problem:** standard red-teaming checks quality and correctness. It does not
simulate an adversary who is trying to exploit the variant for personal gain.
Security, financial, and fraud-adjacent variants need a different attacker model.

**Attacker personas (pick relevant ones):**

| Persona | What they try |
|---|---|
| Opportunist | exploit ambiguous edge cases without deep knowledge |
| Insider | abuse privileged access or pre-existing trust |
| Systematic abuser | find repeatable patterns at scale |
| Social engineer | bypass technical controls through human factors |
| Regulatory arbitrageur | comply with letter while violating intent |

**For each persona:** identify the top 2 attack surfaces in the variant,
describe a concrete attack scenario, specify what the variant would need
to prevent it.

**Output:** `skeptic_verdict.md` extended with `fraud_attack_surfaces` section.

---

## Extension 5 — Simulation-to-Equation (Stage 6 add-on)

**Problem:** the winning variant is a simulation or black-box model. The
Evidence Gate can verify that it works, but not WHY it works. An equation
makes the mechanism transparent, auditable, and falsifiable by theory.

**Protocol:**

1. Generate N outputs from the simulation across a parameter range
2. Identify the dominant functional form (linear, power law, exponential,
   logistic) using log-log and semi-log plots
3. Fit the equation to the outputs
4. Compute residuals — residuals > 10% of output range = equation is incomplete
5. Report the equation with confidence bounds, not as a discovery but as a
   description of what the simulation does

**Evidence level:** the extracted equation is `[INFERRED]` from simulation
outputs. It is NOT `[VERIFIED-REAL]` unless validated on data that was not
used for fitting.

---

**Status:** ACTIVE — extensions for `/evolve-solution` Stages 4–6.
**When to choose:** consult the trigger table at the top before invoking.
**Does not replace:** `docs/variant-tournament.md`, `docs/evidence-judge.md`,
or any Core stage — adds one specialized tool per slot.
