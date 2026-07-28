# estimand.md — 20260728-osa-fl-protocol-vs-standard-analysis
# Required for: FL Full-Ladder + question_type = causal
# Protocol: rules/estimand-ops.md

## L1 Attributes

**Population:** Real historical claims from this repo's `null_results/` with a
documented REJECT verdict, used in PRE-verdict raw form (n=2, pilot —
`20260716-regex-composition-response-guard`, `20260716-llm-judge-response-guard`).

**Intervention:** Arm B — fresh agent applies this repo's actual OSA/FL/Perelman
apparatus (claim_entropy-style reasoning, No-Collapse-Test-style stability
check, Kill Analysis: what's killed / what's NOT killed / Relaxation Map, AOG
if a revision is proposed) to the raw claim + evidence, blind to the real verdict.

**Comparator:** Arm A — fresh agent applies standard/informal expert analysis
(no formal scaffolding) to the SAME raw claim + evidence, blind to the real verdict.

**Endpoint:** Blind-graded 0–12 rubric score (4 sub-scores × 0–3: root-cause
match, anti-pattern avoidance, falsifiability/specificity, actionability),
scored against the real documented null_results verdict as semi-gold-standard.

**Summary measure:** Per-case score difference (Arm B − Arm A), reported
individually per case, not pooled (n=2).

**MCID:** ≥3 points (of 12) on a given case, pilot-only threshold, not
confirmatory.

---

## Intercurrent Events (ICE)

_Post-baseline events that change endpoint meaning or measurability. ICE is NOT missing data._

| Event | Strategy | Rationale |
|-------|----------|-----------|
| Arm's output shows contamination (references or appears to have seen the real null_results verdict/file) | while-active — exclude that case from scoring, log separately, do not impute a score | A contaminated run doesn't measure "method quality," it measures "did it copy the answer" — treating it as missing data and imputing would hide a validity failure instead of reporting it |
| Blind grader's rubric call is genuinely ambiguous on a sub-score | hypothetical — record the grader's stated uncertainty alongside the score, do not force false precision | Forcing a confident number onto a genuinely uncertain read is the exact "false precision" failure mode this whole experiment exists to avoid importing (see Context in claim.md) |
| One arm's agent refuses or fails to produce a verdict (e.g. errors out) | composite — treat as the worst possible score (0/12) for that arm on that case, not a missing value | A method that fails to produce an answer has failed at the task being measured; excluding it would bias the comparison toward the method that runs, not the method that reasons well |

---

## Natural Language Statement
_Written BEFORE collecting results._

> We estimate the per-case difference in blind-graded verdict quality (0–12
> rubric) between applying this repo's full OSA/FL/Perelman protocol (Arm B)
> and standard informal analysis (Arm A) to the SAME raw pre-verdict
> claim+evidence, across 2 real historical null_results cases, handling
> contamination via exclusion and refusal via worst-case scoring, reporting
> each case individually rather than pooling (n=2, pilot only).

---

## Causal Layer (question_type = causal)

### DAG

```
[Analysis Method: Arm A / Arm B] ---------> [Blind-Graded Score 0-12]
        ^                                          ^
        |                                          |
 [assigned by experiment                   [Grader's own skill/bias]
  design — fixed, not chosen                (mitigated: same grader
  based on any case property]                or grading rubric for
                                              both arms per case)
        |
        v
[Raw claim+evidence (frozen,
 identical for both arms per case)]
```

