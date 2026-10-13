# Artifact Provenance Gates

Four gates extracted from a single failure mode observed end-to-end on
2026-08-03 (Buckholtz/MULTING bridge audit): **a project spent months trying to
reconstruct one operator behind two artifacts that were never connected the way
their shared subject implied.**

The gates are cheap, they run before analysis rather than after, and each one is
here because its absence cost real work. They sit upstream of everything in
`falsification-ladder.md`: FL asks "does the claim hold?", these ask "is the
thing you are about to analyse what you think it is?"

```
Artifact Identity  ->  Target Provenance  ->  [FL Step -5 Zero-Signal Gate]
       (what is it)        (who made it, from what)
Positive-Control Digitization  ->  before comparing any extracted curve
Conserved-Budget               ->  before any population integral
```

---

## Gate 1 — Artifact Identity

**The incident.** For weeks a project analysed an object it called "Figure 3 of
the preprint". `grep -c -i "figure"` on the preprint returned **0** — the paper
has no figures at all. The object was an unpublished email attachment. Three
analysis scripts recorded the real path in their source while every surrounding
document said "the published figure".

**The rule.** A conversational name is not an identifier. Before any analysis,
every artifact gets a record:

```yaml
artifact_id:          ARTIFACT_<CHANNEL>_<DATE>_<SLUG>    # never "Figure 3"
source:               file path / URL / message thread
date_created:         from the file's own metadata, not from when you got it
date_received:        when it entered your possession
version:              and what the predecessor was
publication_status:   published | preprint | unpublished | private correspondence
hash:                 so a later copy can be shown to be the same object
relates_to:           other artifact_ids, and HOW (renders / supersedes / cites)
```

**Hard rule:** a verdict established for artifact A never transfers to artifact B
because they share a subject, an author, or a name. Write the non-transfer down
explicitly in each certificate; the transfer happens silently otherwise.

**Cheapest possible check, run it first:** grep the claimed source for the thing
you say is in it. Zero hits is a finding, not a grep problem.

---

## Gate 2 — Target Provenance

**The incident.** A reconstruction programme took a published table as its target
and asked "what operator produces these numbers?" The table's own caption said:
*"Responses, to our prompt, by one online service that has bases in artificial
intelligence."* Three services had been asked; each **fitted** two coefficients to
the observed data it was meant to predict, and normalised the curve to the
observed value at the origin. The target was a fit wearing the costume of a
prediction.

**The rule.** Before reconstructing, reproducing, or validating against any
result, establish:

| field | why it decides everything |
|---|---|
| who produced it | human, instrument, simulation, or a language model |
| what data the producer could see | if it saw the test data, it is not a prediction |
| what the inputs were | free parameters vs fixed ones |
| was anything optimised | fitted / anchored / normalised — and to what |
| what kind of claim is it | **prediction** \| **fit** \| **illustration** |

**Hard rule:** a fit may never be used as the validation target for the thing it
was fitted to. Reproducing it reproduces the fitting procedure, not the theory.
When the classification is `illustration`, say so in every downstream document —
an illustration that gets quoted three times becomes a result.

**The tell that costs nothing to check:** does the artifact agree with the
observations *too well* at the anchor point? Exact agreement with zero quoted
uncertainty at `x = 0` is normalisation, not success.

---

## Gate 3 — Positive-Control Digitization

**The incident.** A first crude extraction of a curve from a PDF gave a 9.8 %
mismatch against a candidate source. Unusable — no way to tell a real difference
from an extraction artifact. The repository's proper digitiser selected curves by
**colour** instead, and the same figure carried a second curve of *known*
identity. Fitting that known curve recovered its parameters to **0.002 %**. Only
then did the 21 % mismatch on the unknown curve become a result.

**The rule.** Before comparing an extracted curve to anything, the extractor must
reproduce a curve on the **same figure** whose identity is independently known,
and the residual of that reproduction is quoted alongside every subsequent number.

```
blue curve (labelled LCDM, Planck)  -> flat LCDM fit -> rms 0.0019 %   <- the control
orange curve (the unknown)          -> flat LCDM fit -> rms 3.9920 %   <- the result
```

