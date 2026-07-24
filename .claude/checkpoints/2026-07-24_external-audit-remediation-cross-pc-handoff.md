# Checkpoint — 2026-07-24, external-audit remediation, cross-PC handoff

## Why this checkpoint exists
Session end -- user leaving, explicitly asked for the repo to be in a
resumable state for another PC. This is that boundary marker.

## Branch / SHA
`main` = `3a3a336` (pushed to `origin/main`, CI green: test 3.11 ✅, test 3.12 ✅,
windows-install ✅ -- confirmed via GitHub check-runs API immediately before
this checkpoint was written, not assumed).

`git status --short --branch` clean at the time of writing. One known,
long-standing stray local branch, deliberately not deleted: `fix/reconcile-upstream-63-commits`
(2 commits, both auto-log noise, no unique real work -- `git branch -D` is a
standing denied command in this repo's permission policy and was not routed
around; harmless to leave, safe to delete manually if desired).

## What's done (full detail: `docs/baselines/2026-07-24-plan.md`)
- **P0 (A/B/C/D):** fully closed. D (SEC-01/SEC-02/AI-01 security risks) is
  a knowing, recorded user risk-acceptance, not an unaddressed gap.
- **P1 (12-15):** fully closed.
- **P2 item 17** (sec-auditor/security-guard + boyko-* "duplication"):
  verified `[DISMISSED]` on both halves, no code change.
- **P2 item 16** (skill maturity): in progress. `docs/skill-maturity-criteria.md`
  written. 4/128 skills now genuinely `dogfooded` (was 1/128 at session start):
  `hypothesis-arbiter`, `boyko-triangle-audit`, `boyko-why-ladder`,
  `intended-vs-implemented`. Each promotion = independent agent run + citable
  artifact under `skills/extensions/<name>/dogfood-runs/` + citations
  spot-checked with a real tool (grep/Read), not trusted on the agent's word.
  Plan's "5-10" target needs 1-6 more -- each is a real run, not a YAML edit.

## What's deliberately NOT done
- **P2 item 18** (vanilla/minimal/standard benchmark): not started. This repo's
  own `CLAUDE.md` requires an EstimandOps L0 gate + `estimand.md`
  (population/comparator/MCID) before building any comparative claim like
  this. Those are judgment calls for the user, not something to decide solo
  under "wrap up before I leave" pressure. Left honestly empty rather than
  built with invented numbers.
- **P3 (19-22):** not started at all -- memory-architecture split, perf,
  governance, installer polish. Long tail, lowest priority per the plan.

## Rollback
If anything here needs to be undone: every change landed as its own
`--no-ff` merge commit with a descriptive message (see `git log --oneline
b52ac5e..3a3a336` for this session's tail, or further back to `c53170f` for
the full remediation arc). `git revert -m 1 <merge-sha>` on any individual
merge commit cleanly undoes just that increment without touching the rest --
nothing in this session was squashed or rebased.

## Next action on pickup
1. `git fetch && git log --oneline -1 origin/main` -- confirm it shows
   `3a3a336` or later. If older, the push didn't take; if newer, another
   session continued past this point -- read those commits first.
2. Read `docs/baselines/2026-07-24-plan.md` for the authoritative per-item
   status (this checkpoint is a summary, that file is the detail).
3. Decide with the user: continue P2 item 16 (more promotions), start P2
   item 18's L0 gate (needs the user's input on population/MCID), or move to
   P3.
