# decision.md — 20260701-revive-session-save

## Decision: NEEDS-HUMAN (informational — the premise was already false, so no REVIVE/KILL/PARK applies)

Per the revive-project decision table: `REVIVE`/`REVIVE-CONDITIONALLY`/`PARK`/`KILL`
all presuppose the project WAS dead or uncertain. The autopsy (Stage 1) settled the
question descriptively before any experiment was needed: **hooks/session_save.py is
alive** — registered on the `Stop` event via `async_wrapper.py`, most recently touched
by a substantive security-hardening commit (2dbc4f9: path traversal, OOM, bearer token
exfil fixes), not a stale/abandoned commit.

`NEEDS-HUMAN` is used here in its literal sense from the command's own decision table
("depends on strategy... domain judgment") — specifically: **whether to invest in test
coverage for this file is a resourcing/priority decision, not something this run can
or should decide unilaterally.** That is the one real, actionable finding this run
produced, and it is a strategic call for a human, not an engineering fact this run can
settle on its own (unlike "is it alive", which was settled with certainty).

## Evidence Gate

Not applicable in the traditional sense (no revival claim to promote) — but the
DESCRIPTIVE claim ("this file is alive, not dead") is itself evidence-gated:

| Requirement | Status |
|---|---|
| Baseline | ✅ "abandoned" framing from the run's own prompt, treated as the null hypothesis to test, not assumed |
| Positive control | ✅ hook registration in settings.json — real grep, real file |
| Negative control | ✅ caught and corrected a real false-negative mid-run (filename-based test search) — this IS the negative control firing, not a hypothetical |
| Real-data measurement | ✅ git log, settings.json, pytest --collect-only — all real repo state |
| Evidence marker | **[VERIFIED-REAL]** — "is alive" is directly measured, not inferred |

## Result Classification (End-of-run diamond scan)

- [x] 💎 **Diamond** — unexpected result, valuable outside the original scope: the
      run was framed as "revive a dead project" and the actual finding is "the
      premise was wrong, and here's the real gap instead." This is exactly the kind
      of result the Oracle-Aware Core's Stage 0/1 (Route + Autopsy) exists to catch
      — a lesser process would have either (a) forced a fake revival narrative onto
      an already-alive file, or (b) taken the "abandoned" framing at face value and
      wasted a tournament on a non-question.
- [ ] 🥇 Gold / 🥈 Silver / 🪨 Stone — n/a (Diamond selected)

**Diamond → recorded in `~/.claude/memory/cross_domain_insights.md` per protocol:**
see append below.

## Real, actionable finding surfaced (out of this run's own scope, flagged not fixed)

`hooks/session_save.py` — 999 lines, actively registered on `Stop`, most recently
touched by a SECURITY fix (path traversal / OOM / token exfil) — has only 2 test
functions covering it (`_get_last_commit_time()` return-value branches +
one stale-vs-fresh `main()` smoke test). Given the file's size, its `Stop`-event
blast radius (fires on every session end), and that its last substantive change was
security-motivated, this is a real coverage gap worth a human prioritization
decision — NOT something this run should silently fix as a "revival," per the
command's own non-goal ("no rebuild/refactor as the first move").
