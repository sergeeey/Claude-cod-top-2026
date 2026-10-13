# decision.md — [EXPERIMENT-ID]

## Verdict

- [ ] PROMOTE — claim holds; merge to main / deploy
- [ ] REPEAT — inconclusive; need more data or different approach; document what to change
- [ ] REJECT — claim falsified → copy to `null_results/<id>-<slug>.md` + update INDEX.md
- [ ] ARCHIVE — valid but deprioritized → copy to `parked/<id>-<slug>.md` + update INDEX.md

## Result Classification (End-of-session diamond scan)

_Независимо от Verdict: что нашли по пути?_

- [ ] 🥇 **Gold** — отвечает на главный вопрос проекта
- [ ] 💎 **Diamond** — неожиданный результат, ценный сам по себе вне проекта
- [ ] 🥈 **Silver** — техника/метод, переносимый в другие проекты
- [ ] 🪨 **Stone** — NULL без переносимой ценности

**Если Diamond или Silver:** добавить в `~/.claude/memory/cross_domain_insights.md`

| Инсайт | Куда применимо |
|--------|----------------|
|        |                |

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

### Escape Point
_Fill AFTER Kill Analysis. Where should this failure have been caught earlier, but wasn't?_

- Should have been caught at: [Zero-Signal Gate / estimand step / controls / skeptic / stress test / external oracle / other]
- Why it wasn't: [missing check / wrong assumption about input / tool not used / skipped step]
- Guard to add: [specific hook, checklist item, or template field that would catch it earlier next time]

### Why This Differs From Prior Null Results
_Required if null_results/INDEX.md has a matching entry._

- Prior null result entry: `null_results/<prior-id>.md`
- How this attempt differed:
- Why it still failed:

## Post-promotion correction (fill ONLY if a promoted claim later turns out wrong)

_Leave empty for every experiment that was never promoted, or whose promotion still holds._

**WHY this section exists (Cycle 2, `experiments/20260912-cycle2-retrospective-replay/ledger.md`
Entry 0):** the methodology's own success criterion is "fewer false promotions", which requires
counting them. A search of this repository's entire history found the event recorded **zero
times** — not because it never happened, but because it had no place to be written. A
reduction measured against an unrecorded baseline is a reduction from zero-known to
zero-known. This section is that place. It is deliberately inside the promoted experiment's own
`decision.md`, next to the verdict being corrected, following the precedent already set by
`20260903-memory-retrieval-repair/decision.md:514` ("**This verdict was WRONG and was
overturned**").

**Two tiers, kept distinct** — the same naming discipline `scripts/false_pass_rate.py` adopted
after an external review caught it overclaiming (it was renamed to *suspected*_false_pass
because "the metric was named more precisely than it measures"):

| Tier | Criterion | Who decides |
|---|---|---|
| **SUSPECTED** | a PROMOTE/VERIFIED verdict, followed within ~30 days by a `fix`/`revert`/`hotfix` commit touching files this experiment named | heuristic — the same method `false_pass_rate.py` already applies to agent verdicts, transplanted to experiment promotions. A signal to look, never a verdict. |
| **CONFIRMED** | someone read the later evidence and established the promoted claim was **wrong as stated** | a human or an agent, in writing, with the evidence cited |

Record a CONFIRMED case with this exact marker so the count is greppable
(`grep -rc "\[FALSE-PROMOTION\]" experiments/*/decision.md`) — no registry file, no gate:

```
[FALSE-PROMOTION] <YYYY-MM-DD> — <what was promoted, one line>
  Found false by: <what surfaced it — a later test, an incident, an external review>
  Wrong in what way: <as-stated / over-scoped / right result, wrong mechanism>
  Evidence: <file:line, commit, or PR — not "it seemed off">
```

A SUSPECTED case that was investigated and turned out fine is worth one line too, marked
`[FALSE-PROMOTION-DISMISSED]` with the reason. A detector whose false positives are never
recorded can never have its precision computed — the gap `scripts/hook_metrics.py` names in
its own docstring ("NOT included on purpose: precision/recall — requires ground-truth labels
we don't have yet").

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

**Crosswalk to `graph.yaml`'s `status` field (Research/Evidence Loop minimal extension,
2026-09-12 — see `docs/experiment-dependency-graph.md`):** if this experiment declares an
OPTIONAL `graph.yaml`, its `status` field is the single machine-queryable source for
cross-experiment queries — it does NOT replace this table, `experiment.yaml`'s own `status:`,
or the human judgment either represents. Fill it consistently with whichever of those you
already wrote, per this mapping:

| This table's `Final Status` | `experiment.yaml`'s `status:` | `graph.yaml`'s `status` |
|---|---|---|
| `hard_killed` / `killed` | `rejected` | `KILLED` |
| `parked` | `archived` | `BLOCKED` |
| `weak_alive` | `running` | `ACTIVE` |
| *(promoted via the Perelman gate above)* | `completed` | `PROMOTED` (or `VERIFIED` if a sealed holdout was also opened and passed) |

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
