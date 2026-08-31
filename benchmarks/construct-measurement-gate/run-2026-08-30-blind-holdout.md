# construct-measurement-gate — blind holdout benchmark

**Date:** 2026-08-30
**Object:** does `construct-measurement-gate` v0.1 (evaluator role, with its own
final Verdict step) add diagnostic value over a strong free-form baseline,
without an unacceptable false-alarm rate — measured on real, independently
curated cases?

## Why this run exists

A first benchmark attempt (same day, not filed as a separate artifact) used 4
self-picked textbook cases (BMI, common-method variance, PHQ-9 DIF, a clean BP
control) with a self-simulated baseline. An independent context-asymmetric
`Agent(skeptic)` review scored that attempt **WEAKENED, bordering FALSIFIED**
for the claim "this benchmark justifies expansion" — not for the gate itself.
Reasons: baseline was imagined, not run independently; all 4 cases were
textbook examples the gate's own steps were conceptually modeled after
(circular validation); every degree of freedom (case selection, baseline
simulation, scoring) sat with one party; a clean 4/4 sweep with zero false
alarms violates this repo's own `skeptic-triggers.md` ("zero failures = test
too weak"). The skeptic's kill criteria for a valid benchmark: ≥8 cases, ≥3 not
textbook examples, ≥2 additional clean controls with subtle false-trigger
traps, an independent party picks the cases, a separate agent runs baseline
blind to which arm it's in. This run was built to satisfy those criteria.

## Protocol

Adapted from the user's own "Construct-Measurement Gate — Blind Validation
Protocol v0.1": independent case curator (blind to the gate) → two independent
arms (baseline, treatment) → blind adjudication against sealed ground truth →
mechanical Pass/Kill criteria.

1. **Independent Case Curator** (`Agent(general-purpose)`, model=opus, given
   zero information about `construct-measurement-gate`'s existence or design —
   told only to build a dataset for evaluating "the quality of methodological
   research audits in general," with WebSearch access and a hard requirement
   to ground every case in real, verifiable sources).
2. **Arm A — Strong Baseline** (`Agent(general-purpose)`, model=sonnet): given
   the 10 case packets verbatim, asked for a rigorous expert methodological
   audit, free-form, no fixed template, explicitly told this must be a STRONG
   audit, not a naive one.
3. **Arm B — Treatment** (`Agent(general-purpose)`, model=sonnet): given the
   same 10 case packets verbatim, plus the actual `construct-measurement-gate`
   v0.1 methodology text (5 steps ending in a Verdict), asked to apply it
   exactly.
4. **Blind Adjudication** (`Agent(general-purpose)`, model=opus): given the
   sealed ground truth plus both arms' full responses, labeled "Response 1" /
   "Response 2" with no indication of which was baseline/treatment, asked to
   score per-case and compute aggregate metrics.

**Acknowledged limitation:** true format-blinding is not achievable in this
setup — Arm B's structured 5-step output (Construct Contract, H_REAL/H_MEASURE
headers) is visually distinguishable from Arm A's free-form prose, so the
adjudicator could very plausibly infer which response came from a templated
method. Content-blinding (not being told which is baseline/treatment, and
being told not to score on format) is real; format-blinding is not. Stated
here rather than glossed over.

## Dataset (curator output, composition audit)

| # | Case | Category | Domain | Textbook example? |
|---|---|---|---|---|
| 1 | Google Flu Trends | CONFIRMED-FAILURE | Big-data epidemiology | Well-known |
| 2 | Pulse oximetry racial bias | CONFIRMED-FAILURE | Clinical instrumentation | Well-known |
| 3 | Google Books n-grams / culturomics | CONFIRMED-FAILURE | Digital humanities | Not textbook |
| 4 | Doubly labeled water / lifespan TDEE | CLEAN | Metabolic physiology | Not textbook |
| 5 | RECOVERY trial dexamethasone | CLEAN | Clinical trials | Not textbook |
| 6 | GPS match distance by position | CLEAN (trap: high-speed-metric invalidity misapplied to total distance) | Sports science | Not textbook |
| 7 | Urban heat island / land warming trend | DECEPTIVE-CONTROL | Climate science | Known dispute, not a measurement-validity textbook case |
| 8 | "3 billion birds" decline | DECEPTIVE-CONTROL | Ecology | Not textbook |
| 9 | Teacher value-added (Chetty/Rothstein) | AMBIGUOUS | Education / labour economics | Known dispute |
| 10 | Implicit Association Test | AMBIGUOUS | Psychology | Known dispute |

Composition target (3/3/2/2, ≥4 non-textbook) met: 6/10 non-textbook. None of
the three cases used in the first (rejected) benchmark attempt (BMI, CMV, PHQ-9
DIF) were reused, to avoid contaminating independence.

