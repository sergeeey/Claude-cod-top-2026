# harvest — side-value scan of this session's own skill-maturity sprint

**Date:** 2026-09-05
**Object:** does `/harvest scan` (Mode 1 + inline Mode 2 scoring) surface real,
distinct, actionable side-assets from this session's own work -- not
restating the main goal, not padding with trivial observations?

## Protocol

Ran the 7 scan questions in autonomous mode (user had explicitly authorized
unattended continuation across the remaining skill list; answered from real
session facts, not invented). Scored each surfaced asset with the skill's own
Reuse+Pain+Proof+Uniqueness formula.

## Result

**Assets found and scored:**

| Asset | Type | Score | Action |
|---|---|---|---|
| `benchmarks/<skill>/run-<date>.md` citable-evidence convention paired with Gate 10's anti-theater check | process_asset | 17/20 | Check as a standalone methodology writeup |
| Usage-audit method (structured grep on `"name":"Skill","input":{"skill":"..."}` across all session transcripts, not crude text-substring matching) | code_asset | 16/20 | Extract as a standalone mini-tool |
| `_nudge_commit_count()` session-scoped throttle pattern in `post_commit_memory.py` | code_asset | 14/20 | Extract to a reusable helper if a second hook needs the same debounce |
| "Two-source provenance-metadata gate" idea (naive form already FALSIFIED by skeptic this session) | research_asset | 10/20 | Keep as a note, not a build target |

**Top asset:** the usage-audit method (16/20) -- the only one with Reuse=5
(already independently applied twice this session to different questions:
skill usage ranking, then tool/agent usage ranking) and no dependency on this
specific repo's structure.

## Result vs the object question

Yes: the 4 surfaced assets are distinct from the sprint's main goal (skill
maturity promotion) and from each other -- one methodology pattern, one
reusable script, one code helper, one parked research note. None restate
"we promoted 5 skills," which is the main-goal outcome, not a side-asset.

## Limitation

Single scan pass, no external validation of the 17/20 and 16/20 scores (no
`skeptic` stress-test of the promote-worthy assets, per the skill's own
suggested next step for anything scoring 17+). n=1 project (this repo,
this session) -- no claim of generality to other projects' harvest scans.
