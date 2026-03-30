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

## Coordination Protocol
1. Both receive the architect's spec
2. Builder implements in worktree-builder branch
3. Tester writes tests in worktree-tester branch
4. Lead merges: implementation + tests into feature branch
5. Run final pytest to verify integration

## Token Budget
~2000-3000 tokens total (builder gets more turns)
