# Frozen-corpus re-run after PR D (experiment index integrity invariant)

## The finding was bigger than PR #446 reported

PR #446's P4 counted only ids that appeared in *cross-experiment relationships*, so its
"2 unrecorded" was a lower bound on the drift, not the orphan count. Measuring every
directory against every index row, in both directions:

| Direction | Count |
|---|---|
| **orphan** — directory on disk, no `INDEX.md` row | **5** |
| **stale** — `INDEX.md` row, no directory | 0 |
| **duplicate** rows | 0 |
| non-standard id format | 1 |

The five orphans:

| Experiment | has `decision.md` | note |
|---|---|---|
| `2026-07-16-route-trace-sci-hypothesis` | no | trace artifact only; also the one non-standard id (`YYYY-MM-DD-` not `YYYYMMDD-`) |
| `20260728-hypothesis-arbiter-taxonomy-pilot` | yes | the two-level-verdict record from PR C |
| `20260903-memory-retrieval-repair` | yes | a PROMOTE |
| `20260912-research-evidence-loop-minimal-extension` | yes | **Cycle 1's own experiment** |
| `20260912-cycle2-retrospective-replay` | yes | **Cycle 2's own experiment** |

Both cycles working on experiment tracking failed to register themselves. That is the
sharpest available statement of why the invariant, not the rows, is the deliverable.

## What shipped

`check_index_integrity()` in `scripts/check_experiment_graph.py`, detecting orphan /
stale / duplicate in both directions, plus the five missing rows so the repository
actually satisfies the invariant it now enforces.

Deliberately **the same invariant** CI's existing "Registry ↔ disk consistency gate"
already enforces for skills (added after 7 skills landed on disk with no registry
entries) — extended to experiments, not invented. Implemented in Python rather than the
bash+`comm` shape that gate uses, because `INDEX.md` is a markdown *table* and this
repository has already been bitten once by a CI step computing a doc count with a flat
`ls`.

## The second defect, found while wiring it

`scripts/check_experiment_graph.py` shipped in PR #444 and **was never wired into CI**.
It ran only when somebody invoked it by hand, so it automatically protected nothing —
the same "mechanism exists but does not fire" class the whole cycle keeps surfacing,
committed by the cycle that was measuring it. PR D adds the CI step, which gates both
the new index invariant and Cycle 1's original graph/holdout checks.

| | before PR D | after PR D |
|---|---|---|
| index invariant | did not exist | enforced |
| orphan experiments | 5 | **0** |
| `check_experiment_graph.py` runs in CI | **no** | yes |

## Mutation testing

Five mutations, all caught:

| Mutation | Caught |
|---|---|
| drop orphan detection | yes |
| drop stale detection | yes |
| drop duplicate detection | yes |
| treat a missing `INDEX.md` as "nothing to check" | yes |
| stop excluding `_template` from the on-disk set | yes |

Note on the first: `test_real_repository_satisfies_the_invariant` does **not** fail when
orphan detection is removed — correctly, because the real repository now has zero
orphans. That test is a regression guard for future drift, not a detector of today's
state; the synthetic-fixture test is what pins the detection logic itself. Recorded
because the distinction is easy to misread as a weak test.
