# escape_route.md — [EXPERIMENT-ID]

_Fill BEFORE running the experiment. Not after. Pre-specifying actions per outcome
removes post-hoc bias and ensures every result produces information, not just "success"._

---

## Pre-Experiment Escape Route Map

| Possible Result | What it means | Immediate action |
|---|---|---|
| **Strong positive** (p < threshold, effect ≥ MCID) | Claim holds under these conditions | Design next test: which assumptions to stress next? List: |
| **Weak positive** (trend but below threshold) | Possible signal, insufficient power | Artifact audit: check confounds {A₁, A₂}. Increase n or run cheapest test for confound |
| **Null result** (no effect, p > 0.1) | Assumption(s) killed — specify WHICH ones below | Kill analysis (decision.md): what survived? Run Relaxation Map |
| **Negative result** (opposite direction) | Stronger falsification + possible mechanism insight | Document as null_results/. Check: does this kill related options V_? |
| **Noisy / contradictory** | Measurement or context assumption likely broken | Diagnostic: which of {A_measurement, A_context} is wrong? Run diagnostic test first |
| **Confounded** (correlates with known confounder) | Result not interpretable without controlling | Re-run with control for [confounder]. Do NOT interpret raw result. |

---

## Null Result Pre-Analysis
_If result is null: which assumptions are killed? Pre-specify NOW._

On null result, assumption(s) killed will be:
- Primary: A_ — because
- Possibly also: A_ — if

On null result, the following will NOT be killed:
- A_ — because (independent basis: )
- Core mechanism — because

---

## Cheapest Diagnostic Per Outcome
_For outcomes that require more data before deciding — what's the next step?_

| Outcome | Diagnostic | Cost |
|---|---|---|
| Weak positive | | |
| Noisy | | |
| Confounded | | |

---

## Anti-Overfitting Pre-Commitment
_Sign off BEFORE running: if result is null, I will NOT change more than ONE assumption
before the next attempt. Any multi-assumption change requires a new experiment ID and a
new claim.md._

- [ ] I commit to Minimal Relaxation Rule (one assumption at a time)
- [ ] Kill condition pre-specified: if [condition] → verdict = REJECT, no further revisions
- [ ] Stop condition: if [N] consecutive null results across Relaxation Map → archive the hypothesis

---

## Notes
_Context, environment, known confounds to watch for._
