# decision.md — 20260727-profile-comparison-validation-theater

## Verdict

- [x] ARCHIVE — valid but deprioritized → copy to `parked/<id>-<slug>.md` + update INDEX.md

## Result Classification (End-of-session diamond scan)

- [ ] 🥇 Gold
- [ ] 💎 Diamond
- [x] 🥈 **Silver** — same transferable finding as
      `parked/20260727-config-effectiveness-opportunistic.md`: a bare `claude -p`
      subprocess spawned from this session's own Bash tool cannot authenticate.
      Cheaply reconfirmed here on a fresh, minimal invocation
      (`echo "..." | claude -p --bare --no-session-persistence`), independent of
      the other experiment's own script — same exact error
      (`Not logged in · Please run /login`, exit 1). Two independent
      confirmations of the same substrate constraint, not one.
- [ ] 🪨 Stone

## Evidence Summary

| Check | Result |
|-------|--------|
| Positive control | Not built as a formal experiment artifact (no `controls.md` exists — this experiment never got past `estimand.md`). Instead, a minimal ad hoc feasibility check was run directly: `echo "Reply with exactly one word: OK" \| claude -p --bare --no-session-persistence` from this session's Bash tool. Result: `Not logged in · Please run /login`, exit code 1 — identical failure mode to `config-effectiveness-opportunistic`'s formal positive control. |
| Negative control | Not reached. |
| Stress tests | Not reached. |
| Skeptic verdict | SKIPPED — ARCHIVE, not PROMOTE/REJECT. |

## Rationale

This experiment was DESIGN-only (`estimand.md` written, no `claim.md`,
`controls.md`, or scripts ever built) when the question arose: given
`config-effectiveness-opportunistic` just hit a real, root-caused
infrastructure blocker (`claude -p` subprocesses spawned from this session
can't authenticate), would building this experiment's own 3-arm × 10-scenario
= 30-run design hit the identical wall?

Per this repo's Cheapest Differentiating Test Protocol, checked BEFORE
investing in the full scenario-and-script build: a single minimal `claude -p
--bare` invocation, independent of the other experiment's own script,
reproduced the exact same auth failure. This confirms the blocker is shared,
not incidental to how the other experiment's script happened to be written.

Building this experiment as designed would require the SAME per-run
manual-operator workaround as `config-effectiveness-opportunistic` — except
at 30 runs instead of 3, a materially larger version of the exact cost the
user already declined to accept for the smaller experiment. Asked directly
whether to park for consistency, build anyway with the user personally
running all 30, or redesign around the constraint (Agent-tool-simulated
vanilla/minimal instead of genuinely separate processes) — the user chose to
park, for consistency with the `config-effectiveness-opportunistic` decision.

This is ARCHIVE, not REJECT: the claim (standard profile improves
validation-theater detection) was never tested. Only the *design's*
feasibility under the current substrate constraint was checked, and found to
share the same real, already-documented blocker.

## Revival Condition

Same as `parked/20260727-config-effectiveness-opportunistic.md`:
1. An `ANTHROPIC_API_KEY` (or equivalent credential passthrough) becomes
   available to this session's Bash-spawned subprocesses.
2. The user wants to invest the manual-run time for this specific claim
   (arguably higher-value than the opportunistic one, since it directly
   tests this repo's own headline README claim about validation-theater
   detection — but that value judgment is the user's to make, not assumed
   here).
3. A redesign avoiding genuinely-separate `claude -p` processes (e.g.
   Agent-tool-simulated arms) is judged an acceptable ecological-validity
   tradeoff in a future session — not decided here, left open.
