# ECSA extraction rules (committed BEFORE `claim_cutsets.py` is run on any real subject)

Authored 2026-10-01. The prose of each subject was read to find its atoms; no cut set, kappa or singleton
list has been computed for any real subject yet. P3 (see `claim.md`) compares what the tool computes against
what the source ALREADY declares as blocking; the declared set is fixed here, before the computation.

## Translation rule (prose -> logic)

1. Atoms are exactly the atoms the source names (`C1..C7`, `T1..T5`). No atom is added or merged.
2. **AND is the default** between atoms. A pair is OR-ed ONLY if the source text states an explicit
   alternative ("either", "or", "any one of", "at least one"), quoted in the table below.
3. Dependency edges ("Ci -> Cj" = Cj relies on Ci) add the upstream atom to the AND of the downstream one.
4. `BLOCKING_ATOMS` is copied from the source only where the source declares blocking atoms. E1's source declares
   a blocking CONTRADICTION (C5 x C6), so BLOCKING_ATOMS = {C5, C6}; C3 and C7 are NOT added (that would be me
   inventing a declaration). The tool's default logic then ANDs those with their transitive dependencies.
5. A contradiction between two atoms is NOT encoded as logic (it is a verdict about the atoms, not a
   support structure); it is recorded separately and compared with the tool output.

## Subjects (independent units: 2 claims; they are different claims in different experiments)

| Subject | Source | Atoms | Explicit OR quoted? | Source-declared blocking set (fixed now) |
|---|---|---|---|---|
| E1 `two_source_gate` | `benchmarks/claim-decomposer/run-2026-09-05-two-source-gate-claim.md` | C1..C7 | none found (grep for either/or/alternative: no hit) | the contradiction pair C5 x C6 (blocking, source verdict KILL) |
| E2 `evidence_chain_verifier` | `experiments/20260906-evidence-chain-verifier/claim.md` | T1..T5 (the 5 pre-registered tests) | none | T4 alone (MCID: "if test #4 alone passes when it should reject, the mechanism is worthless") |

## What P3 asks of these subjects

P3 = "do computed singleton cuts differ from the declared blocking set". With AND-only logic every atom is a
singleton cut by construction, so P3 can only be informative if the source distinguishes critical atoms from the
rest; E1 and E2 both do (C5xC6, T4). If the tool returns "all atoms singleton" on both, it adds nothing the
source did not already say, and the pre-registered park criterion for ECSA (no claim with OR structure)
applies. Count of claims with explicit OR structure: reported as found (expected 0 of 2).

## Out of scope

Claims from Y-17 and `20260912-research-evidence-loop-minimal-extension` are not extracted: the second has no
atom list, only narrative; extracting atoms from it would be the analyst inventing the structure.
