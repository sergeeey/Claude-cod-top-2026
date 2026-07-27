# Substrate Gate (Step 2a, falsification-ladder.md)

**Date:** 2026-07-27
**Verdict:** BLOCKED-INFRASTRUCTURE

## What happened

Ran the positive control (`run_pilot_task.sh` against the real repo, task_id
`positive-control`). All 3 worktrees created cleanly. All 3 `claude -p` invocations
exited non-zero with identical stdout: `"Not logged in · Please run /login"`.

## Root cause (verified, not assumed)

```
$ echo $ANTHROPIC_API_KEY   -> empty
$ claude auth status
{"loggedIn": false, "authMethod": "none", "apiProvider": "firstParty"}
```

A `claude` CLI subprocess spawned from inside this session's own Bash tool does NOT
inherit this session's own authentication. This session itself is clearly authenticated
(it's running), but that credential is not exposed to a freshly-spawned child `claude`
process -- no `ANTHROPIC_API_KEY` env var is set, and OAuth/keychain access (which
`--bare` mode explicitly documents as never reading, and which apparently isn't
otherwise available to this sandboxed subprocess either) isn't reachable from here.

This is almost certainly a deliberate sandboxing boundary of the harness this session
runs inside, not a bug in `run_pilot_task.sh` or in `claude` itself.

## Why this is BLOCKED-INFRASTRUCTURE, not a claim result

Per `falsification-ladder.md` Step 2a: "test could not run" and "test ran and disproved
the claim" are different facts with different consequences. All three copies failing
identically, at the exact same auth step, before any task-specific work began, is a
substrate failure -- it says nothing about whether standard/minimal/vanilla config
catches more bugs. Recording this as "no-catch x3" would be exactly the anti-pattern
the Substrate Gate exists to prevent (`audit-verification-gate.md`'s own "BLOCKED /
UNTRUSTED-ENVIRONMENT verdict must never be recorded as evidence against the claim").

## What does NOT change

- `results.json` was NOT written to. No task or control result recorded.
- `null_results/INDEX.md` was NOT touched -- this is not a REJECT, there is nothing to
  reject yet.
- The estimand, claim, and scripts remain valid as designed -- the mechanism itself
  (worktree isolation, `--bare`/`--append-system-prompt` flag choices) was never actually
  exercised end-to-end, so it is also not yet confirmed working, only designed and
  unit-tested at the statistics layer (`score_pilot.py`'s 8 tests, which don't touch the
  `claude` CLI at all).

## Fix required before Step 3 (positive control) can proceed

`run_pilot_task.sh`'s `claude -p` invocations must run from an authenticated shell.
Options, cheapest first:

1. **Human runs the script directly** in their own terminal (already logged in there) --
   `bash experiments/20260727-config-effectiveness-opportunistic/scripts/run_pilot_task.sh <repo> <task_id> <prompt_file>`.
   No code change needed, just a different operator.
2. **Set `ANTHROPIC_API_KEY`** in the environment this session's Bash tool runs in, if an
   API key (not just OAuth session login) is available -- `--bare` mode explicitly
   supports this.
3. Investigate whether this session's harness exposes any credential-passthrough
   mechanism for spawned subprocesses (not investigated here -- (1) is cheaper and
   doesn't require understanding the harness's internals).

## Cleanup performed

Worktrees from this failed attempt (`~/pilot-worktrees-positive-control/`) removed --
nothing useful was produced in them (all 3 copies died before touching the target file),
no reason to keep them around. Re-run will recreate them once the auth blocker is fixed.
