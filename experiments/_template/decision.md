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

## Evaporating Cloud (fill if verdict required a trade-off)
_TOC tool: don't accept conflict as given — find the hidden assumption that makes it seem necessary, then inject a solution that dissolves it. A good conflict doesn't get resolved by compromise; it evaporates._

| Field | Value |
|-------|-------|
| **Goal** | [shared objective both sides serve — e.g. "ship reliable software fast"] |
| **Need A** | [what side A requires to achieve the goal] |
| **Need B** | [what side B requires to achieve the goal] |
| **Action A** | [what Need A demands — e.g. "thorough manual testing"] |
| **Action B** | [what Need B demands — conflicts with A — e.g. "deploy immediately"] |
| **Hidden assumption** | [why A and B seem mutually exclusive — e.g. "only manual testing ensures quality"] |
| **Injection** | [what disproves the assumption — e.g. "automated test suite covers 90% of cases"] |
| **Outcome** | [both needs satisfied without compromise — or document the unavoidable cost] |

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

### Escape Point
_Where should this defect/failure have been caught, but wasn't? Naming it prevents the same miss next time._

- Should have been caught at: [Zero-Signal Gate / estimand step / controls / skeptic / stress test / external oracle / other]
- Why it wasn't: [missing check / wrong assumption about input / tool not used / skipped step]
- Guard to add: [specific hook, checklist item, or template field that would catch it earlier]

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

## Rescue Review (OSA)
_Run after Kill Analysis. Distinguishes "killed formulation" from "killed branch"._
_Rescue cannot promote a branch to `alive` by narrative alone. Maximum output without AOG: `parked`._

| Branch | What Red Team killed | Whole branch dead? | Weaker formulation | Revival Condition | AOG risk | Final Status |
|---|---|---|---|---|---|---|
|  |  | yes / no |  |  | low / medium / high | hard_killed / killed / parked / weak_alive |

**Rescue rules:**
- `hard_killed`: direct contradiction, theorem, or verified null result only. Outside Rescue scope.
- `killed`: formulation falsified; new branch allowed (Minimal Relaxation Rule applies).
- `parked`: branch has a potential bridge but is not usable as evidence. Revival Condition required.
- `weak_alive`: weaker non-circular formulation + Revival Condition + cheapest differentiating test + AOG passed.
- If AOG risk = high → final status cannot exceed `parked`.
- Flow: Red Team → Rescue Review → AOG Check → Final Status.

---

## Hypothesis Generation Mode (OSA)
_Run when major branches have been killed or parked. Input: surviving assumptions + null results + parked pearls._
_Do not run from random brainstorming — only from explicit Kill Analysis output._

| New Branch | Parent Null Result | Surviving Assumption | Imported Mechanism | Revival Condition | Cheapest Test | Initial Status |
|---|---|---|---|---|---|---|
|  |  |  |  |  |  | unknown |

**Procedure (one branch at a time):**
1. Select one killed branch; state explicitly what was killed and what survived.
2. Find one adjacent mechanism from a different domain or discipline.
3. Propose weaker non-circular formulation (must not assume the desired result).
4. Define Revival Condition (specific, measurable, not "more data").
5. Define cheapest differentiating test (see FL Cheapest Test Protocol).
6. Run Anti-Overfitting Gate before promoting beyond `unknown`.

---

## Pearl Card Update
_If this experiment was triggered by a fix: commit, pattern_extractor.py auto-prompted Prediction
and Falsification fields. Record the outcome here so the next reader knows whether the pattern held._

**Was the Prediction correct?** Yes / No / Not testable yet

**Falsification condition triggered?** Yes (claim rejected) / No / Partially

_If you need to manually update patterns.md, find the [AVOID] entry matching this claim
and add a line: `- Outcome [date]: Prediction was [correct/wrong] — [one sentence]`_
