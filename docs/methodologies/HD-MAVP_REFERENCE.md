# HD-MAVP — Hypothesis Decomposition & Multi-Angle Validation Protocol
## Full Reference Architecture

**Status:** Reference specification — NOT a runtime skill  
**Use for:** Designing new skills, manual deep audits, methodological training  
**Runtime skills:** `/claim-decomposer` (atomic core) + `/hd-mavp-router` (orchestrator)

---

## Core Philosophy

> "Don't evaluate claims whole. Decompose → validate atoms → detect contradictions → recompose."

Three failure modes this architecture prevents:
1. **Narrative smoothing** — strong opening/closing hides broken middle
2. **Confirmation tunneling** — only searching for supporting evidence
3. **Cross-atom blindness** — missing when Atom A and Atom D contradict each other

---

## CEVA Framework (Claim Evidence Validity Architecture)

Four layers of claim analysis, in order:

```
Layer 1 — CONTEXT LOCK
  What exactly are we analyzing? Source? Scope? Question type?
  Without this, atoms mean different things to different readers.

Layer 2 — EVIDENCE MAPPING
  For each atom: what evidence supports it?
  Mark: MODEL_OUTPUT vs OBSERVATION vs DERIVATION vs ASSUMPTION
  This distinction matters: model outputs can be confident and wrong.

Layer 3 — VALIDITY CHECK
  For each atom: is the inference valid?
  Types: logical validity, statistical validity, mathematical consistency

Layer 4 — ASSEMBLY
  Do the valid atoms add up to the original claim?
  Or does the claim say more than its atoms actually support?
```

---

## EGTS Protocol (Evidence-Gated Tree Search)

When claim has tree structure (premises lead to sub-conclusions lead to conclusion):

```
Root claim
├── Sub-claim A
│   ├── Evidence A1 → [VERIFIED-REAL / VERIFIED-SYNTHETIC / MODEL_OUTPUT]
│   └── Evidence A2 → [mark]
├── Sub-claim B (depends on A)
│   └── Evidence B1 → [mark]
└── Conclusion C (depends on A + B)
```

**Gate rule:** if any node is MODEL_OUTPUT and load-bearing → the conclusion above it
inherits the same label. Confidence cannot exceed weakest load-bearing node.

**Local-valid / global-fail principle:** each step can be locally correct while
the full chain leads to a wrong conclusion. Always check the assembled chain, not just steps.

---

## Anti-Failure Layer

Common patterns that break claim analysis:

| Pattern | Description | Detection |
|---------|-------------|-----------|
| `illusion_of_rigor` | More structure = more confidence, but structure ≠ correctness | Count mandatory sections; >8 = red flag |
| `llm_judge_bias` | LLM scores its own output, scores are inflated | Who generated the claim + who scored it? Same agent? |
| `false_precision` | "8.7/10" without evidence basis | Where do the numbers come from? |
| `confirmation_tunnel` | Search only for supporting evidence | Were contradicting sources searched? |
| `narrative_smoothing` | Strong start + strong end hides broken middle | Check atoms 3–6 in a 8-step chain specifically |
| `synthetic_validation` | Test data created in same session as claim | Is test dataset external? URL cited? |
| `HARKing` | Hypothesizing After Results Known | Was estimand written before seeing results? |

---

## Pearl Registry

For causal claims: maintain a registry of causal graphs.

```yaml
pearl_registry:
  when_required: "question_type == causal"
  contents:
    - dag: directed acyclic graph (draw or describe)
    - identifiability:
        consistency: "Y = Y^a when A=a"
        positivity: "P(A=a|L) > 0 for all support"
        exchangeability: "Y^a ⊥ A | L (no unmeasured confounders)"
        SUTVA: "no interference, no hidden treatment versions"
    - identification_strategy: "RCT / IV / RD / DiD / g-formula / TMLE"
    - unmeasured_threats: [list known threats + E-value if observational]
  hard_stop: "if any identifiability assumption violated and unrecoverable → 
              causal estimand NOT identifiable → downgrade to descriptive"
```

---

## Human Agency Gate

Before writing final verdict: pause and check.

