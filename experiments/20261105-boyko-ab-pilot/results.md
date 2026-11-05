# Results: pilot, task T1 (one run per arm)

Runs started 2026-11-05T07:56:46Z, all four in parallel, exit code 0, no permission denials.
Pre-registration: commit 6eed5be (before any run). No deviations from the protocol.

## Acceptance (criteria 1-3 pre-registered; 4 reported separately)

| Arm | 1 exact answer | 2 no false findings | 3 repo unchanged | 4 tool used | success |
|---|---|---|---|---|---|
| A (plain Claude Code) | yes | yes | yes | yes | yes |
| B (full add-on) | yes | yes | yes | yes | yes |
| C′ (contract only) | yes | yes | yes | yes | yes |
| C (minimal Boyko) | yes | yes | yes | yes | yes |

Truth (script on the clone): empty list. All four answered "нет". The trap (four entries without
a directory that are not `type: directory`) caught no arm.

## Observed cost (one run each, not a statistical comparison)

| Arm | cost USD | turns | tool uses | wall time | cache-creation tokens | output tokens |
|---|---|---|---|---|---|---|
| A | 0.092 | 5 | 4 | 30 s | 15,653 | 1,246 |
| B | 0.410 | 5 | 4 | 34 s | 89,819 | 1,457 |
| C′ | 0.060 | 4 | 3 | 26 s | 9,231 | 1,035 |
| C | 0.086 | 5 | 4 | 27 s | 14,183 | 1,171 |

Cost and cache-creation tokens depend on prompt-cache state: arm A built 34,215 cache tokens in
an earlier smoke test and 15,653 here with the same flags. Treat the token and dollar figures as
indicative, not as a measured ratio.

## Other observations (not graded)

- Arm C′ added side claims outside the graded block that are wrong: 13 core and 149 extension
  directories, against 12 and 146 on the clone. The graded answer was correct.
- Arm C named the four non-directory entries explicitly as `file`, `external` and untyped and
  cited the independent `grep -c` cross-check; arm A mentioned them more briefly.
- Arm B's hooks did not block any tool call on this task.
- Arm B wrote to the owner's live hook logs while running (known threat, recorded in claim.md).

## What this does and does not show

- By the pre-registered rule, T1 **does not discriminate**: every arm succeeded. It supports
  no conclusion that Boyko helps or does not help.
- It shows the harness works: isolated arms run on the owner's subscription, the checker can
  fail, and one cell costs well under one dollar notional.
- The add-on (arm B) used more context and cost more on a task it did not need to change.
  One run each; `MDE=undetectable`.

## Next step (decided in advance)

A harder cell: T2 (code change with a trap) and T6 (vague goal), run the same four ways, with
repeats on any cell where arms disagree. Criteria must be committed before those runs.
