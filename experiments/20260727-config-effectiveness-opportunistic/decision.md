# decision.md — 20260727-config-effectiveness-opportunistic

## Verdict

- [x] ARCHIVE — valid but deprioritized → copy to `parked/<id>-<slug>.md` + update INDEX.md

## Result Classification (End-of-session diamond scan)

- [ ] 🥇 Gold
- [ ] 💎 Diamond
- [x] 🥈 **Silver** — the Substrate Gate finding itself (`substrate_gate.md`) is a
      transferable technique: a `claude` CLI subprocess spawned from inside this
      session's own Bash tool does not inherit this session's authentication, no
      `ANTHROPIC_API_KEY`, no OAuth/keychain passthrough. Any future experiment
      design in this repo that needs a separately-configured `claude -p` process
      (different flags, different loaded config) will hit the identical wall —
      this is now a documented, reusable fact about this session's sandbox
      boundary, not something each future design needs to rediscover.
- [ ] 🪨 Stone

## Evidence Summary

| Check | Result |
|-------|--------|
| Positive control | BLOCKED-INFRASTRUCTURE — all 3 copies (`A_vanilla`/`B_minimal`/`C_standard`) exited identically on `"Not logged in · Please run /login"`, before any task-specific work began. Per `falsification-ladder.md` Step 2a, this is explicitly NOT a claim result. |
| Negative control | Not reached — blocked upstream of this step. |
| Stress tests | Not reached. |
| Skeptic verdict | SKIPPED — not a PROMOTE/REJECT verdict, ARCHIVE governed by parked/ protocol instead. |

## Rationale

The experiment's design and statistics layer (`estimand.md`, `claim.md`,
`score_pilot.py`'s paired-permutation estimator, 8 passing unit tests) remain
sound and untouched by this verdict — nothing about the CLAIM was tested,
let alone falsified. What blocks it is a real, root-caused infrastructure
constraint documented in `substrate_gate.md`: `claude -p` subprocesses spawned
from this session's own Bash tool cannot authenticate. The substrate gate's
own cheapest fix ("human runs the script directly in their own terminal") is
real and would unblock this experiment today — but it means every future
opportunistically-accumulated real task requires the user to personally run
one command in their own authenticated terminal, not something the assistant
can do autonomously going forward.

Given that ongoing per-task manual cost, and asked directly whether to (a)
run the mechanism as designed with the user operating the script per task,
(b) redesign around the constraint (simulate vanilla/minimal in-session via
the Agent tool instead of genuinely separate processes — a real ecological-
validity tradeoff), or (c) park it — the user chose to park it. This is an
ARCHIVE, not a REJECT: the claim was never tested, the design is not
falsified, only deprioritized under the real cost this specific substrate
constraint imposes.

## Revival Condition

Any of:
1. An `ANTHROPIC_API_KEY` (or equivalent credential passthrough) becomes
   available to this session's Bash-spawned subprocesses — removes the
   manual-operator requirement entirely, same design as-is.
2. The user decides the per-task manual-run cost is worth it for a specific
   high-stakes real task and wants to run `run_pilot_task.sh` themselves for
   that one case (doesn't require reviving the whole opportunistic-
   accumulation design, just one operator-run instance).
3. `profile-comparison-validation-theater`'s cheap positive-control check
   (in progress, see that experiment's own decision) either confirms the same
   auth blocker (making a shared fix worth building once for both) or finds a
   workaround this experiment could also reuse.
