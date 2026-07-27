---
name: build-squad
description: Parallel implementation — code + tests in isolated worktrees. Build and test simultaneously.
lead: builder
teammates:
  - tester
strategy: parallel-worktree
---

## Purpose
Write implementation code and tests simultaneously in separate git worktrees.
Lead (builder) implements the feature in an isolated branch.
Teammate (tester) writes tests based on the spec in a separate branch.

## When to Use
- New features with clear specs (both implementation and tests can start from spec)
- Refactoring with existing test coverage (tester updates tests while builder refactors)

## Predecessor (run before this team, not a teammate)

Step 1 below says "Both receive the architect's spec" but nothing in this repo
actually invoked `architect` to produce one — the same class of gap as
`security-guard`'s missing wiring (coherence audit, 2026-07-17). `architect`'s
own `whenToUse` ("designing a new module... or before implementing anything
spanning 3+ files") already matches this team's own scope, and lines up with
`hooks/plan_mode_guard.py`'s 3-file milestone trigger. Run it first when there
isn't already a clear spec to hand to builder/tester:

`Agent(architect, prompt="Design: <feature description>. Output: file tree,
pattern choices, explicit justification.")`

Skip this step for small/trivial changes where the spec is already obvious —
architect is a predecessor here specifically because it doesn't fit as a
`teammates:` entry (it must finish before builder/tester start, not run
alongside them).

## Coordination Protocol
1. Both receive the architect's spec (see Predecessor above)
2. Builder implements in worktree-builder branch
3. Tester writes tests in worktree-tester branch
4. If builder introduces a new dependency/package/URL, run `verifier` on it
   before merging — its `whenToUse` covers exactly this ("installing
   unfamiliar packages... recalled from memory rather than read from a file")
5. Lead merges: implementation + tests into feature branch
6. Run final pytest to verify integration

## Token Budget
~2000-3000 tokens total (builder gets more turns), +~800-1200 if the architect
predecessor step runs, +~300-500 if verifier checks a new dependency
