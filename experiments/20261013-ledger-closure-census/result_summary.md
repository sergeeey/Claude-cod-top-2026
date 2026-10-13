# result_summary.md — 20261013-ledger-closure-census

Snapshot: 2026-10-13T14:29:23Z. Population: 85 merged PRs since 2026-09-10 (last merge 2026-10-08).
Rules: `claim.md` (frozen 2026-10-13, sha256 in `prereg.sha256`) + Amendment 1 (`prereg_amended.sha256`).
Raw output: `data/results.json`. Every number below comes from `analyze.py` unless marked exploratory.
Evidence level: [VERIFIED-REAL] (real PRs via `gh`), single coder for the closure judgement.

## Controls

| Control | Result |
|---|---|
| Negative: 215 PRs merged 2026-07-13..09-09 (before the rule) | 0 declared (0/215). Parser does not invent ledgers |
| Positive (parser vs hand reading), first run | **Failed on 2 of 4 read**: #413 (the rule text with placeholders) and #450 (a table header) counted as declared. Parser fixed (Amendment 1), re-run; #424 and #476 agreed both times |
| Spot-check of the BC rule on 3 PRs via `gh pr view` | #424 docs-only (not BC), #476 SKILL.md (BC), #513 hooks/ (BC): all as classified |

## Metrics (after Amendment 1)

| Metric | Value |
|---|---|
| BC PRs / all PRs in window | 66 / 85 |
| **M1** declared over BC | **9/66 = 0.14** (first run before the fix: 10/66 = 0.15, not used) |
| M1 over all PRs | 10/85 = 0.12 |
| M1, all four labels (D4) over BC | 7/66 = 0.11 |
| M1, strict set (hooks/, rules/, gate scripts) | 5/47 = 0.11 |
| **M3** declared with a checkable "Check after" | 4/10 = 0.40 |
| Declared PRs due at snapshot / not due / undeterminable | 2 / 0 / 8 |
| **M2** closed over declared-and-due | **1/2 (n=2 < 5: uninformative at this n, no band applies)** |

Reading against the frozen band: **M1 < 1/3 -> "rule largely unused" fires.** M2: no band (n<5).

## M2 judgement, quoted (the only two due ledgers)

- **#424** (check: "next 5 distribution findings, or 2026-10-11"): the later PR #427 says "Half the
  recorded prediction did not survive contact" and names which half. Counted CLOSED by the frozen
  definition, but it is a **partial** closure written at implementation time, not at the check
  date. The headline prediction (no drift incident in the kinds the extended guard covers by
  2026-10-11) has no recorded outcome. Under a stricter "closed at or after the check date" reading
  M2 would be 0/2.
- **#427** (same check): later PRs #428 and #430 mention it but do not compare an observation with
  its prediction. NOT CLOSED.

## What "Check after" points at (10 declared ledgers, read by hand)

| Kind | PRs | Count |
|---|---|---|
| "this PR's own CI" (closes at merge by construction) | 415, 416, 417, 420 | 4 |
| CI, then the next 20 router firings | 418 | 1 |
| next `/skill-doctor` run (undated event) | 419 | 1 |
| next 5 findings or a date | 424, 427 | 2 |
| a count of real uses of a skill (5; three) | 476, 488 | 2 |

Only **4** of 66 BC PRs (424, 427, 476, 488) point at a future check that could stay open for
weeks, and only 2 of those carry a date or a repo-countable trigger.

## Exploratory (NOT pre-registered; label it so wherever it is quoted)

- Timeline of BC PRs declared per ISO week (weeks 37 to 41): 7/35, 0/6, 2/5, 0/16, 0/4. Eight of
  the ten declared ledgers date from 2026-09-10 and 2026-09-11, the first two days after the rule
  was added. None after 2026-09-27, while 20 BC PRs merged in weeks 40 and 41. Descriptively: use
  was front-loaded and has lapsed.
- Parser misses: PR #487 holds a real ledger written as free prose under the heading "Проверяемая
  гипотеза (Harness Change Ledger)" (a prediction, a rollback condition and "~2 weeks, >=15
  sessions"), and #502 refers to a prediction recorded in the pearl registry. With both counted
  M1 would be 11/66 = 0.17, still below 1/3; the reading does not change.
- 18 BC PRs mention "prediction/falsified/ledger" in other senses (a rule they changed, a rejected
  design); only the two above are plausible ledgers.

## Limits that bound every number above

1. BC by file path overstates the denominator (a one-line `scripts/` edit counts), so M1 is a
   lower bound of adherence, not adherence.
2. The rule is global (`~/.claude/rules/meta-loop.md`), not shipped by the repo; whether it was
   loaded in the session that wrote each PR is not recorded.
3. Closure was searched only in PR bodies, own post-merge PR comments and later PR bodies.
   Closures kept in memory files or chat are invisible here.
4. Single coder; the quoted sentences are the audit trail.