The method (A vs B) is the manipulated variable; the raw material is held
fixed per case (both arms see byte-identical input). This is closer to a
randomized/controlled design than an observational one: assignment of
method-to-run is fully under experimenter control and does not depend on any
property of the case or the agent, so there is no case-level confounding path
into the method variable itself. The main threat to identifiability here is
not confounding of the treatment assignment (that's controlled by design) but
**measurement validity of the endpoint** — i.e., whether the blind grader's
score is actually independent of which arm the grader believes they are
reading (see Exchangeability row below).

### Identifiability Checks

| Assumption | Status | Evidence / Notes |
|-----------|--------|-----------------|
| Consistency: Y = Y^a when A=a | satisfied | Each arm produces one observed output under one method; no interference between the counterfactual "what Arm A would have said" and what Arm B actually said — they're independent agent runs on the same frozen input. |
| Positivity: P(A=a given L) > 0 for all a, L in support | satisfied by design | Both arms are run on every case (no case is method-restricted); this is enforced by the experiment design, not observational selection. |
| Exchangeability: Y^a independent of A given L | **at risk — requires blind grading to hold** | If the grader can tell which output came from which arm (e.g. Arm B's output is longer / uses recognizable rubric jargon like "claim_entropy" or "Kill Analysis"), grading is no longer blind and a grader-side prior about "the protocol is better" can leak into the score. Mitigation: grader receives ONLY the two outputs, unlabeled and order-randomized-by-case (not by a `random()` call — assigned manually per case to avoid the environment's `Math.random()` prohibition), with instruction to flag if either output reveals its own arm identity (logged as a contamination-adjacent ICE, not silently scored). |
| SUTVA: no interference between units, no hidden treatment versions | satisfied with a caveat | The 2 cases are graded independently by the same grader in the same session — no cross-contamination between cases is expected, but using the SAME grader across both cases (rather than 2 independent graders) means grader-level idiosyncrasy is a shared, non-independent error source across the n=2 sample. Documented as a known limitation, not fixed in this pilot (fixing it would require ≥2 independent graders per case, out of scope for a 2-case pilot). |

> Hard stop check: none of the 4 assumptions is violated outright; Exchangeability
> is downgraded from "satisfied" to "at risk, mitigated" rather than "violated" —
> proceeding is justified, but the blinding mitigation is load-bearing and must
> actually be followed during grading, not just declared here.

### Identification Strategy
[x] Randomization — method-to-run assignment is fully controlled by the
    experimenter (not observational), which is the practical equivalent of
    randomization for a 2-arm within-case comparison. No IV/RD/DiD/g-formula/
    TMLE needed given the controlled-assignment design.

### Unmeasured Confounders

- **Grader fatigue/order effects**: mitigation — grade both arms for a case
  back-to-back in the same sitting, not the two cases interleaved by arm.
- **Agent run-to-run variance unrelated to method** (e.g. one run is just
  worse by chance, not because of the method): mitigation — none applied in
  this pilot (would require multiple runs per arm per case, out of scope at
  n=2); documented explicitly in "What This Result Does NOT Mean."

---

## What This Result Does NOT Mean
_Written BEFORE collecting results._

1. Does NOT prove the protocol is worth its overhead in general — n=2 is a
   pilot; confirmatory evidence needs the same opportunistic accumulation
   already used in `20260727-config-effectiveness-opportunistic`.
2. Does NOT control for single-run variance — each arm is run ONCE per case;
   a bad Arm B run could reflect agent variance, not protocol weakness (and
   vice versa for Arm A).
3. Does NOT generalize beyond REJECT-verdict null results — both cases are
   rejections; PROMOTE-shaped claims are untested here.
4. Does NOT establish which specific protocol mechanism (if any) drives a
   score difference — the intervention is "the whole protocol," not a single
   isolated component; attributing an effect to one mechanism would need a
   factorial design this pilot doesn't run.

---

## Sensitivity Analyses

1. **Alternative grading**: if grader flags contamination (arm identity
   leaked through style), re-score with the flagged sub-scores excluded
   rather than zeroed, and report both readings.
2. **Alternative comparator framing**: treat Arm A's "no scaffolding"
   instruction itself as one specific operationalization of "standard
   analysis" — report the actual Arm A prompt verbatim so a future replication
   can vary it (e.g. an ACH-matrix-style structured-but-non-OSA baseline)
   without re-deriving the estimand from scratch.
