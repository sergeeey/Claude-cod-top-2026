# claim.md — 20261001-epistemic-structure-layer

_Full ladder. Plan of record: `C:\Users\serge\.claude\plans\hazy-pondering-hinton.md` (v2, after an independent
critique whose factual claims were re-verified against `origin/main`). Everything below was written BEFORE any
tool in this experiment was run on real data._

## Zero-Signal Gate

| Field | Value |
|-------|-------|
| **Entity** | Three new read-only scripts — `scripts/verdict_invariance.py`, `scripts/ach_quotient.py`, `scripts/claim_cutsets.py` — plus the text edits they would justify in existing skills/rules |
| **Falsifiable predicate** | Each script's *derived view* of an artifact that is really filled in (hypothesis tables, `claim-decomposer` output, skeptic-pilot inputs, tracked checkpoints) shows structure that a human reading of the same artifact did not state: a non-trivial equivalence class beyond chance, a computed singleton cut that the skill's own `BLOCKING_ATOMS` did not declare, a verdict or checkpoint-answer divergence beyond run-to-run noise |
| **Measurable outcome** | The six counters P1–P6 below, each with a stated parking criterion, produced by the scripts into `metrics/run.json` (never retyped by hand) |

> Gate rule satisfied: all three fields filled from the input alone. Issuing a PARK verdict for a module is a
> valid and expected outcome; the prior experiment in this lineage (`20260912-cycle2-retrospective-replay`)
> returned `NO_HEADROOM` for exactly the reason this experiment is shaped to avoid.

---

## L0: Question Type

- [x] Descriptive — "does a derived view show structure in artifacts that are actually filled in?"
- [ ] Predictive
- [ ] Causal

**Reasoning.** The causal question ("did verdicts get better after adopting these tools?") was ruled
non-identifiable retrospectively in Cycle 2 (`20260912-cycle2-retrospective-replay/decision.md`); the
retrospective data needed to identify it do not exist (0 recorded false promotions, 0 recorded repeated dead
ends). This experiment therefore asks only the descriptive question and records prospective ledger entries
(`ledger.md`) for the causal one.

---

## Natural Language Statement

> "We count, for each of three derived-view tools, on the independent real artifacts available (≈2–3 per
> module), how often the tool's output states something the artifact's own author or skill did not — measured
> against a chance/noise floor computed on the same shape of data — handling missing cells (`N/A`) as a
> separate symbol rather than as agreement."

## What this result does NOT mean (required, written before results)

1. It does **not** show that verdict quality improved — no outcome variable is measured; the causal question is
   explicitly out of scope.
2. It does **not** generalise beyond ≈2–3 independent subjects per module. Variants of one object (remy-tumorigenesis
   `h4…h31`, lakes-tda `v1…`) are **one** independent unit, not many (lesson of 2026-09-24).
3. A synthetic-fixture pass (`[VERIFIED-SYNTHETIC]`) shows the *code* is correct, not that the tool is *useful*.
4. Parking a module is not a verdict that the underlying idea (EC², minimal cut sets, metamorphic testing) is wrong —
   only that on this corpus it showed no headroom.

---

## Claim Entropy
_Counted before running anything._

| Component | Count |
|---|---|
| Unsupported HIGH claims | 0 |
| Hidden assumptions | 3 |
| Missing negative controls | 0 |
| Ambiguous definitions | 1 |
| Unresolved blockers | 0 |
| **Total claim_entropy** | 4 |

_Notes on the counts._ Unsupported HIGH claims = 0: no claim of usefulness is made, only counters. Hidden
assumptions = 3: (i) hand-extracted prediction matrices are faithful to the source prose; (ii) `N/A` is not
agreement; (iii) the Y-17 subjects, read read-only, are representative enough to be informative. Missing negative
controls = 0: each module has a control in `ceiling.md`. Ambiguous definitions = 1: "non-trivial class beyond
chance" is defined operationally in P1.

---

## Counterfactual Frame

| Question | Answer |
|---|---|
| What must change for the claim to be true? | The real artifacts must contain redundancy / hidden single points of failure / process sensitivity that current mechanisms do not name |
| How many independent changes required? | 0 — it is a measurement of what is already there |
| Known system where these conditions already hold? | Two in-repo precedents: the 2026-08-24 skeptic paraphrase pilots (WEAKENED vs FALSIFIED on identical input) show process sensitivity exists; `claim-decomposer`'s own `BLOCKING_ATOMS` is a declared, uncomputed cut set |

**Verdict:** `within-framework`

---

## Preregistered measures P1–P6 (descriptive; parking criterion on the right)

| # | What is counted | Parking criterion for the module |
|---|---|---|
| **P1** | Number of independent hypothesis sets with ≥1 non-singleton class (classes = identical **full** vectors, `N/A` its own symbol, coverage ≥ 0.50), **compared with a row-wise-shuffle null of the same shape** (`ach_quotient.py floor`, seeded) | no set exceeds its null → park EQR as a utility; make no skill/rule edit |
| **P2** | Distribution of `d_min` between classes (reported only) | not a criterion (on small matrices `d_min = 1` is near-certain) |
| **P3** | On `claim-decomposer` outputs that have a hand-written OR structure: do **computed singleton cuts** differ from the skill's own **declared `BLOCKING_ATOMS`**; the number of such claims is reported (`< 3` ⇒ labelled anecdotal) | agree everywhere, or no claim has an OR structure → ECSA stays a utility; no skill/template edit |
| **P4** | Checkpoint Fidelity: divergence of answers between non-trivial variants **beyond the divergence among no-variation repeats**; the truncated variant is the **instrument's positive control** (it must abstain or diverge), not part of the test | truncated variant did not diverge → instrument invalid, results not interpreted |
| **P5** | Narrative Poison: raw verdicts only (anecdotal, 2 inputs); framing difference vs the spread of 3 "no history" repeats | with `n < 3` no inference is drawn; raw verdicts are published |
| **P6** | FIS-lite retrodiction: share of actually-pursued follow-ups covered by mechanically enumerated single-assumption mutations, **against the chance baseline covered ÷ enumerated**; evaluator knows the outcomes (flagged) | not above chance → park FIS-lite |

Dropped as predictions (and why): the former P7 — for exact-duplicate likelihood rows EIG does not change
mathematically (only the prior *mass* does, under a uniform-per-hypothesis convention), so it is a **unit test**
plus a warning in `eig_calculator.py`; the former P8 — `n = 1` with the author as judge.

## Extraction rules (to be committed BEFORE any class / cut set is computed on a real subject)

_Filled in a separate commit, one file per subject, under `rules/` in this folder. Until a subject's rule file is
committed, that subject's tool output must not be looked at. This is the guard against motivated extraction._

## Falsifiable Claim

**Claim:** On the independent real subjects available, at least one of the three tools produces an output that
exceeds its chance/noise floor on a pre-declared counter (P1, P3, P4); a module whose counter does not is parked.

**Check (command or observation):** `metrics/run.json` produced by the scripts; per-module verdict recorded in
`decision.md`; raw inputs and verdicts archived under `benchmarks/epistemic-layer/`.
