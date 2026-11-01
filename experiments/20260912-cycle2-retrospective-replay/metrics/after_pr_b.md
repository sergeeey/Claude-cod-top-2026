# Frozen-corpus re-run after PR B (shared verdict extraction + section-format coverage)

The replay harness and corpus are unchanged from the PR #446 baseline; only the gate
under test changed. This file records the measured move so the claim in PR B's
description can be checked against an artifact rather than taken on trust.

## Verdict-detection coverage — the headline number

Measured over the 13 real `experiments/*/decision.md` files (`_template` excluded):

| Detector | Produced a definite reading | Notes |
|---|---|---|
| **Before** — `re.search(r"\[x\]\s*REJECT", ...)` | **1 / 13** | checkbox form only |
| **After** — `hooks/lib/verdicts.extract_verdict` | **12 / 13** | 9 KNOWN + 3 UNKNOWN_TOKEN |

Breakdown of the 12:

- **9 KNOWN** — a verdict in the canonical four-word vocabulary.
- **3 UNKNOWN_TOKEN** — reported verbatim, *not* normalised:
  `NEEDS-HUMAN` (`20260701-revive-session-save`), `RESOLVED`
  (`20260824-quote-splitting-sweep`), `NEEDS-MORE-DATA`
  (`20260912-research-evidence-loop-minimal-extension`).
- **1 UNPARSEABLE** — `20260728-hypothesis-arbiter-taxonomy-pilot`, which records **two**
  verdicts at different levels (`**Filing status: ARCHIVE**` and
  `**Claim-level result: REJECT**`). Choosing between them is an ontology decision, so
  the parser correctly refuses. Pinned as a regression fixture in `tests/test_verdicts.py`.

## Effect on `reject_gate_guard` over the same corpus

| | before PR B | after PR B |
|---|---|---|
| gate applies to | 1 / 12 | **3 / 12** |
| gate fires | 0 | **2** |

The two firings are `20260824-elai-hooks-skeptic-pilot` and
`20260824-permission-policy-skeptic-pilot` — the two "falsified-then-fixed" records.

**Signal quality improved even where the count went up.** Before the section-format fix
those two failed *all four* conditions, i.e. the gate claimed their Kill Analysis was
missing entirely, about files whose Kill Analysis is substantial and visible on screen.
After the fix, `elai-hooks` fails exactly one condition (`relaxation_map`). The remaining
failures are a genuine open question, not noise — see below.

## Deliberately NOT fixed here, and why

1. **`relaxation_map` requires a markdown table.** Both records document a relaxation in
   prose (`- **Relaxation:** claim re-stated post-fix as ...`). Whether prose satisfies
   the Relaxation Map requirement, or whether the table *is* the point (one row per
   surviving assumption, so the option space is visible), is a policy question for the
   falsification-status semantics work — not something a parser may decide.
2. **Short section labels.** `20260824-permission-policy-skeptic-pilot` writes
   `- **Killed:**` / `- **Not killed:**` rather than `What was killed` / `What was NOT
   killed`. Supporting the short form by loosening the match to a substring would make a
   lookup for `Killed` match `**Not killed:**` and return the SURVIVORS as the
   casualties. A confidently wrong answer is worse than a reported failure, so the
   pattern stays anchored and this is left as canonicalisation work — see
   `tests/test_reject_gate_guard.py::TestSection::test_bullet_phrase_is_anchored_not_a_loose_substring`.

## Controls

Unchanged and still passing: the `_template` negative control never fires; the known-good
REJECT (`20260728-osa-fl-protocol-vs-standard-analysis`) still passes all four conditions.
