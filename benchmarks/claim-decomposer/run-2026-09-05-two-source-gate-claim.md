# claim-decomposer — two-source Gate 10 claim, atomic decomposition

**Date:** 2026-09-05
**Object:** does `claim-decomposer`'s atom/contradiction-map process find a
real, structural block in a causal claim, including something the prior
`skeptic` review of the SAME claim did not explicitly name -- or does it
just restate the skeptic verdict it was given?

## Why this run exists, and an honesty caveat up front

This is not a blind, independent test: `claim-decomposer` was invoked with
skeptic's FALSIFIED verdict already stated in its arguments (see the sibling
`cross-domain` benchmark for the original claim and skeptic review). Any
apparent "agreement" with skeptic is NOT independent corroboration -- it is
analysis performed with the answer already visible. The value of this run is
whether the atomic decomposition process surfaces something ADDITIONAL, not
whether it reaches the same headline verdict.

## Protocol

Ran the skill's 6-step protocol for real against the actual claim text and
the actual Gate 10 code (`scripts/check_architecture.py`'s
`gate_maturity_declared`).

## Result

**7 atoms extracted**, with a dependency chain (C1 technical feasibility ->
C2 behavioral compliance -> C3 semantic validity of that compliance) and a
separate baseline chain (C4 current 100% single-source -> C5 causal drop
claim). C6 (measurement validity) and C7 (uniform-scope design choice) named
as cross-cutting.

**Math-Code Trace step (Step 3) surfaced a finding skeptic's review did not
explicitly name:** tracing the actual Gate 10 code line-by-line
(`target = str(evidence).split(" -- ", 1)[0]...`) shows the current parser
only ever validates the FIRST citation target before the first ` -- `. Even
the naive "mentions a second source" regex extension proposed in the original
claim does not fit this existing single-split structure without a broader
parser redesign -- a distinct IMPLEMENTATION gap, separate from skeptic's
semantic ("mention != independence") and measurement (circular metric)
objections.

**Contradiction Map** found one blocking contradiction: C5 (the causal drop
claim) × C6 (measurement validity) -- if the proposed measurement cannot
distinguish real corroboration from compliant text, the causal claim is not
merely unconfirmed but **structurally untestable by its own stated protocol**.
This formalizes skeptic's Point 3 (circular toy-test) as a specific atom-pair
contradiction rather than a general observation.

**Verdict: KILL** for the claim as literally stated. The recomposed surviving
claim (provenance-metadata disjointness, checked by code without write
access to the evidence field) matches skeptic's own suggested reformulation --
noted explicitly as NOT independent confirmation, since this run had already
seen that reformulation in its input.

## Result vs the object question

Partially yes: the process did more than restate skeptic's verdict -- the
Math-Code Trace step's parser-structure finding is a genuine, distinct,
additional result not present in the skeptic review this run was given. But
the honest limitation stands: this was not a blind test of whether
`claim-decomposer` reaches sound verdicts independently; it was a test of
whether its structured process adds value ON TOP OF an already-known verdict.
A real test of independent convergence would need a claim decomposer given
the claim BEFORE any skeptic review exists.

## Limitation

Not context-asymmetric (unlike the cross-domain -> skeptic handoff, which
followed `falsification-ladder.md`'s Context Asymmetry Rule correctly). This
run's design is a genuine gap for a future, cleaner benchmark: run
`claim-decomposer` FIRST on a new claim, independently, before any skeptic
review exists, to test blind convergence rather than post-hoc elaboration.
