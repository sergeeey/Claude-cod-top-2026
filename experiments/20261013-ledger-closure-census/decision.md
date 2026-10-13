# decision.md — 20261013-ledger-closure-census

**Verdict: REPEAT** (descriptive census; the M1 half is answered, the M2 half is not).

| Part of the claim | Result | Reading |
|---|---|---|
| M1 >= 1/3 (ledger declared for behavior-changing PRs) | 9/66 = 0.14 | **Not met.** Frozen band "rule largely unused" fires. Robust to the parser's known misses (up to 11/66 = 0.17) |
| M2 >= 1/2 (declared, due predictions have a recorded outcome) | 1/2 (n = 2) | **Uninformative at this n.** No band applies; 0/2 under a stricter reading |

Escape route applied as written in `claim.md`: n < 5 declared-and-due -> report "uninformative at
this n" and re-run after the next 10 behavior-changing PRs. M2 < 1/2 with n >= 5 did not occur, so
the "propose a closure step" branch is not triggered.

## What this does and does not support

- Supported (descriptive): between 2026-09-10 and 2026-10-08 about 1 in 7 behavior-changing PRs
  carried a falsifiable prediction; 8 of the 10 ledgers date from the first two days; none after
  2026-09-27, while 20 behavior-changing PRs merged afterwards.
- Supported: half the ledgers (5 of 10) name "this PR's own CI" or a CI plus a short window as the
  check, so they close at merge by construction; only 4 of 66 point at a later check.
- NOT supported: that the ledger improves quality, that the lapse is a problem (the rule's own worked
  example says it "does not add detection"), or that this is typical beyond this repo and author.
- Evidence: [VERIFIED-REAL] on the counts; the closure judgement is single-coder.

## Pre-answered concerns (for a later skeptic pass, not yet run)

- "The denominator is wrong": yes, it is a path-based upper bound; M1 is stated as a lower bound of
  adherence in `result_summary.md`.
- "The first parser run was wrong": yes, 2 of 4 hand-read PRs were false positives; fixed and
  recorded as Amendment 1 before any closure was read, first-run numbers kept but unused.
- "Closure may live outside PR text": stated as limit 3; M2 is a lower bound for "closed anywhere".

## Options for the owner (nothing built, nothing changed in rules or hooks)

1. Leave as is. The census shows the ledger lapsed; whether that matters is unproven.
2. Re-run `python analyze.py` after the next 10 behavior-changing PRs (a fresh `gh` snapshot is
   needed; `data/snapshot_time.txt` must be updated). Cost: minutes.
3. Make the ledger cheaper to follow (for example a PR-body template section or a soft nudge on
   behavior-changing PRs). Not recommended now: no evidence yet that the ledger adds detection,
   and the repo's own history warns against adding config machinery without a measured need.

## Skeptic Concerns

Step 8a not run: nothing here is PROMOTE and no rule is changed.
