# null_results/INDEX.md — Falsified Experiments Registry

_Entries here mean: this claim was tested and FALSIFIED. Do NOT retry without a fundamentally different approach._
_Before starting any new experiment, grep this file for your topic._

## How to add an entry

On REJECT verdict in `decision.md`:
1. Copy filled `decision.md` to `null_results/<id>-<slug>.md`
2. Add one row to this table

## How to record a REPEATED dead end

**WHY (Cycle 2, `experiments/20260912-cycle2-retrospective-replay/ledger.md` Entry 0):** the
methodology's success criterion includes "fewer repeated dead ends", which requires counting
them. A search of the whole repository found the event recorded **zero times** — not because it
never happened, but because it had nowhere to be written. This is that place, next to the dead
end that was re-entered.

`hooks/null_results_pre_check.py` already DETECTS the suspected case at prompt time (keyword
overlap of ≥2 tokens against this file). Two tiers, kept distinct:

| Tier | Criterion | Who decides |
|---|---|---|
| **SUSPECTED** | `null_results_pre_check` fires on a prompt | heuristic keyword overlap — a prompt to check, never proof |
| **CONFIRMED** | work actually proceeded down a path whose **failure MECHANISM** matches a recorded null result | a human or an agent, in writing |

**The confirmation test is the mechanism, not the name** — load-bearing, not pedantry. The same
spatial-CV methodology error was independently rediscovered **three times across three
repositories under three different names** (`memory-protocol.md` § Cross-project transfer step).
A name-match or keyword-match test would have missed all three. Ask *does this path fail for the
same reason the recorded one failed?* — not *does it share words with it?*

Record a CONFIRMED repeat as an indented block under the re-entered entry's row:

```
[REPEATED-DEAD-END] <YYYY-MM-DD> — re-entered `<null-result-id>`
  Shared failure mechanism: <the mechanism, not the topic>
  How far it got before the match was noticed: <prompt / design / partial run / full run>
  What the pre-check said: <fired and was ignored / did not fire / no pre-check ran>
```

That last field is what makes the record worth keeping: it separates "the detector missed it"
from "the detector caught it and a human overrode it" — two different failures needing two
different fixes.

**Recording a FALSE positive matters equally.** When `null_results_pre_check` fires on a prompt
that is *not* a repeat, add a `[REPEAT-PRECHECK-FALSE-POSITIVE]` line with the matched tokens and
why the match was spurious. Without those labels the detector's precision can never be computed —
the gap `scripts/hook_metrics.py` names in its own docstring ("NOT included on purpose:
precision/recall — requires ground-truth labels we don't have yet").

Count either with a grep — deliberately no registry file and no gate:
`grep -c "\[REPEATED-DEAD-END\]" null_results/INDEX.md`

### Observed detector firings (the precision baseline starts here)

All three below are FALSE positives observed live on 2026-09-12. They are the first labelled
data points for a precision figure this repository has never been able to compute. All three
share one shape: **a keyword match treated as an assertion** — the `[AVOID×7]` pattern
`patterns.md` already tracks.

[REPEAT-PRECHECK-FALSE-POSITIVE] 2026-09-12 — matched `20260716-regex-composition-response-guard`
  Matched tokens: `guard`, `regex`
  Why spurious: the prompt was about a verdict-extraction parser for `decision.md` files, not a
  response-guard classifier. Shared vocabulary, unrelated mechanism.

[REPEAT-PRECHECK-FALSE-POSITIVE] 2026-09-12 — matched `20260715-sde-cc-fabricated-historical-corpus`
  Matched tokens: `corpus`, `historical`
  Why spurious: that null result is about a FABRICATED corpus; the work here used the real
  existing one. The shared word `corpus` inverts the very property that was falsified.

[REPEAT-PRECHECK-FALSE-POSITIVE] 2026-09-12 — detector: `null_retroscan.py` (not the pre-check)
  Matched tokens: `keyword`, `never`, `overlap` against active PROMOTE `20260903-memory-retrieval-repair`
  Why spurious: it fired on the edit that added THIS section — reading a *description of a
  detector* as a newly-filed NULL result. No NULL was filed; the prose merely contains the
  vocabulary a NULL entry would use. Recorded because it is a different detector from the two
  above and therefore an independent data point, and because a hook mis-classifying
  documentation about itself is the sharpest possible illustration of the shared failure shape.

## Index

| ID | Date | Slug | Verdict | Why falsified (10 words max) |
|----|------|------|---------|------------------------------|
| example | 2026-01-01 | example-claim | REJECT | baseline matched complex model, no added value |
| 20260715-sde-cc-fabricated-historical-corpus | 2026-07-15 | sde-cc-fabricated-historical-corpus | REJECT | 3/3 spot-checks failed, zero sources, benchmark unrun |
| 20260715-pairwise-elo-tournament-premature-recommendation | 2026-07-15 | pairwise-elo-tournament-premature-recommendation | REJECT | source claimed opposite: pairwise less stable, not more |
| 20260716-regex-composition-response-guard | 2026-07-16 | regex-composition-response-guard | REJECT | 0/0 on calibration, 6/8 held-out — regex can't classify context |
| 20260716-llm-judge-response-guard | 2026-07-16 | llm-judge-response-guard | REJECT | red-team: weak injectable model gating sole control on highest-value attacks |
| 20260728-osa-fl-protocol-vs-standard-analysis | 2026-07-28 | osa-fl-protocol-vs-standard-analysis | REJECT | n=2 pilot: full protocol scored lower than plain analysis on both cases |
| 20260907-null-results-semantic-topup | 2026-09-07 | null-results-semantic-topup | REJECT | TF-IDF: no signal; real embeddings: work but cost 11.7s per hook call |
| 20260908-toolgate-blanket-benchmark-factory | 2026-09-08 | toolgate-blanket-benchmark-factory | REJECT | 190,848 tokens/3 candidates on 1 skill; mechanism works, catalog-wide economics don't |
