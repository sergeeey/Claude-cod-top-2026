# claim.md — 20261013-ledger-closure-census

Tier: Standard (descriptive census, no code change, no sampling comparison).
Protocol frozen 2026-10-13 BEFORE any PR body was classified. The only data looked at before
freezing: the count `85 merged since 2026-09-10 / 12 contain "Falsified if"` from an earlier
exploratory `gh` call (a rough number, not classified, with no denominator rule).

## Zero-Signal Gate

| Field | Value |
|---|---|
| **Entity** | PRs merged into `main` of `sergeeey/Claude-cod-top-2026` since 2026-09-10 (the date the Harness Change Ledger rule was added to `~/.claude/rules/meta-loop.md`) |
| **Falsifiable predicate** | The prediction-then-check loop of the Harness Change Ledger closes for most behavior-changing PRs: M1 >= 1/3 and M2 >= 1/2 (bands below) |
| **Measurable outcome** | M1, M2, M3 computed by `analyze.py` from a saved `gh` snapshot; closure judged by reading, listed PR by PR |

## L0: Question Type

- [x] Descriptive
- [ ] Predictive
- [ ] Causal

Reasoning: the causal version ("does the ledger improve the harness") is not identifiable with one
author, one repo and n of a few dozen (EstimandOps hard stop; same conclusion as Cycle 2 of the
Research/Evidence Loop). Only a census of what happened is asked.

## Natural Language Statement

> We estimate the share of behavior-changing PRs that declare a falsifiable prediction (M1), and
> the share of declared, already-due predictions for which an outcome was later recorded (M2), for
> merged PRs of Claude-cod-top-2026 from 2026-09-10 to the snapshot time, without a causal
> interpretation and without comparing against any other repository or period.

## What this result does NOT mean

1. It does NOT show that the ledger improves harness quality, or that PRs without a ledger are worse.
2. It does NOT generalize to other repositories, other authors, or sessions that never reach a PR
   (the rule also lives in global `~/.claude`, which the repo does not ship).
3. It does NOT measure whether a recorded outcome is correct, only whether one was recorded.
4. A closure not found in PR text, PR comments or later PR bodies may still exist elsewhere
   (memory files, chat). Those places are out of scope, so M2 is a lower bound for "closed anywhere".

## Design (census, MDE not applicable)

No sampling comparison: the whole finite population in the window is counted. No `alpha`, `power`
or `MDE`. Small n is reported as is; with fewer than 5 declared-and-due PRs M2 is called
"uninformative at this n" and no band applies.

## Frozen operational rules

**Population P.** `gh pr list --state merged --limit 300`, keep `mergedAt >= 2026-09-10T00:00:00Z`.
Snapshot time recorded in `data/snapshot_meta.json`. All authors kept.

**Behavior-changing (BC), by changed files.** A PR is BC if it changes at least one file matching:
`^hooks/` (excluding `hooks/CLAUDE.md`), `^rules/`, `^agents/`, `^commands/`,
`^skills/.+/SKILL\.md$`, `^skills/registry\.yaml$`, `^scripts/.+\.py$`, `^claude-md/CLAUDE\.md$`,
`^install\.sh$`, `^\.github/workflows/`.
Not BC: PRs touching only `tests/`, `docs/`, `README*`, `CHANGELOG*`, `.claude/memory/`,
`benchmarks/`, `experiments/`, `null_results/`, `parked/`, other.
**Strict sensitivity set:** `^hooks/` (excluding `hooks/CLAUDE.md`), `^rules/`,
`^scripts/(check_|gen_|sync_).+\.py$`. Reported next to the main set, not instead of it.

**Declared.** D1: body matches `(?i)falsified\s+if`. D4: body has all four labels `Change`,
`Prediction`, `Falsified if`, `Check after`, each as `(?i)\blabel\b\W{0,3}:`.

**Checkable.** The text after `Check after:` on the same line contains a digit (a date or a
count). A bare "later", "soon", "TBD" or an empty value is not checkable.

**Due.** If an ISO date is present: due when the date is <= snapshot. If "N PRs": due when at
least N PRs merged after this one. Anything else: `undeterminable`, excluded from M2 and counted.

**Closed.** Two levels, both reported.
- Mechanical candidate: a PR merged later, or a comment on the same PR written after its merge,
  whose text contains `#<n>` and one of: confirmed, falsified, held, wrong, surprise,
  prediction, ledger.
- Final: I read each candidate and mark CLOSED only if the text states what was observed
  compared with the prediction; otherwise NOT CLOSED. Single coder (the same actor that wrote
  most of the PRs). Every judgement is printed with the quoted sentence so it can be re-judged.

**Metrics.**
- M1 = declared(D1) / BC. Also reported: D1 / all P, D4 / BC, and M1 on the strict set.
- M3 = checkable / declared(D1).
- M2 = closed(final) / (declared and due), with the mechanical-candidate count next to it.

**Controls.**
- Negative control: PRs merged 2026-07-13 to 2026-09-09 (before the rule). Expect D1 close to 0.
  If D1 is high there, either the regex over-matches or the rule's date is wrong, and M1 is not
  interpreted.
- Positive control (parser): three declared PRs read by hand; the parser must agree on D1, D4 and
  checkable for all three. Disagreement means the parser is fixed and re-run before reading results.

**Provisional reading bands (no empirical basis, a heuristic like the 2.5x in skeptic-triggers):**
M1 < 1/3: rule largely unused. M2 < 1/2 with n >= 5: loop mostly open. Otherwise: no band.

## Escape route (decided before the result)

- M2 < 1/2 with n >= 5: propose, do not build, a closure step at the "Check after" date
  (owner decides). Pearl candidate only with the owner's word.
- M2 >= 1/2: leave the rule as is; the loop is not the bottleneck.
- n < 5 declared-and-due: report "uninformative at this n", re-run after the next 10 BC PRs.
- Negative control fails: stop, fix the parser or the date, re-run, record the change here.

## Claim Entropy (counted before the run)

| Component | Count |
|---|---|
| Unsupported HIGH claims | 0 |
| Hidden assumptions | 3 (rule start date = 2026-09-10; BC file list captures behavior change; closure is visible in PR text) |
| Missing negative controls | 0 |
| Ambiguous definitions | 1 (closure judged by reading) |
| Unresolved blockers | 0 |
| **Total** | **4** |

## Known weaknesses of the design

- Single coder for closure; the quoted sentences are the only audit trail.
- The ledger rule is personal-global; sessions without it loaded produce PRs without a ledger,
  which lowers M1 for a reason unrelated to discipline.
- BC by file path can misclassify: a one-line change in `scripts/` counts as BC.
- A prediction for a hook is often checked only by CI going green on the same PR, which the rule
  itself says "finds nothing CI missed"; such PRs may be declared but have no later closure text.

## Amendment 1 (2026-10-13, after the positive control, before any closure was read)

Positive control read by hand: PR #413 and PR #450 are parser false positives. #413 is the rule
text itself (a template with `<...>` placeholders and an inline example); #450 is a table header
`| Prediction | Falsified if |` with no prediction about its own change. PRs #424 and #476 were read
and agree with the parser. Per the control rule the parser is fixed and re-run.

Fix (applied to D1 and D4, nothing else changes): a label counts only when it starts a line
(after optional bullet, bold or quote marks), is followed by `:`, and has a value that is not a
placeholder (does not start with `<`); a line that starts with `|` (table row) never counts.
Numbers before the fix, kept for the record: declared D1 = 12, D4 = 8, M1 over BC = 10/66.
The first-run numbers are not used for any reading.