```
Did I (the model) generate the claim I am now validating?
  YES → label all support as MODEL_OUTPUT, not OBSERVATION
        independent verification required before GO

Did the validation data come from the same session as the claim?
  YES → label [VERIFIED-SYNTHETIC], not [VERIFIED-REAL]
        external data required for hypothesis validation claims

Is the judge (scoring this) the same process as the claimant?
  YES → scores are biased upward; require independent review
```

---

## Evidence-Gated Synthesis Rule

**The synthesis can only be as strong as its weakest load-bearing node.**

```
IF any_blocking_atom == MODEL_OUTPUT:
  max_claim_strength = HYPOTHESIS (not VERIFIED)

IF any_blocking_atom == VERIFIED-SYNTHETIC:
  max_claim_strength = VERIFIED-SYNTHETIC (valid for unit tests, not hypothesis validation)

IF all_blocking_atoms == VERIFIED-REAL:
  claim_strength = min(confidence of individual atoms)
```

---

## Multi-Angle Validation: 6 Angles

When atoms are validated, use these angles (parallelize independently):

| Angle | Question | Tool |
|-------|----------|------|
| Mathematical consistency | Do the formulas derive correctly? | Math-Code Trace |
| Statistical validity | Are inferences from data sound? | `/consilience` path 2 |
| Empirical support | Does real-world data agree? | `/consilience` path 2, 5 |
| Adversarial critique | What's the strongest counter-argument? | `/skeptic` |
| Literature support | What does prior work say? | `/consilience` path 1 |
| Mechanistic coherence | Does the proposed mechanism make sense? | `/consilience` path 3 |

**Critical:** parallelize only after `claim-decomposer` completes Contradiction Map + Recomposition.
Multi-angle fan-out on un-decomposed claim = missing cross-angle contradictions.

---

## Full Pipeline Reference

```
/hd-mavp-router quick mode:
  claim-decomposer → gate

/hd-mavp-router full mode:
  claim-decomposer
    → [if Gate = GO or CONDITIONAL]
    → sci-evidence falsify
    → consilience
    → proof-ladder
    → synthesis

/hd-mavp-router math_code mode:
  claim-decomposer (with Math-Code Trace)
    → [for each DIVERGENT atom]
    → targeted fix / flag

/hd-mavp-router contradiction mode:
  claim-decomposer (focus on Contradiction Map)
    → skeptic (attack blocking atoms)
    → hypothesis-arbiter (if atoms became competing hypotheses)

/hd-mavp-router decision_record mode:
  claim-decomposer
    → proof-ladder
    → write to decisions.md
```

---

## Integration Points in Existing Skills

Suggested pre-step language to add to existing skills:

**consilience:**
> "If claim has ≥4 sub-assertions or contains formulas → run `/claim-decomposer` first
> to get atom map. Use surviving atoms as inputs to each consilience path."

**proof-ladder:**
> "If hypothesis is complex (multiple premises) → `/claim-decomposer` before building ladder.
> Focus ladder on blocking atoms, not the full narrative."

**hypothesis-arbiter:**
> "If source claim has internal contradictions → `/claim-decomposer` first.
> Contradicting atoms become competing hypotheses for arbiter."

**skeptic:**
> "Attack blocking atoms from `/claim-decomposer` output, not the whole narrative.
> Asymmetric context: give skeptic only claim register + blocking atoms, not reasoning chain."

---

## When This Architecture Was Conceived

HD-MAVP emerged from the observation that:
- Single-agent review of complex claims suffers from narrative smoothing
- Existing skills (consilience, proof-ladder, hypothesis-lab) operate on whole claims
- The gap was: no skill decomposed claims into atoms first, then looked for cross-atom contradictions
- Atomic decomposition + Contradiction Map = the unique operation not present elsewhere

The claim-decomposer skill extracts this unique operation.
The hd-mavp-router orchestrates existing skills around it.
This document preserves the full methodological reasoning.

---

**Last updated:** 2026-06-10  
**Origin:** HD-MAVP skill definition, evaluated 8.7/10 (2026-06-10)  
**Runtime implementation:** `/claim-decomposer` + `/hd-mavp-router`
