# Worked Example

### Input Excerpt
Domain: Computer Science / Machine Learning

```text
We propose GraphReasoner, a new transformer-based architecture for mathematical reasoning.
GraphReasoner achieves 87.4% accuracy on MathBench-500, compared with 81.2% for the previous best model.
This demonstrates that graph-structured attention is the key mechanism behind mathematical reasoning.
Our ablation shows that removing graph edges reduces accuracy by 9.1 percentage points.
Since transformers are universal approximators, GraphReasoner will generalize to all symbolic reasoning tasks.
We believe this architecture provides a theory of machine reasoning.
```

### Classification

| ID | Presented as | Final level | Evidence source | Confidence | Downgrade reason |
|---|---|---|---|---|---|
| C001 | Model / proposal | Level 5 | IN_TEXT_DIRECT | High | Architecture proposal with specific realization |
| C002 | Fact / benchmark result | Level 1 | IN_TEXT_DIRECT | High | Fact only for MathBench-500 under stated comparison |
| C003 | Mechanistic conclusion | Level 6 | IN_TEXT_INDIRECT | Low | Ablation suggests component importance but does not prove "key mechanism" |
| C004 | Empirical result / ablation | Level 1 | IN_TEXT_DIRECT | Medium | Dataset/protocol not fully described, but result is local |
| C005 | Generalization claim | Level 6 | MIXED_DOWNGRADED | Low | Universal approximation does not prove generalization to all symbolic tasks |
| C006 | Theory claim | Level 6 | NONE | Low | "We believe" signals hypothesis; no theory-level validation shown |

### Adversarial Downgrade Check (Step 5.7)

Only C001, C002, and C004 sit below Level 3, so the adversarial check targets none of
them by rule (see main SKILL.md). No claim in this excerpt reached Level 3+, so
`classification_appropriateness_rate`'s adversarial-check term is vacuously satisfied
(6/6) — every claim's status rests on the plain Step 4 rule, not on surviving an attack.

### Critical Findings
| Type | ID | Finding |
|---|---|---|
| Category error | C003 | Ablation result used as proof of mechanism |
| Category error | C005 | Mathematical property used to infer empirical generalization |
| Category error | C006 | Architecture/model presented as theory |
| Evidence gap | C002 | Benchmark protocol and independent reproduction not shown |
| Domain violation | C005 | Formal approximation property extended to all symbolic reasoning tasks |

### Scoring
```text
total_claims = 6
traceability_rate = 6/6 = 1.00
in_text_evidence_rate = 6/6 = 1.00
classification_appropriateness_rate = 6/6 = 1.00   (no Level 3+ claims, adversarial check vacuous)
category_error_rate = 3/6 = 0.50
consistency_rate = 1.00

rigor_score = 10 × (0.30×1.00 + 0.25×1.00 + 0.20×1.00 + 0.15×(1−0.50) + 0.10×1.00)
rigor_score = 9.25 → 9.3/10  [HEURISTIC — see Deterministic Scoring caveats in SKILL.md]

hardness_index = 2/6 = 0.33
```

### Interpretation
Само разложение rigorous, потому что claims traceable и классифицированы консервативно.
Научная сила excerpt слабее, чем предполагает тон: только 2 из 6 claims — hard
benchmark/ablation факты; 3 claims содержат category errors; архитектура не обоснована
как теория; широкая генерализация не поддержана. rigor_score 9.3/10 отражает, что
разложение ЧЕСТНОЕ (claims правильно понижены), а не что сам excerpt научно силён —
это два разных измерения (см. `hardness_index = 0.33`, отдельно от rigor).

---

## Second Worked Example — Adversarial Downgrade Check In Action

The example above has no Level 3+ claims, so Step 5.7 (Adversarial Downgrade Check)
never actually fires. This example shows the check doing real work.

### Input Excerpt
Domain: Physics

```text
Maxwell's equations describe the behavior of the electromagnetic field.
Our new symmetry principle predicts a small correction term to Coulomb's law at
sub-nanometer scales, arising from a proposed extension of gauge invariance.
This correction has not yet been measured, but it follows deductively once the
extended symmetry is assumed.
```

### Classification (before adversarial check)

| ID | Presented as | Candidate level | Exact quote basis |
|---|---|---|---|
| D001 | Physical law | Level 3-P | "Maxwell's equations describe the behavior of the electromagnetic field" |
| D002 | Predicted correction | Level 6 | "predicts a small correction term... has not yet been measured" |
| D003 | Deductive consequence | Level 3-M (candidate) | "follows deductively once the extended symmetry is assumed" |

### Step 5.7 — Adversarial Downgrade Check

**D001** (Level 3-P candidate): Attack — is Maxwell's equations being cited as a
free-standing claim of THIS text, or is it background context the author assumes as
common ground? The text states it as a bare assertion with no derivation, measurement,
or scope statement in view. Per the Text-Only Justification Rule, external knowledge
that Maxwell's equations are well-verified cannot be used to UPGRADE this claim within
THIS text's audit — the text itself provides no evidence for it.
→ **Downgrade succeeds**: Level 3-P → **Level 0** (`EXTERNAL_NOT_USED_TO_UPGRADE`), with
a note that a well-known law is being invoked as unstated background, not established
in-text.

**D003** (Level 3-M candidate): Attack — "follows deductively" is asserted, but no
proof, derivation sketch, or precise reference is given for the "extended symmetry" or
the deduction itself. Per Mathematics mode: "if doubtless a sketch is absent and the
reference is vague — Level 0."
→ **Downgrade succeeds**: Level 3-M → **Level 0** (no proof sketch present).

**D002** (Level 6): Not subject to Step 5.7 (below Level 3). Stays Level 6 — explicitly
unmeasured, explicitly conditional ("predicts", "has not yet been measured").

### Scoring impact
```text
total_claims = 3
Level 3+ claims subjected to Step 5.7 = 2 (D001, D003)
Both downgraded to Level 0 -> 0/2 survived the adversarial check for that subset
classification_appropriateness_rate = (1 [D002, correctly Level 6] + 0 [D001, D003 downgraded]) / 3 = 0.33
```

Contrast with the OLD (pre-v3.1) formula: without Step 5.7, a less careful first pass
might have left D001 at Level 3-P and D003 at Level 3-M simply because they were
INTERNALLY CONSISTENT with the model's own Step 4 classification — `classification_
appropriateness_rate` would have scored 1.00 (tautologically "correct by its own
rule"), even though neither claim survives a genuine adversarial challenge. This is
exactly the gap Step 5.7 closes.
