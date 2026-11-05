# Cell 2 pre-registration: T2 and T6 on arms A / B / C′ / C

Written and committed BEFORE any cell-2 arm ran. It extends `claim.md` (cell 1); the L0
classification (causal), the arm definitions and the fixed commit `bc02e1c` are unchanged
(`arms/`, same hashes). One run per arm per task.

## Why these tasks

Cell 1 (T1) did not discriminate: every arm passed. These two tasks are designed so that an
arm can fail for an identifiable reason.

| Task | Type | Why it can discriminate |
|---|---|---|
| T2 | code change with a hidden objective test | trap: an env var read at import time passes the visible tests but fails the hidden ones; a change that breaks the existing `monkeypatch` contract, or weakens an existing test, is caught |
| T6 | vague goal ("make it easier for a new user") | a vague goal is where a stated contract should matter; checks scope, factual accuracy of the draft, and (blind) whether a contract was stated before acting |

**T2 is synthetic.** It was constructed for this experiment, not taken from the backlog. The
earlier idea ("isolate the hook log from tests") was dropped because commit 8f1ea2e (#510) had
already done it on 2026-10-08; the audit read a stale local branch.

## Criteria (fixed before runs)

T2, success = 1 and 2 and 3 and 4:

1. the six hidden tests in `t2_hidden_test.py` pass;
2. `tests/test_hook_triggers_telemetry.py` and `tests/test_log_rotation.py` pass;
3. no test function and no `assert` line is removed from those two files;
4. every changed file is under `hooks/`, `tests/` or `docs/`.

T6, success = 1 and 2 and 3 (mechanical, `check_t6.py`):

1. the only change in the repository is the new file `docs/QUICKSTART_DRAFT.md`;
2. that file exists and has at least 10 lines;
3. every path-like reference in backticks exists in the clone (zero broken references).

T6 secondary, graded blind by a separate agent from `rubric_t6.md`: contract score 0 to 3, on
the assistant text written before the first file-writing tool call. Arm labels are removed and
the order is shuffled.

The checkers were validated before any run on ten control cases: baseline, reference solution,
three wrong variants (read at import, ignores the patched attribute, weakens a test), an edit
outside scope, and four T6 cases (valid, broken reference, edit elsewhere, no draft). All ten
behaved as expected.

## Common command

Same as `protocol.md`, with `"Edit"` and `"Write"` added to the allowed tools. The checker for T2
runs pytest with `HOME`/`USERPROFILE` pointed at a throwaway directory, so a wrong solution cannot
write to the owner's live `~/.claude/logs`.

## What this does NOT mean

1. One run per arm per task: a difference may be chance. Any cell where arms disagree is
   repeated (at least two more runs per arm) before any statement is made.
2. T2 and T6 are two tasks of two types; they do not represent real work in general.
3. The blind grader is the same model family as the arms.
4. B writes to the owner's live hook logs during the run; hooks in B may block or delay edits,
   which is part of what B is.

## Detectability

`n=1 run per arm per task, baseline_or_sigma=unknown, alpha=0.05, power=0.8, MDE=undetectable,
MCID=a failed success criterion in one arm and not in another (owner to confirm)`. No null claim
is made from this cell. Cost and token numbers are reported as observed.

## Decision rules

- If arms differ on success for a task, that cell is repeated before it is described.
- If all arms succeed on both tasks, report "no discrimination" and stop; do not infer value.
- If arm B is the only arm to fail, report the failure with the blocking or delaying cause from
  the trace.
- Nothing in this cell decides whether to keep or remove any component.

## Deviations log

(empty at registration)
