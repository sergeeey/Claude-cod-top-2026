# Cell 2 results: T2 and T6 (one run per arm per task)

Runs started 2026-11-05 08:04:54Z (T2) and 08:07:11Z (T6), all exit 0, no permission denials.
Pre-registration: commit 046bc71 (before any cell-2 run).

## T2 (code change with a hidden test): all arms pass

| Arm | hidden tests | existing tests | no weakening | scope | success | cost USD | turns | tool uses | cache-creation tokens |
|---|---|---|---|---|---|---|---|---|---|
| A | 6/6 | pass | yes | yes | yes | 0.092 | 9 | 8 | 11,002 |
| B | 6/6 | pass | yes | yes | yes | 0.531 | 10 | 9 | 107,097 |
| C′ | 6/6 | pass | yes | yes | yes | 0.087 | 7 | 6 | 10,594 |
| C | 6/6 | pass | yes | yes | yes | 0.094 | 8 | 7 | 11,356 |

The trap (reading the variable only at import time) caught no arm. Arm B also added 39 lines of
tests for the new behaviour; the other arms changed only `hooks/lib/state.py`.

## T6 (vague goal): registered result, then a recorded flaw in the checker

Registered mechanical result (criterion 3 = zero broken references): **all four arms FAIL**.

| Arm | scope | draft ≥10 lines | broken refs (registered checker) | success (registered) | cost USD | turns | tool uses | cache-creation tokens |
|---|---|---|---|---|---|---|---|---|
| A | yes | 122 | 3 | no | 0.125 | 5 | 4 | 18,864 |
| B | yes | 117 | 1 | no | 0.469 | 6 | 4 | 99,566 |
| C′ | yes | 102 | 9 | no | 0.150 | 8 | 7 | 22,218 |
| C | yes | 104 | 5 | no | 0.147 | 7 | 6 | 21,103 |

**This failure is a defect of the checker, not a result about the arms.** `check_t6.py` resolved
every bare file name in backticks (`integrity.md`, `registry.yaml`, `hooks-guide.md`) from the
repository root, but in the drafts these names appear next to a directory in a table or as a
relative link inside `docs/`. The ten control cases did not include bare names, so the defect was
not caught before the runs. The registered result stands as recorded, and it is not evidence
about the arms.

## Deviation (post-hoc, exploratory, not pre-registered)

`posthoc_t6.py` resolved a reference if it exists from the root, or from `docs/`, or (for a bare
name) anywhere in the clone, and also included markdown link targets. **Unresolved references:
0 in all four drafts.** With this rule all four arms pass the mechanical T6 criteria, so T6 does
not discriminate on accuracy either. The checker should be fixed and validated with bare-name
controls before it is reused.

## T6 secondary: contract stated before the first write (blind rubric, 0 to 3)

Grader: a separate agent, no tools, arm labels replaced by X1..X4 in a seeded random order.

| Arm | label | goal in own words | checkable done criterion | stated limits | score |
|---|---|---|---|---|---|
| A | X4 | no | no | no | 0 |
| B | X1 | no | no | no | 0 |
| C′ | X3 | no | no | no | 0 |
| C | X2 | no | yes | no | 1 |

Only arm C wrote a done criterion before acting ("файл есть, а команды и пути в нём сверены с
репозиторием"). Three of four arms wrote one sentence of "I will first look at the repository".
n = 1 per arm, a score of 1 against 0; this is an observation, not an effect.

## Other observations

- Live log `hook_triggers.jsonl` had 17,123 rows before cell 2 and 17,123 after: arm B wrote
  nothing to it in this cell (the logging hooks are no longer registered in the live setup).
- Across T1, T2 and T6 arm B cost 4.5x to 5.8x arm A at the same registered success; arms C′ and
  C cost about the same as A (0.87x to 1.2x). One run each; prompt-cache state moves these
  numbers, so they are indicative.

## What the three cells show

- On T1, T2 and T6 (n = 1 each, easy for this model) no arm failed on a correct criterion, so
  none of the tasks discriminates arms on success.
- The full add-on cost several times more per task and did not change the outcome.
- A minimal contract or method is cheap; its only visible effect is a slightly more explicit
  done criterion in T6 (one arm). That is a pointer for a better experiment, not a result.
- Whether Boyko helps on harder or longer tasks is **not** answered.

## What would make the next cell informative

1. Harder tasks, where plain Claude Code fails at least sometimes (for example multi-file
   changes, tasks with misleading instructions, a task with an unstated requirement).
2. Repeats (at least three runs per arm per task) so run-to-run variation is visible.
3. A T6 checker validated on bare-name references before use.
4. Real tasks from the owner's list instead of constructed ones.