## Ground truth (condensed; full sourcing in the curator agent's transcript)

- **Case 1 (CONFIRMED-FAILURE):** Lazer, Kennedy, King, Vespignani (2014),
  *Science* 343 — the 45 retained query terms were selected by pure
  correlation with a seasonal CDC series from 50M candidates ("part flu
  detector, part winter detector" — a construct-validity failure from the
  selection procedure itself), plus the platform's own product changes and
  media-driven searching independently altered query volume ("algorithm
  dynamics"). GFT overshot CDC by >2x in 2012–13 and missed the 2009 pandemic.
- **Case 2 (CONFIRMED-FAILURE):** Sjoding et al. (2020), *NEJM* — pulse
  oximetry's calibration curve, fit on mostly light-skinned healthy-volunteer
  panels, is not population-invariant; melanin biases the absorbance ratio,
  producing directionally dangerous upward-biased SpO2 in darker-skinned
  patients. Occult hypoxemia found in 11.7%/3.6% and 17.0%/6.2% (Black/White),
  replicated across two independently-designed cohorts.
- **Case 3 (CONFIRMED-FAILURE):** Pechenick, Danforth, Dodds (2015), *PLOS
  ONE* — one-copy-per-book disconnects frequency from readership by
  construction; corpus genre composition drifts across the very time axis
  studied (increasingly technical/scientific through the 1900s); published
  trend claims do not survive recomputation across corpus versions/sub-corpora.
- **Case 4 (CLEAN):** Pontzer et al. (2021), *Science*; Speakman et al.
  (2021) — DLW is the accepted criterion method, measures a direct physical
  consequence of metabolism; the pooling group recomputed every measurement
  under one standardized methodology rather than trusting each lab's own
  number, removing the main plausible measurement-heterogeneity confound. Real
  limitations (convenience sample, food-quotient scale uncertainty, 1–2 week
  averaging) are generalizability/precision issues, not measurement-validity
  failures.
- **Case 5 (CLEAN):** RECOVERY Collaborative Group (2021), *NEJM* —
  all-cause 28-day mortality via national registry linkage is objective, no
  assessor discretion; open-label design threatens subjective outcomes, not
  this hard endpoint. Differential co-intervention is a real causal-pathway
  concern, distinct from measurement-validity.
- **Case 6 (CLEAN, deceptive trap embedded):** total-distance GPS metrics
  have the lowest error of all GPS-derived metrics (CV≈3.6%), reliability
  improves with accumulated distance; the well-documented GPS invalidity for
  high-speed/acceleration/change-of-direction metrics does not apply to total
  distance specifically — importing it anyway is the trap.
- **Case 7 (DECEPTIVE-CONTROL):** Wickham et al. (2013, Berkeley Earth) —
  urban-heating influence on the global land trend, computed from
  MODIS-classified very-rural sites only, is indistinguishable from zero;
  Fall et al. (2011) — poorly-sited stations bias min/max trends in opposite,
  canceling directions, so mean trends were nearly identical across
  site-quality classes; Hausfather et al. (2013) — the real urbanization
  signal in unadjusted minima is removed by USHCN v2 homogenization. Concluding
  the warming trend is substantially a siting/UHI artifact is the trap this
  case is built to catch.
- **Case 8 (DECEPTIVE-CONTROL):** Rosenberg et al. (2019), *Science* — a
  methodologically independent, zero-human-observer instrument (143 NEXRAD
  radars measuring nocturnal migratory biomass, 2007–2017) shows a
  directionally and magnitude-consistent decline (13.6%±9.1%), which two
  instruments with orthogonal failure modes agreeing is strong evidence
  against the "citizen-science observer-effort artifact" hypothesis. The
  legitimate, non-trap criticism is narrower: the absolute "2.9 billion" figure
  (not the ~29% relative decline) carries real extrapolation uncertainty.
- **Case 9 (AMBIGUOUS):** Chetty, Friedman, Rockoff (2014, *AER*) vs.
  Rothstein (2017, *AER* comment) — a live, still-published exchange over
  whether teacher-turnover quasi-experiments' key identifying assumption
  (turnover uncorrelated with contemporaneous cohort-preparedness shifts)
  holds. Broad agreement value-added is neither pure noise nor bias-free;
  disagreement is over magnitude.
- **Case 10 (AMBIGUOUS):** declining pooled IAT-criterion correlations across
  more rigorous meta-analyses (r≈0.27 → 0.15 → 0.10); near-consensus that
  individual-level diagnostic use is unsupported; genuinely open whether a
  real aggregate/group-level association exists (Kurdi et al. 2019's
  incremental-validity finding is real but self-flagged as tentative, ~20% of
  included IATs).

## Result

**Sensitivity** (3 confirmed-failure cases): Baseline 3/3, Treatment 3/3.
**Specificity** (3 clean cases): Baseline 3/3, Treatment 3/3.
**Deceptive-control resistance** (2 cases): Baseline 2/2, Treatment 1.5/2 —
Treatment correctly avoided declaring a false failure on both, but on Case 7
it withheld a verdict (TRIANGULATE) where the evidence given supported a
conclusion (PASS); Baseline reached the correct conclusion and independently
reconstructed the real published discriminating mechanism (Fall et al. 2011's
canceling min/max trends).
**Ambiguous-case handling** (2 cases): Baseline 2/2, Treatment 1.5/2 — on
Case 10, Treatment partially resolved the genuinely open aggregate-level
question toward the skeptical pole instead of fully preserving the
settled(individual)/open(aggregate) split; Baseline preserved it precisely.
**Harm rate:** 0/0 — neither arm recommended REPLACE/REDEFINE on a clean
system.
**Actionability:** Treatment produced an explicit, concrete discriminating
test in 10/10 cases; Baseline did so explicitly in roughly 4/10.
**Per-case wins:** Treatment 5, Baseline 3, 2 ties — but the single largest
margin in the whole set (Case 7) favors Baseline, on the highest-stakes case
in the design.

**Adjudicator's verbatim overall verdict:** "Roughly comparable overall, with
different and largely complementary failure profiles... R1 [baseline] is
stronger at calibration and verdict formation... R2 [treatment] is stronger at
mechanism decomposition and experimental design... A combined workflow — R2's
channel-hunting and test design, gated by R1's verdict calibration — would
outperform either alone."

## Formal Pass Criteria (per the user's protocol)

| # | Criterion | Met? |
|---|---|---|
| 1 | Treatment finds ≥2 real failures baseline misses | ✅ (≥4-5: fit-target-as-validation circularity on Case 1, ABG co-oximetry independence on Case 2, named-and-rejected trap on Case 6, missing-data dispute on Case 9, alternative-construct test on Case 10) |
| 2 | Specificity ≥0.80 | ✅ (1.0 for both arms) |
| 3 | No critical false positive (REPLACE/REDEFINE on a clean system) | ✅ (harm rate 0/0) |
| 4 | Average diagnostic quality of Treatment exceeds Baseline | ❌ ("roughly comparable... neither shows a clear, consistent incremental advantage" — adjudicator's own words) |
| 5 | Improvement not explained by 1-2 textbook cases | Moot given #4 |
| 6 | Added complexity justified by the gain | ❌ (given #4) |

Criteria must hold **simultaneously** per the protocol. Two do not. **EXPAND
(full 13-gate version) is rejected.**

## Decision

**MERGE / SPECIALIZE, not EXPAND, not RETIRE.** The user explicitly declined
the tempting narrow fix ("apply broad model knowledge when specific studies
are named") as trading evidence discipline for passing one benchmark case.
Instead: `construct-measurement-gate` v0.2 removes its own final Verdict step
entirely, keeping only diagnostics (Steps 1–8: construct contract, measurement
chain, H_REAL/H_MEASURE, construct validity checks, measurement invariance,
independent-channel search, discriminating test design, risk profile) plus
advisory-only recommendations (Step 9, never REPLACE/REDEFINE directly) and an
explicit handoff (Step 10) to a downstream adjudicator (`hypothesis-arbiter`,
`boyko-scientific-consortium`, `skeptic`, or a human). This routes the gate's
demonstrated strength (mechanism decomposition, independent-channel discovery,
test design) to where it wins, and routes final verdict formation (where it
lost the highest-stakes case) to where the baseline-style free reasoning won.

The v0.2 architecture itself has **not** been separately benchmarked — this is
a response to the v0.1 finding, not a confirmed improvement. Per the user's
own "max one revision per cycle, then a new holdout or stop" rule, no new
blind holdout was run immediately. Next evidence source: real usage — cases
where the gate's diagnostics measurably change a downstream adjudicator's
decision — not another synthetic benchmark on the same question.

## Full agent transcripts

The curator's full 10 case packets + sealed ground truth, and both arms' full
per-case responses, and the adjudicator's full per-case reasoning, exist in
this session's agent transcripts (not reproduced verbatim here to keep this
file a readable summary rather than a ~50KB dump). This file is the citable,
committed artifact per this repo's anti-theater convention
(`scripts/check_architecture.py` gate 10) — the summary above is a faithful
condensation, not a fabrication; the underlying claim structure (which
mechanism was cited for which case, which arm said what) matches the source
transcripts word-for-word on the specific quotes reproduced.
