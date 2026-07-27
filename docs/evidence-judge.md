# Evidence Judge

> Marking evidence is not the same as judging it. A `[VERIFIED-REAL]` marker
> says what you did — it does not say whether what you did is enough.

## The problem this solves

`rules/integrity.md` defines evidence markers (`[VERIFIED-REAL]`, `[WEAK]`, etc.)
and `hooks/promotion_gate_guard.py` enforces that a claim carries a marker before
promotion. But neither answers the question: **is the evidence strong enough to
support this specific claim, at this scope, for this use case?**

Three variants can all carry `[VERIFIED-REAL]` and still differ by an order of
magnitude in how much confidence the evidence actually justifies. A single
10-sample real-data test and a 10,000-sample replicated test are both
`[VERIFIED-REAL]` — the marker does not distinguish them.

The Evidence Judge closes this gap. It is component 6b of the Oracle-Aware Core:

```
Stage 6 — Evidence Gate
  6a. Checklist gate (verification_plan.yaml — does evidence exist?)
  6b. Evidence Judge  <-- THIS DOCUMENT (is the evidence sufficient?)
  6c. Claim scope alignment (scope must equal what was verified)
```

## The four judgment dimensions

Judge each finalist's evidence across all four dimensions before issuing a verdict.

### Dimension 1 — Strength

Does the evidence tier match the claim tier?

| Evidence tier | What it permits |
|---|---|
| `[VERIFIED-REAL]` on ≥2 independent real-data sources | Full claim — may assert result holds for the stated population |
| `[VERIFIED-REAL]` on 1 real-data source | Qualified claim — scope limited to the exact measurement condition |
| `[VERIFIED-SYNTHETIC]` | Cannot support a real-world claim; supports only "code runs correctly" |
| `[WEAK]` | Hypothesis only; requires escalation to `[VERIFIED-REAL]` before promotion |

**Strength mismatch:** claim asserts broad generalization but evidence covers one
condition → downscope the claim to match the evidence, or gather more evidence.

### Dimension 2 — Scope alignment

Does the population/condition in the claim exactly match the population/condition
that was measured?

Scope mismatches are the most common evidence failure (`rules/integrity.md` Claim
Scope Discipline: "verified subset, claimed whole"). Before judging:

1. Extract the claim's scope from `templates/intent_card.yaml → scope.in_scope`.
2. Extract what was actually measured from `templates/verification_plan.yaml → stage_6_evidence.final_claim.scope`.
3. If they differ → the claim must be narrowed OR additional evidence gathered
   to cover the gap.

### Dimension 3 — Independence

Did at least two tests confirm the result *independently* — different datasets,
different seeds, different engineers, different runs?

| Independence level | Confidence |
|---|---|
| Same test run twice (same seed, same dataset) | No independence — one measurement |
| Two runs, same dataset, different seeds | Partial independence — catches randomness |
| Two datasets from the same source | Partial independence — same distribution risk |
| Two datasets from different sources | Full independence — catches distribution shift |
| Replicated by an independent party | Highest confidence |

A claim supported by a single run on a single dataset earns `[VERIFIED-REAL]`
but only **one** independent measurement — sufficient for a qualified claim, not
a broad generalization.

### Dimension 4 — Reproducibility

Can an independent party reproduce the result in ≤ 4 hours following
`templates/verification_plan.yaml → stage_6_evidence.final_claim` alone?

Reproducibility requirement:
- Exact command or script that produces the result
- Exact dataset reference (URL, hash, or file path)
- Exact environment (Python version, key dependencies)
- Exact metric computation (no ambiguity in what is measured)

If any of these are missing → reproducibility = UNKNOWN → cap confidence at MEDIUM.

## Verdict matrix

Score each dimension 0–3 (see rubric below), sum to a confidence score (0–12):

| Score | Verdict | Action |
|---|---|---|
| 10–12 | **PROMOTE** | Evidence is sufficient; issue the claim with its marker |
| 7–9 | **PROMOTE-QUALIFIED** | Sufficient for a narrowed scope; document exact limitations in `caveats.md` |
| 4–6 | **ITERATE** | Evidence exists but has a specific gap; name the gap, gather targeted evidence |
| 0–3 | **REJECT** | Evidence is insufficient for any claim; route to Null Result Ledger |

### Dimension scoring rubric (0–3 each)

**Strength (0–3)**
- 3: `[VERIFIED-REAL]` on ≥2 independent sources
- 2: `[VERIFIED-REAL]` on 1 source, scope tightly matched
- 1: `[VERIFIED-REAL]` but scope is broader than measurement
- 0: `[VERIFIED-SYNTHETIC]` or `[WEAK]`

**Scope alignment (0–3)**
- 3: Claim scope = measured scope exactly
- 2: Claim scope ⊂ measured scope (narrower than what was measured — conservative)
- 1: Claim scope ⊃ measured scope (broader, some extrapolation)
- 0: Claim scope ∩ measured scope = ∅ (orthogonal — different population)

**Independence (0–3)**
- 3: Two datasets from different sources confirm
- 2: Two runs on same dataset with different seeds
- 1: Single run
- 0: Result reported from memory or described, not run

**Reproducibility (0–3)**
- 3: Exact command + dataset hash + environment pinned; reproduced by a second party
- 2: Exact command + dataset reference; not yet replicated
- 1: Script exists but dataset or environment is ambiguous
- 0: No reproduction path

## Integration with existing gates

| Gate | What it checks | What Evidence Judge adds |
|---|---|---|
| `hooks/promotion_gate_guard.py` | Does a `[VERIFIED-*]` marker exist? | Is the marker sufficient for the claim scope? |
| `rules/integrity.md` markers | What was done | Whether what was done is enough |
| `rules/audit-verification-gate.md` | Are agent `[VERIFIED]` claims tool-confirmed? | Are tool-confirmed claims independently replicated? |
| `templates/verification_plan.yaml` stage_6 | Checklist pass/fail | Quantified confidence score for the claim |

## Anti-patterns

| Anti-pattern | What it corrupts |
|---|---|
| **Marker = sufficient** | `[VERIFIED-REAL]` on 3 samples claimed to generalize to production |
| **Scope creep in the claim** | "Tested on dataset A" → claim says "works in general" |
| **Single-run reproducibility** | "I ran it and it worked" — not reproducible without the exact command + dataset |
| **Independence theater** | Same data re-split and called "two independent tests" |
| **Iterating on evidence post-verdict** | Gathering more data after a REJECT to rescue the claim rather than to answer a new question |

## Output artifact

Fill `templates/evidence_report.yaml` with the judgment. One report per finalist
that reaches Stage 6.

---

**Status:** ACTIVE — component 6b of the Oracle-Aware Evolutionary Mode.
**Command:** `/evolve-solution` runs this judgment at Stage 6 before issuing any
promotion or rejection.
**Depends on:** `rules/integrity.md` (markers), `templates/verification_plan.yaml`
(stage_6 checklist), `hooks/promotion_gate_guard.py` (enforcement).
**Produces:** `templates/evidence_report.yaml` (one per finalist).
