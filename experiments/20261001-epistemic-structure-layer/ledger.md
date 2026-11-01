# ledger.md — 20261001-epistemic-structure-layer (prospective Harness Change Ledger)

Format per `rules/meta-loop.md` § Harness Change Ledger. One file inside the experiment folder rather than PR
bodies, because the program spans several PRs (same deviation, same reason, as
`20260912-cycle2-retrospective-replay/ledger.md`). No gate enforces this file.

**Baseline note (Entry 0).** Neither "a promotion later found false" nor "a dead end re-entered" has ever been
recorded in this repository (`20260912-cycle2-retrospective-replay/ledger.md` Entry 0). These entries therefore
make predictions about **what the new tools surface**, not about outcome reduction.

---

## Entry 1 — `ach_quotient.py` (EQR + EECD)
- **Change:** a read-only script that groups hypotheses with identical full vectors, rejects tests that split no class, reports `d_min`.
- **Prediction:** on the next 5 real hypothesis tables produced by `hypothesis-arbiter` or the variant tournament, at least 1 has a non-trivial class beyond its shuffle floor.
- **Falsified if:** 0 of 5 do.
- **Check after:** the next 5 real hypothesis tables (not a date).

## Entry 2 — `claim_cutsets.py` (ECSA)
- **Change:** a read-only script that computes minimal support / cut sets from a hand-written support logic.
- **Prediction:** on the next 3 `claim-decomposer` outputs that contain an OR structure, computed singleton cuts differ from the declared `BLOCKING_ATOMS` in at least 1.
- **Falsified if:** they agree in all 3, or no output contains an OR structure.
- **Check after:** the next 3 `claim-decomposer` runs on multi-source claims.

## Entry 3 — `verdict_invariance.py` (EMT)
- **Change:** deterministic nuisance transforms + a comparator with per-family verdict vocabularies.
- **Prediction:** the next 3 checkpoints written for a real multi-PR chain show at least 1 answer divergence between the full and the compressed variant (graded against git).
- **Falsified if:** 0 of 3 diverge while the truncated control does diverge.
- **Check after:** the next 3 real checkpoints.

## Entry 4 — FIS-lite (conditional on Entry 2)
- **Change:** a read-only candidate generator for single-assumption mutations from a Kill Analysis.
- **Prediction:** on the next 2 REJECT verdicts with a filled Kill Analysis, at least 1 follow-up that is later actually pursued is among the enumerated candidates and is not among the recorded Relaxation Map rows.
- **Falsified if:** none is.
- **Check after:** the next 2 REJECT verdicts with a filled Kill Analysis.
