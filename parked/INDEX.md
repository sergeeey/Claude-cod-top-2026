# parked/INDEX.md — Archived Experiments Registry

_Entries here mean: this claim is valid but deprioritized. Revisit when conditions change._
_Before starting any new experiment, grep this file to avoid duplicating deferred work._

## How to add an entry

On ARCHIVE verdict in `decision.md`:
1. Copy filled `decision.md` to `parked/<id>-<slug>.md`
2. Add one row to this table

## Index

| ID | Date | Slug | Why parked | Revival trigger |
|----|------|------|-----------|----------------|
| example | 2026-01-01 | example-idea | deprioritized, team capacity | new dataset available / deadline passed |
| 20260728-hypothesis-arbiter-taxonomy-pilot | 2026-07-28 | hypothesis-arbiter-taxonomy-pilot | claim-level REJECT (n=1, MCID not met) but Rescue Review kept direction alive — untested on harder case | a messier/less-cued real case (see Relaxation Map), or a KILL-DESIGN-stage (not SPAWN-stage) re-test of the Pearl Registry's separation-quality observation |
| 20260727-config-effectiveness-opportunistic | 2026-07-29 | config-effectiveness-opportunistic | design/statistics layer untested and unfalsified; BLOCKED-INFRASTRUCTURE at the positive control (`claude -p` subprocess spawned from this session's Bash tool can't authenticate, no ANTHROPIC_API_KEY/OAuth passthrough — see `substrate_gate.md`); real ongoing per-task manual-operator cost to unblock as designed, user chose to park rather than accept that cost right now | ANTHROPIC_API_KEY becomes available to spawned subprocesses, OR user wants to personally run one high-stakes task through it, OR `profile-comparison-validation-theater`'s cheap blocker-check finds a shared workaround |
| 20260727-profile-comparison-validation-theater | 2026-07-29 | profile-comparison-validation-theater | DESIGN-only, never built; a cheap independent feasibility check (single `claude -p --bare` invocation) confirmed the SAME auth blocker as `config-effectiveness-opportunistic`, at 30 runs instead of 3 — user parked for consistency rather than accept a larger version of a cost already declined | ANTHROPIC_API_KEY becomes available to spawned subprocesses, OR user judges this claim (tests the repo's own headline README claim) worth the manual-run cost, OR an Agent-tool-simulated redesign is judged an acceptable ecological-validity tradeoff |
