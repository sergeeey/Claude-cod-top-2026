# decision.md — [EXPERIMENT-ID]

## Verdict

- [ ] PROMOTE — claim holds; merge to main / deploy
- [ ] REPEAT — inconclusive; need more data or different approach; document what to change
- [ ] REJECT — claim falsified → copy to `null_results/<id>-<slug>.md` + update INDEX.md
- [ ] ARCHIVE — valid but deprioritized → copy to `parked/<id>-<slug>.md` + update INDEX.md

## Evidence Summary

| Check | Result |
|-------|--------|
| Positive control | PASS / FAIL |
| Negative control | PASS / FAIL |
| Stress tests | PASS / FAIL / SKIPPED |
| Skeptic verdict | CONFIRMED / WEAKENED / FALSIFIED / SKIPPED |

**Skeptic result:** [attach skeptic output or write SKIPPED with reason]

## Rationale
_Why this verdict, not another._

## Skeptic Concerns and Resolution

| Concern | Resolution |
|---------|-----------|
| [concern 1] | Accepted / Mitigated / Dismissed — [reasoning] |
| [concern 2] | Accepted / Mitigated / Dismissed — [reasoning] |

## If REPEAT: What Changes Next Attempt
_Required. Vague "try again" is not acceptable._

- Change:

## If REJECT: Kill Analysis (OSA)
_Required. Do NOT write "hypothesis falsified" without this decomposition._

### What Was Killed
_Be specific: H under conditions {A₁ ∩ A₂ ∩ A₃}, not "the whole idea"._

- The claim as stated under: {  }
- Specifically, assumption(s) killed: {  }

### What Was NOT Killed
_Explicit list. These survive and can anchor future variants._

- [ ] Core mechanism / theoretical basis:
- [ ] Assumption [A_]: (survived because: )
- [ ] Assumption [A_]: (survived because: )

### Relaxation Map (for surviving assumptions)
_Minimal Relaxation Rule: change ONE assumption at a time per variant._

| Assumption | Modification | New Path | Known kill-evidence? | Cheapest test |
|---|---|---|---|---|
| A_ | Remove | V1: | No | [test, N days] |
| A_ | Weaken | V2: | No | [test, N days] |
| A_ | Replace | V3: | Check: | [test, N days] |

_Kill any row where "Known kill-evidence" = Yes before running the test._

### Why This Differs From Prior Null Results
_Required if null_results/INDEX.md has a matching entry._

- Prior null result entry: `null_results/<prior-id>.md`
- How this attempt differed:
- Why it still failed:

## Pearl Card Update
_If this experiment was triggered by a fix: commit, pattern_extractor.py auto-prompted Prediction
and Falsification fields. Record the outcome here so the next reader knows whether the pattern held._

**Was the Prediction correct?** Yes / No / Not testable yet

**Falsification condition triggered?** Yes (claim rejected) / No / Partially

_If you need to manually update patterns.md, find the [AVOID] entry matching this claim
and add a line: `- Outcome [date]: Prediction was [correct/wrong] — [one sentence]`_
