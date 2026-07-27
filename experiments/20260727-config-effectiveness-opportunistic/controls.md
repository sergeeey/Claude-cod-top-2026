# Controls

**Run once, before accumulating any real pilot task**, to validate the harness itself
(the 3-copy mechanism + the catch/no-catch grading) is sound. Failing either control
means fix the harness, not the config comparison — a harness bug would corrupt every
subsequent opportunistic task.

## Mechanism (verified, not guessed)

Confirmed via `claude --help` (this session, before writing this file) rather than
assumed from memory:

| Copy | Invocation | What it approximates |
|---|---|---|
| **A — vanilla** | `claude -p --bare "<prompt>"` | `--bare` skips CLAUDE.md auto-discovery, hooks, plugin sync, auto-memory, background prefetches (per `claude --help`) — no project/user config reaches the model |
| **B — minimal** | `claude -p --bare --append-system-prompt "$(cat minimal_doc.md)" "<prompt>"` | `--bare` baseline + exactly one injected doc, nothing else |
| **C — standard** | `claude -p "<prompt>"` (run from the real checkout, no flags) | Full current `CLAUDE.md` + `rules/` + `skills/` + `hooks/` as normally discovered |

All three run via `-p/--print` (non-interactive, single-shot) for reproducibility — no
follow-up turns, no human steering mid-task, so the comparison is fair (C doesn't get
extra interactive correction that A/B don't).

Each copy runs in its own `git worktree` (isolated filesystem) at the **same commit**, so
none can see another's edits and there's no codebase-drift confound between copies.

## Positive Control

**Purpose:** confirm the grading criterion actually fires when there IS something to
catch — if even a config-irrelevant, obvious bug goes uncaught by all 3 copies, the
harness (prompt wording, task framing) is broken, not the config comparison.

**Task:** a small file with a deliberately planted, unambiguous bug (e.g., an off-by-one
in a loop bound, or a function that returns the wrong sign) plus a prompt: "Review
`<file>` for correctness bugs before we ship it. List anything you find."

**Pre-registered catch criterion (write before running):** output explicitly names the
planted bug's location and describes the actual defect (not just "looks fine" or a vague
"consider adding tests").

**Expected result:** ALL THREE copies catch it (vanilla included) — a bug this
unambiguous shouldn't need elaborate config to find. If vanilla (A) also catches it,
that's fine and expected; the positive control is about the HARNESS working, not about
differentiating configs.

**Failure mode this catches:** if even standard (C) misses this, stop — something is
wrong with the prompt/task/file, not with the config comparison. Do not proceed to real
tasks until this passes.

## Negative Control

**Purpose:** confirm the grading criterion doesn't fire on nothing — if a clean,
correct file gets "caught" as buggy by any copy, the criterion is too loose (or the copy
is hallucinating problems), which would corrupt every real-task catch/no-catch call in
the same direction (inflated catch-rate for whichever copy over-triggers).

**Task:** a small, genuinely correct file (same style/domain as the positive control, so
it's not trivially distinguishable by file size or topic alone) plus the identical
prompt: "Review `<file>` for correctness bugs before we ship it. List anything you find."

**Pre-registered catch criterion:** any output that asserts a real correctness defect
exists (not stylistic nitpicks, not "consider adding a test," not hedged "might want to
double check X" without asserting X is actually wrong) counts as a FALSE catch.

**Expected result:** none of the three copies falsely catch anything.

**Failure mode this catches:** if standard (C) over-triggers on the negative control
more than vanilla (A) does, that's a real and important finding in its own right (more
elaborate config = more hallucinated findings, not just more real ones) — log it in
`caveats.md`, do not silently exclude it, and consider whether the primary catch-rate
comparison needs a false-positive-rate companion metric before trusting it.

## Recording

Both controls' results go in `results.json` under a `"controls"` key, separate from the
opportunistic task population (`"tasks"` key) — controls validate the mechanism, they are
NOT part of the accumulated population used for the primary risk-difference estimate.
