# controls.md — 20261013-ledger-closure-census

## Negative control (known-bad input: no ledger can exist)

PRs merged 2026-07-13 to 2026-09-09, before the Harness Change Ledger rule existed (215 PRs in the
snapshot). Expected: about 0 declared. Observed: **0/215** with the amended parser (and 0/215 with
the first parser). Parser does not invent ledgers on text that predates the rule.

## Positive control (known-good input: ledgers a human can read)

Four declared PRs read by hand against the parser, before any closure was read:

| PR | Hand reading | First parser | Amended parser |
|---|---|---|---|
| #413 | rule text with placeholders, not a ledger | declared (WRONG) | not declared |
| #450 | table header only, no prediction | declared (WRONG) | not declared |
| #424 | real ledger, check after "next 5 findings, or 2026-10-11" | declared | declared |
| #476 | real ledger, check after "5 использований" | declared | declared |

The first parser failed the control (2 of 4). The fix and its reason are in `claim.md` Amendment 1;
the first-run numbers are kept in `result_summary.md` and not used.

**Known miss after the fix (exploratory find, not fixed on purpose):** #487 is a real ledger in
free prose under a Russian heading, which the label-based parser cannot see. The frozen rule stays
as written; the effect (M1 from 0.14 to at most 0.17) is reported next to the main number.

## Classification control (BC by file path)

`gh pr view` file lists checked for #424 (docs only, not BC), #476 (SKILL.md, BC), #513
(hooks/ and tests/, BC): all as the script classified.

## What no control here can do

The closure judgement (CLOSED / NOT CLOSED) has no ground truth and no second coder; it is audited
only by the quoted sentences in `result_summary.md`.
