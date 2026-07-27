# Perelman-Style Audit Protocol

**Core principle:** Good verification doesn't require genius — it requires the right process,
a monotone control quantity, and honest treatment of singularities.

Source: Perelman's proof of Poincaré conjecture (2002–2003) → universal methodology.
Integrated into FL stack as claim_entropy + no-collapse tests + surgery log.

---

## Stack position

```
FL (falsification-ladder.md)         ← "does the claim hold?"
     ↓
Perelman Audit (this file)           ← "is the claim well-formed and honestly promoted?"
     ↓
integrity.md / evidence policy       ← "are markers correctly assigned?"
```

---

## 8 Principles → FL Artifacts

| Perelman Principle | Mathematical analog | FL / OSA artifact |
|---|---|---|
| Ricci flow | deformation to standard form | claim-flow (C0→Cn), causal DAG |
| W-functional (entropy) | monotone control quantity | **claim_entropy** in claim.md |
| No local collapsing | stability under deformation | **no-collapse tests** in controls.md |
| Surgery | controlled component replacement | **surgery log** in decision.md |
| Canonical neighborhoods | local failure model | minimal reproducible example |
| External verification | Kleiner–Lott, Cao–Zhu, Morgan–Tian | external oracle requirement |
| Finite-time extinction | process has an end | promotion gate / freeze rule |
| Singularity analysis | failure = diagnostic point, not bug | singularity catalogue |

---

## claim_entropy (monotone invariant)

Must decrease with each valid step. Count BEFORE running tests.

```
claim_entropy = N_unsupported_HIGH + N_hidden_assumptions
              + N_missing_negative_controls + N_ambiguous_definitions
              + N_unresolved_blockers
```

**Rule:** claim_entropy[t+1] < claim_entropy[t] — else the step doesn't count.

**Artifact:** `## Claim Entropy` table in `experiments/_template/claim.md`

---

## No-Collapse Tests (stability checklist)

Result must survive small, legal changes. If it disappears — artifact, not law.

| Test | What changes |
|---|---|
| Data swap | different dataset, same type |
| Noise injection | σ = 10% noise |
| Scale variation | ×0.1 and ×10 |
| Convention flip | different normalization / baseline |
| Negative control | known-false input |
| Adversarial | targeted hard examples |
| Alternative tool | different tool, same task |

Minimum (Standard): data swap + negative control + 1 other.
Full: all 7.

**Artifact:** `## No-Collapse Tests` table in `experiments/_template/controls.md`

---

## Surgery Log (controlled replacement)

Required for any non-trivial component change.

```markdown
| old_component | failure_mode | evidence | replacement | why_valid | forbidden_claims | new_tests |
```

**Key constraint:** forbidden_claims must be listed — what can NO LONGER be asserted after surgery.

**Artifact:** add to `decision.md` Surgery section when making a non-trivial change.

---

## Singularity Catalogue

Failures are diagnostic points, not bugs to hide.

```markdown
| ID | Where | Local model | Root cause | Status |
|----|-------|-------------|------------|--------|
| S1 | claim C3 | minimal example | definition gap | open |
```

Root cause types: definition / data / model / tool / scale / market

---

## Promotion Rule (5 conditions)

Claim can be promoted ONLY if ALL five are satisfied:

1. ✅ evidence increased
2. ✅ claim_entropy decreased
3. ✅ negative controls passed
4. ✅ no-collapse tests passed
5. ✅ external reconstruction exists

Promotion blocked by: beautiful reasoning alone / previous step success / logical consistency.

**Verdicts:** VALIDATED / PARTIALLY_SUPPORTED / SCAFFOLD_ONLY /
BLOCKED_BY_DEFINITION / BLOCKED_BY_EVIDENCE / BLOCKED_BY_EXTERNAL_INPUT / OVERCLAIM_RISK

---

## Anti-Patterns

| Anti-pattern | Description |
|---|---|
| Genius leap | skip intermediate claims as "obvious" |
| Evidence laundering | same source confirms multiple independent claims |
| Surgery without log | "improved the model" without forbidden_claims |
| Entropy theatre | lots of activity, claim_entropy unchanged |
| Premature promotion | promote before negative controls pass |
| Singularity suppression | call failure "edge case", don't catalogue |
| Fake external oracle | "colleague agreed" is not independent |
| Infinite surgery | endless fix cycles instead of BLOCKED_BY_EXTERNAL_INPUT |
| Overclaim escalation | one test → multi-level claim promotion |

---

## Integration with existing FL/OSA

- **claim_entropy** → tracked in `claim.md § Claim Entropy`
- **no-collapse tests** → in `controls.md § No-Collapse Tests`
- **surgery log** → in `decision.md` when component replaced
- **singularity catalogue** → in `null_results/<id>.md` for serious failures
- **promotion rule** → extends existing OSA-HC promotion gate (Rescue → AOG → Final Status)
- **external reconstruction** → maps to `[VERIFIED-REAL]` in integrity.md

---

## Quick reference prompt (for AI audit agent)

```
Perelman-style audit:
1. Decompose into C0→Cn claim flow
2. Count claim_entropy (must decrease each step)
3. Catalogue singularities — where does it break?
4. Run no-collapse tests: noise, scale, convention, adversarial, negative control
5. Surgery log for any replacement: forbidden_claims required
6. External reconstruction for HIGH-claims
7. Promote only if all 5 conditions satisfied — otherwise FREEZE
```

**Last updated:** 2026-06-20
**Status:** ACTIVE — reference for research/audit tasks
**Source:** КРИЗИС-П synthesis (OSA-HC + Perelman protocol)
