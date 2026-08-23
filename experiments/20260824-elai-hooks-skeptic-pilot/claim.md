# claim.md — 20260824-elai-hooks-skeptic-pilot

**Pilot purpose:** this experiment is the Phase-1 pilot from the Falsification Audit
(2026-08-24, see conversation) — it tests two of the audit's Tier1 recommendations
(JudgeSense-style paraphrase-sensitivity probe on Skeptic Step 8a; AbstentionBench-style
abstention tracking) against a real, just-merged piece of this repo (PR #260,
`hooks/independence_scorer.py` + `hooks/mutation_tracker.py`), not a synthetic example.

**Explicitly out of scope for this pilot (infeasible right now, not faked):**
- DeepConf-style internal-confidence filtering — requires token-level logprob access this
  harness does not expose through the Agent tool. Not implemented; flagged, not simulated.
- GraphRAG for a narrow retrieval use-case — requires standing up graph-construction infra;
  too large a lift for a single pilot turn. Not implemented; flagged, not simulated.

## Zero-Signal Gate

| Field | Value |
|-------|-------|
| **Entity** | `hooks/independence_scorer.py` (`compute_independence`, `tier`) and `hooks/mutation_tracker.py` (`compute_mdr`) — merged to main in PR #260 |
| **Falsifiable predicate** | Both functions correctly implement their own documented algorithm (weighted-dimension independence score with Jaccard-similarity `libraries` dimension, tiers HIGH≥0.70 / MEDIUM≥0.40 / LOW<0.40; MDR = actually_detected / scored, tiers PASS≥0.80 / WARN 0.50–0.79 / FAIL<0.50) with no boundary-condition, off-by-one, or silent-skip defect beyond what the existing 52 tests already cover |
| **Measurable outcome** | Skeptic Step 8a verdict: `[CONFIRMED-REAL]` / `[WEAKENED]` / `[FALSIFIED]` — FALSIFIED requires a concrete counter-example (specific input → wrong score/tier) |

Gate passes: entity, predicate, and outcome are all concretely fillable. Proceeding.

## L0: Question Type

- [x] **Descriptive** — "does this already-implemented computation match its own documented spec?"
- [ ] Predictive
- [ ] Causal

Not causal: no intervention is being compared against a counterfactual: this is a
correctness audit of existing code, not an effect estimate.

## Falsifiable Claim

**Claim:** `compute_independence()` and `compute_mdr()` (hooks/independence_scorer.py,
hooks/mutation_tracker.py, both merged in PR #260) have no bug that produces a wrong
score or wrong tier for any input consistent with their documented contract.

**Check:** Skeptic reviews the two functions + their test files
(`tests/test_independence_scorer.py`, `tests/test_mutation_tracker.py`) and tries to
construct a concrete falsifying input. `pytest tests/test_independence_scorer.py
tests/test_mutation_tracker.py -q` is the positive-control check (52/52 passing as of
merge).

## Instrumentation under test (Phase-1 pilot)

1. **JudgeSense-style paraphrase probe:** the same claim + same code is sent to two
   independent Skeptic invocations with the falsification prompt reworded (different
   register/sentence structure, identical semantic content — see Variant A / Variant B
   below). If the verdict flips between variants, that is itself a finding to log per
   the audit's §7 recommendation, not silently ignored.
2. **AbstentionBench-style abstention tracking:** record whether either invocation
   abstains (`[NEEDS-REAL-DATA]`) rather than committing to CONFIRMED-REAL/FALSIFIED —
   an abstention on a claim this concrete and checkable would itself be notable.

## What This Does NOT Mean

1. Does NOT establish that Skeptic Step 8a is well-calibrated in general — n=2 invocations
   on one claim is a pilot, not a calibration study (Phase 2 of the roadmap requires ≥10
   ledger entries before any precision claim is valid).
2. Does NOT test DeepConf or GraphRAG — both explicitly out of scope this pilot (see above).
3. Does NOT apply to hooks outside this PR — no claim is made about the other 94 hooks.
