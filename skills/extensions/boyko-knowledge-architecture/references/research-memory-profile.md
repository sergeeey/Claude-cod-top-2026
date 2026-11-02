# Research-memory profile

Read this when the project holds experiments, hypotheses, claims, runs, null results or a
research registry. The ten axes still apply; this adds the questions that decide whether past
research is *usable* by the next agent, not merely stored.

## Why this exists

Captured is not the same as usable. [REPORTED, single audit by the skill's author] In one
multi-repo research setup a finished experiment sat untracked in a git worktree, and a fresh
agent asked to plan the same study found nothing. After it was committed, a second fresh agent
still missed it, because no index and no instruction told agents where to look; only a generated
catalog plus one pointer line in the agents' entry document made it findable. Each was a
different break in the chain and needed a different fix.

## The chain, and how to find the first break

```
CAPTURE -> CLOSE -> CATALOG -> DISCOVER -> RETRIEVE -> INTERPRET -> APPLY -> INVALIDATE -> PRESERVE
```

Walk it in order and name the first failure. Later stages that depend on it are not inferred
(`UNKNOWN`, not `PASS`). Axes that can be checked statically regardless (backup, privacy,
preservation) are still reported.

| Question | If no |
|---|---|
| Is the research object durably stored somewhere (committed, or intentionally kept in a private domain)? | `CAPTURE` fail |
| Does it have a readable outcome and, for unfinished work, the next test? | `CLOSE` fail |
| Does a catalog or index list it, across the places research actually lives (branches, worktrees, other repos)? | `CATALOG` fail |
| Do agents know the catalog exists (a pointer in their entry document or workflow)? | `DISCOVER` fail |
| Does a fresh agent given only the idea, without ID or path, find the right object? | `RETRIEVE` fail |
| Does it read the governing verdict (not a cached copy) and the conditions it applies to? | `INTERPRET` fail |
| Does it choose the right action? | `APPLY` fail |
| After inputs change (data, code, a refuted premise), is the dependent result flagged `RECHECK_REQUIRED`? | `INVALIDATE` fail |
| Is the whole set kept intact and recoverable (backup, restore evidence, private domain)? | `PRESERVE` fail |

Fix at the break. A vector database does not repair `CAPTURE`; a new schema does not repair
`DISCOVER`. Name the break in the report and propose the smallest change for that stage only.

## Where a research object stands

| State | Meaning | Defect? |
|---|---|---|
| `UNCOMMITTED_ORPHAN` | on disk only, in no commit | yes: one cleanup or crash from loss |
| `COMMITTED_LOCAL_BRANCH` | committed, but the branch exists only on this machine | at risk, not lost; also needs `CATALOG` coverage |
| `COMMITTED_PUBLISHED_BRANCH` | committed and pushed, not merged | not a capture defect |
| `MERGED_DEFAULT` | on the default branch | none |
| `LOCAL_PRIVATE_CAPTURED` | intentionally kept outside git (secrets, correspondence), with a known place and backup | not a defect; see the privacy boundary in `SKILL.md` |
| `LOCAL_PRIVATE_UNBACKED` | private or of unknown sensitivity, in no commit and with no known backup | yes, but a different one: add a private backup; do not commit it |
| `ARCHIVED` | parked with a revival condition | not a defect if the condition is recorded |

A committed local-branch object is captured. Calling it "uncaptured" sends the owner to commit
what is already committed, and hides the real problem, which is that nothing points to it.
`UNCOMMITTED_ORPHAN` applies only to material that is safe to publish; private material is never
an orphan to be committed.

## Catalog, discovery, freshness

A catalog is any derived mechanism that lists research objects across the relevant locations. It
is a view, never an authority: each row points at the artifact that owns the result.

- **Coverage.** Which research locations does it include? List them and say which are missing
  (local branches, linked worktrees, sibling repos, archive repos). Do not index everything by
  default; index the relevant scope and make the gaps visible.
- **Discoverability.** A catalog that exists but that no instruction mentions is invisible to a
  fresh agent. Test it: does the entry document (CLAUDE.md, AGENTS.md or the project's workflow)
  say where it is and when to consult it? Absence of the pointer is a `DISCOVER` failure even when
  the catalog is perfect.
- **Freshness.** Compare its generation time or rebuild marker with the newest research object it
  should contain. Manual rebuild is acceptable if staleness is visible and the command is written
  down; do not require automation.
- **Derived fields are cache.** A verdict or status copied into a catalog or registry may disagree
  with the governing decision file. Sample several; if they differ, the decision file governs, the
  copy is marked non-authoritative and points to it, and the report says "catalog inconsistency",
  not "the experiment contradicts itself". [REPORTED, single audit] Sampled registry verdicts
  differed from the decision files, and a catalog parser once copied a quoted verdict from
  further down the file instead of the real one.

## The functional test

Static inspection cannot tell you whether memory works. Run the use case in a fresh independent
context (a subagent, not the auditing session) with only an idea phrased in new words:

1. `FOUND`: did it locate the prior work?
2. `CORRECT_OBJECT`: the same experiment, not a sibling with a similar name?
3. `CORRECT_VERDICT`: the governing outcome, with the conditions it was obtained under?
4. `CORRECT_ACTION`: one of `REUSE`, `DON'T_REPEAT`, `CONTINUE_MISSING_TEST`, `REOPEN_WITH_DELTA`,
   `NEW_EXPERIMENT`.

Pre-register the expected answers from the decision files before running. Include a similar-but-
different case (the new condition must not be blocked) and a genuinely new idea (must not be
reported as already done). Similarity alone never blocks work: compare data, method, baseline and
code revision. With 5-6 cases report each case, not a rate.

## What not to add

No database, graph, embedding index or automatic rebuild until a measured break at `RETRIEVE` or
`CATALOG` shows a simple catalog and pointer are insufficient.