**Hard rule:** an extracted-curve comparison without a stated control residual is
not evidence. If the figure carries no known curve, say the extraction is
uncalibrated and bound the conclusion accordingly.

**The second half of this gate, and the one people skip:** run the *same test* on
the control. A cubic spline fitted the unknown curve to 0.046 % — apparent proof
of graphical construction, until the same spline fitted the known ΛCDM curve to
0.003 %. The test discriminated nothing and had to be withdrawn. **A test that
cannot distinguish your control from your target is not a test.**

The same discipline applies outside digitisation. Its analogue in mass
spectrometry is the *lock mass*: a known peak in every spectrum, calibrating the
scale in place rather than beforehand.

---

## Gate 4 — Conserved-Budget

**The incident.** A population integral used number density `1e-4 Mpc^-3` with
mass `1e15 M_sun`, described in the code and in the write-up as *"deliberately
generous, so the result is a ceiling."* It was not a ceiling. Expressed as a
fraction of the matter density it was **2.52 — 252 % of all the matter in the
universe.** Because the result went as the square of that density, the single
unchecked assumption accounted for 2.79 of a 3.11-decade discrepancy with an
independent implementation.

**The rule.** Before any integral over a population, express the population's
total against the conserved quantity that bounds it, and print the ratio:

```
n * <M>  /  rho_available   <= 1        must be printed, not assumed
```

Generalises directly: energy budgets, baryon budgets, photon budgets, time
budgets, token budgets, headcount. Anything with a conservation law has one.

**Hard rule:** the words "generous", "conservative", "an upper bound" and
"a ceiling" are claims about a conservation law and require the ratio to be
shown. An adjective is not a bound.

**Generalization — Scientism Detection (added 2026-09-06, source: external
research-report comparison, `rationalizations.md` § 5 has the paired
rationalizations-table entry):** the same failure wears a second costume —
not a hidden ratio, but a hidden CALCULATION, laundered behind an appeal to
general authority instead of a computed number for this specific case.
"It's well-established that X" / "best practice says Y" / "как известно" /
"общепринято" are, structurally, the same move as "generous" or
"conservative": a word standing in for a number that was never shown. The
tell is the same too — does the sentence carry a number/ratio for THIS
case, or only a category ("science", "best practice") that could describe
any case? If the latter, the hard rule applies exactly as written above:
show the specific computation, or the claim doesn't count as checked.

**Why this belongs with the other three:** it is the same failure in a different
costume. Gates 1–3 catch "I did not check what this object is." Gate 4 catches
"I did not check what this number is against." Both are unexamined premises
sitting upstream of a long, careful, worthless calculation.

---

## Cost

All four gates together, on the audit that produced them: under an hour of
compute. They overturned two load-bearing premises, withdrew four published
numbers, and converted an open-ended question to the author into a
one-line yes/no about the existence of a single file.

---

## Quick reference

```
About to analyse an artifact?      -> Gate 1: does it have an ID, or just a nickname?
                                      grep the claimed source for it FIRST
About to reconstruct a result?     -> Gate 2: prediction, fit, or illustration?
                                      did the producer see the test data?
About to compare extracted data?   -> Gate 3: what is the control residual?
                                      does the same test pass on the control too?
About to integrate a population?   -> Gate 4: print n<M>/rho_available before the integral
Calling an assumption "generous"?  -> Gate 4: then show the ratio
Saying "well-established" / "best practice" / "как известно"?
                                    -> Gate 4 (Scientism Detection): same move as "generous" --
                                      show the computed number for THIS case, not the category
Verdict established for A?         -> Gate 1: it does not transfer to B. Write that down.
```

**Last updated:** 2026-09-06 (Scientism Detection generalization added to Gate 4)
**Status:** ACTIVE
**Source:** Buckholtz/MULTING bridge audit, certificates C1–C5C; Scientism Detection generalization from external research-report comparison (Claude-cod-top-2026, 2026-09-06)
