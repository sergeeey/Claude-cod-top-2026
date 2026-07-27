# Variant Tournament

> Never one solution. Always a field. The best candidate in a field of one is just
> the only candidate.

## The problem this solves

Single-solution selection is the failure mode where you generate one idea, test
it, and promote or reject it. When it passes, you have weak signal (it was the
only competitor). When it fails, you have almost no information about *what* to
try next. Tournament selection solves both by forcing **genuine diversity** before
any evaluation — so the winner earned its rank rather than inherited it by default.

This is component 4 of the Oracle-Aware Core.

```
Oracle-Aware Core (7 components)
  1. Intent              templates/intent_card.yaml
  2. Oracle Adequacy     docs/oracle-adequacy-gate.md
  3. Falsification       templates/falsification_contract.yaml
  4. Variant Tournament  <-- THIS DOCUMENT
  5. Red-Team            skeptic / codex-skeptic
  6. Evidence Gate       rules/integrity.md + hooks/promotion_gate_guard.py
  7. Null Result Ledger  null_results/ + hooks/reject_gate_guard.py
```

## Where it sits

Runs **after** the oracle has been audited (Stage 2, verdict ADEQUATE or WEAK)
and each finalist has a signed falsification contract (Stage 3). Runs **before**
the red-team (Stage 5), which receives only the winner — not the full field.

An INADEQUATE oracle verdict from Stage 2 blocks the tournament entirely: ranking
variants against a bad judge manufactures a confident false winner.

## Protocol

### Step 1 — Generate a diverse field (minimum 3 variants)

Diversity means **different mechanisms**, not different phrasings of the same idea.
A variant is genuinely different if it would fail under different conditions from
the others — if the same edge case breaks two variants, they are not diverse enough.

```
Required diversity axes (use at least 2):
  mechanism   — different underlying approach (rule vs. model vs. lookup)
  domain      — borrowed from a different field (/cross-domain)
  scale       — operates at a different level of abstraction (token vs. sentence vs. doc)
  direction   — addresses the problem from the opposite angle
  constraint  — holds a different constraint constant (speed vs. quality vs. cost)
```

**Minimum field size: 3.** More is fine; the marginal cost is one
`falsification_contract.yaml` per variant. Stop adding when new variants repeat
mechanism territory already covered.

**Variant naming convention:** `V1-<slug>`, `V2-<slug>`, `V3-<slug>` — slug is the
mechanism, not a quality claim. `V1-cached-retrieval`, not `V1-better-approach`.

### Step 2 — Fill a falsification contract for every finalist

Before any variant is scored, its `templates/falsification_contract.yaml` must be
filled with:
- Pre-committed kill conditions (at least 2)
- Negative control (known-bad input that MUST fail)
- Positive control (known-good input that MUST pass)

Deciding kill conditions after seeing results is rationalization (Anti-Overfitting
Gate, `rules/falsification-ladder.md`). Pre-commit or the tournament is theater.

### Step 3 — Score each variant against the audited oracle

Use exactly the `success_metric` from `templates/intent_card.yaml`. No proxy
metrics during the tournament — proxy scoring re-introduces the Goodhart problem
that Stage 2 was designed to prevent.

Record the full scoring table:

| Variant | Mechanism | Score (metric) | Positive control | Negative control | Notes |
|---------|-----------|----------------|-----------------|-----------------|-------|
| V1-...  |           |                | pass / fail     | pass / fail     |       |
| V2-...  |           |                | pass / fail     | pass / fail     |       |
| V3-...  |           |                | pass / fail     | pass / fail     |       |

A variant is **eliminated** if:
- Any falsification condition fires, OR
- Its positive control fails (test harness is broken), OR
- Its negative control passes (oracle is broken — return to Stage 2)

### Step 4 — Rank survivors and break ties

Primary rank: score on the single `intent_card` success_metric (higher/lower per
`direction`).

Tie-breaking (in order):
1. **Simplicity** — fewer moving parts, fewer dependencies, fewer LOC.
2. **Reversibility** — can the change be rolled back in ≤30 min?
3. **Scope fit** — stays within `intent_card.scope.in_scope`.

**Do not optimize novelty** — a boring variant that scores better is a better
variant. Novelty without the intent metric is noise.

### Step 5 — Select the finalist

The finalist is the top-ranked variant that passed both controls. It advances to
Stage 5 (Red-Team) with its `falsification_contract.yaml`.

**All eliminated variants** are routed to Stage 7 (Null Result Ledger) with a
Kill Analysis — not deleted, not ignored.

## Anti-patterns

| Anti-pattern | Why it corrupts the tournament |
|---|---|
| **3 phrasings of one idea** | Same mechanism = same failure modes = fake diversity. Generate from different constraint axes. |
| **Premature elimination** | Eliminating a variant before controls run loses information about which oracle assumption failed. Run controls first. |
| **Mid-tournament oracle drift** | Switching the metric between V1 and V2 scoring makes ranks incomparable. Lock `success_metric` before Step 3. |
| **Adding variants after scoring** | Adding a variant that "looks better" after seeing the others' scores = motivated selection. Lock the field at Step 1. |
| **Complexity as a tie-breaker primary** | Complexity should break ties, not primary-rank. A variant that is complex but clearly better still wins. |
| **Skipping controls for "obvious" variants** | Controls catch oracle breakage, not variant weakness. "Obvious" variants have the same risk of oracle corruption. |

## Relationship to existing skills

| Need | Use |
|---|---|
| Generate variants from other domains | `/cross-domain` (Feasibility Gate ≥ 7 → go) |
| Structured selection between competing explanations | `/hypothesis-arbiter` |
| Combinatorial variant generation | `/combinatorial-creativity` |
| Tie-breaking by skeptic | `/skeptic` (full context, this is design not artifact review) |
| Red-team the winner (Stage 5) | `/skeptic` with context asymmetry (claim + code only) |

## Worked example (skeleton)

```
Intent:   cut RAG hallucination rate on our support corpus (baseline 0.18)
Oracle:   automated check on 200 real production tickets (ADEQUATE verdict)

Field:
  V1-reranker     — add cross-encoder reranker on top of retrieval (mechanism: model)
  V2-citation-pin — force citations to verbatim spans (mechanism: constraint)
  V3-cot-prompt   — chain-of-thought before answering (mechanism: direction)

Scoring table:
  V1-reranker     0.11  positive: pass  negative: pass  → SURVIVOR
  V2-citation-pin 0.09  positive: pass  negative: pass  → SURVIVOR
  V3-cot-prompt   0.16  positive: pass  negative: fail  → ELIMINATED (negative control passed — oracle check failure, return to Stage 2)

Tie-break (V1 vs V2):
  V1 score 0.11 > V2 score 0.09 → V1-reranker advances to Stage 5.

Null results:
  V2-citation-pin → null_results/20260630-v2-citation-pin.md (killed by score, mechanism survives as component idea)
  V3-cot-prompt   → null_results/20260630-v3-cot-prompt.md   (killed by oracle break, triggered Stage 2 re-audit)
```

---

**Status:** ACTIVE — component 4 of the Oracle-Aware Evolutionary Mode.
**Command:** `/evolve-solution` runs this protocol at Stage 4.
**Templates:** `templates/falsification_contract.yaml` (one per finalist variant).
**Feeds into:** `docs/oracle-adequacy-gate.md` if a negative control passes (oracle break),
otherwise Stage 5 (`/skeptic` context-blind, winner only).
