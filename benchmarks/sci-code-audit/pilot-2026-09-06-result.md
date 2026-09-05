# sci-code-audit — blind pilot vs free-form baseline, result

**Date:** 2026-09-06
**Object:** does applying `sci-code-audit`'s actual 10-layer protocol find more
real, verifiable code-trust issues than a strong free-form code review, on
real code with independently-sourced, sealed ground truth, without an
unacceptable false-positive rate? Pre-registered in
`pilot-2026-09-06-preregistration.md` before any results existed.

## Why this pilot exists

Prompted directly by a user-supplied critique of this same day's earlier
"6/10 -> ~19 dogfooded" skill-maturity sprint: every one of those 19
promotions showed a skill produced a real finding, none showed a skill
performing BETTER than not using it. This is the first genuine with/without
comparison run against that critique's own proposed protocol (pre-registered
criteria, 6 comparable objects, blind arms, blind adjudication).

## Protocol

Mirrors `benchmarks/construct-measurement-gate/run-2026-08-30-blind-holdout.md`:
1. **Independent Case Curator** (`Agent(general-purpose)`, model=opus, blind
   to `sci-code-audit`'s existence) — built 6 real objects from verified
   GitHub history via WebSearch/WebFetch/`get_commit`: 4 with a real,
   documented bug (fetched pre-fix code at a permanent tag + the real fix
   commit as sealed ground truth), 2 clean objects from mature libraries
   with deliberately-tempting false-positive bait.
2. **Arm A — Baseline** (`Agent(general-purpose)`, model=sonnet) — free-form
   rigorous code review, no template, no knowledge of `sci-code-audit`.
3. **Arm B — Treatment** (`Agent(general-purpose)`, model=sonnet) — given
   `sci-code-audit`'s real `SKILL.md`, applied its actual protocol.
4. **Blind Adjudication** (`Agent(general-purpose)`, model=opus) — given the
   sealed ground truth and both responses labeled "Response 1"/"Response 2"
   with no indication of which was baseline/treatment, scored against the
   4 pre-registered criteria.

## Dataset (6 real, verified objects)

| # | Object | Verdict | Bug type |
|---|---|---|---|
| R1 | astropy `FITS_rec.__setitem__` | BUGGY | missing invariant (negative-slice + length check) |
| R2 | scikit-learn `KFold` | CLEAN (bait: `random_state=None`, CV-splitter) | -- |
| R3 | sktime `Imputer` | BUGGY | control/data provenance (train/test leakage) |
| R4 | pandas C-parser `raise_parser_error` | BUGGY | silent fallback (swallowed exception) |
| R5 | CPython `statistics.covariance/correlation` | CLEAN (bait: `try/except` shape) | -- |
| R6 | AllenNLP `MultiprocessDatasetReader` | BUGGY | reproducibility gap (cross-process reseeding) |

All 4 "buggy" objects trace to a real, verified GitHub commit (repo, hash,
PR number, verbatim commit message) fetched via the GitHub API; pre-fix code
fetched byte-for-byte from `raw.githubusercontent.com` at a permanent tag.

## Result — per-object scoring against sealed ground truth

| Object | Response 1 (baseline) | Response 2 (treatment) |
|---|---|---|
| R1 | Correct verdict; hits defect (a) + the `step` omission; **misses** the missing-length-check defect (b) | Correct verdict; hits **both** (a) and (b); misses the `step` omission |
| R2 | CLEAN, correctly dismisses bait | CLEAN, correctly dismisses bait |
| R3 | BUGGY, but names a *different* real bug (RNG reseeding), not the leakage GT bug | BUGGY, **same different bug** as Response 1, also misses leakage |
| R4 | BUGGY (memory leak) — different bug from GT, and itself unverified from the excerpt | **False negative** — "no confirmed bug," though it flags the right code region under the wrong mechanism (GIL safety, not swallowed exception) |
| R5 | CLEAN, correctly dismisses bait with reasoning | CLEAN, correctly dismisses bait with reasoning |
| R6 | BUGGY, different real bug (no worker-failure handling) | BUGGY, different real bug (no `try/finally`, queue reuse) |

**Strict ground-truth recall: 1 of 4 buggy objects (R1 only) for BOTH arms.**
On R3, R4, and R6, both arms found *a* real, plausible, well-reasoned bug —
just not the one the ground truth documents. R4 is the sharpest case: the
treatment arm (Response 2) cleared a genuinely buggy object.

## The 4 pre-registered criteria

| # | Criterion | Result |
|---|---|---|
| 1 | Treatment finds >=2 real issues baseline misses | **FAILS** (in both directions — neither arm has 2 GT-matching findings the other lacks; the only differentiating GT-matching content is R1's defect (b), which only Response 2 caught) |
| 2 | Specificity >=0.80 on R2/R5 for both | PASSES (1.00 for both — zero HIGH/MEDIUM false positives, both correctly reasoned through the deliberate bait) |
| 3 | No critical false positive | PASSES (neither arm recommended a destructive action on a clean object) |
| 4 | Actionability >=4/6 | PASSES for both (4/4 on the buggy objects each; Response 2's recommendations name slightly more specific regression tests) |

**MCID:** per the pre-registration, criterion 1 failing alone means the
headline claim does not hold, regardless of the other three. **The MCID does
not hold.**

## Final verdict (adjudicator's own words, not softened)

> "Effectively a tie, with no clear winner — and specifically not a win for
> the more structured response... Nothing here supports 'Response X
> performed better' at a magnitude worth acting on, and per the
> pre-registration's own framing a tie is a legitimate outcome."

Response 1 (baseline) had better verdict accuracy (6/6 correct buggy/clean
calls vs. 5/6 — the treatment's R4 miss). Response 2 (treatment) landed its
one hit more completely and showed better calibration hygiene (labeling an
unverified GIL-safety concern as `REQUIRES-CHECK` rather than asserting it,
where Response 1 asserted an unverified memory-leak claim as a confirmed
"real issue"). These two edges roughly cancel.

## Format-blinding check (disclosed limitation, tested for real)

Per the pre-registration's own acknowledged limitation, true format-blinding
was not achievable — the adjudicator correctly inferred which response was
the treatment arm from its structured-template vocabulary. **The inference
did not favor that arm**: the single largest scoring event (R4's false
negative) belongs to the response the adjudicator guessed was the treatment,
which is evidence the adjudicator scored content, not form.

## What this result means, and does not mean

1. **Does NOT mean `sci-code-audit` is useless.** It means: on this specific
   6-object set, applying its protocol did not find more of the *documented*
   bugs than an unstructured strong review did. Both arms found real,
   different, defensible issues on 3 of 4 buggy objects — the dataset itself
   may simply contain multiple plausible defects per object (a property of
   these specific packets, noted by the adjudicator), which weakens "found a
   bug" as a discriminator on this set specifically.
2. **Does NOT generalize beyond n=6, this shape of code** (real open-source
   Python/Cython snippets, 20-150 lines, one bug type per object). A
   different object type (e.g. this repo's own hooks/, which `sci-code-audit`
   was actually built to audit) might show a different result.
3. **Does mean the honest baseline for future `sci-code-audit` maturity
   claims changes.** Before this pilot, zero entries in this project's
   evidence base had a real with/without comparison for this skill. Now
   there is one, and it is a null result on the comparative claim -- worth
   recording precisely because null results are informative, not because
   they are convenient.

## Limitation

n=6 is a first read, not a statistically powered trial (both this pilot's
own pre-registration and this project's own `skeptic-triggers.md` flag this
explicitly). A single skeptic-worthy sweep either direction (6/6) would
itself warrant a re-check before trusting it -- this result is NOT a clean
sweep either direction, which is itself informative: it did not need that
extra scrutiny to be believable.

## Full agent transcripts

The curator's full sourcing work, both arms' complete per-object reviews,
and the adjudicator's complete reasoning exist in this session's own
transcript. This file is the citable, committed artifact per this repo's
established `benchmarks/` convention -- the condensation above preserves the
adjudicator's own verdict language on the headline question rather than
rephrasing it into something more decisive than it was.
