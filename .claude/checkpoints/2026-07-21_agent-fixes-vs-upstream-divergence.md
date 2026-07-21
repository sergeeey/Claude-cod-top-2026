# Checkpoint — agent-doc fixes vs 63-commit upstream divergence

**Date:** 2026-07-21
**Branch:** main (local, 2 commits ahead of the merge-base)
**Task:** merge origin/main (which advanced 63 commits via PR #215-#218 while this session
worked locally) into local main, which carries 2 of this session's own commits, before pushing.

## State before this operation
- Local main HEAD: `6635fd6` (merge of `fix/agent-contract-self-inconsistencies`, itself on
  top of `7d99033`), both on top of merge-base `44ce62f`.
- `origin/main` HEAD: `dfe0ef5`, 63 commits ahead of the same merge-base `44ce62f`.
- Push of local main to origin was rejected (non-fast-forward) — this is why the merge is
  happening: origin advanced independently (other session/PC), not a conflict from this
  session's own actions.
- File-level overlap check (python, `git diff --name-only 44ce62f <ref>`): 3 of this session's
  6 changed files were ALSO touched upstream: `agents/reviewer.md`, `agents/scope-guard.md`,
  `agents/skill-suggester.md`. Real conflict risk, not yet resolved to line-level.
- My 2 local commits (both docs-only, agents/*.md): `7d99033` (5 agent contract fixes) and
  `6635fd6` (its --no-ff merge commit). Full local test suite was green before this point
  (2237 passed, 1 pre-existing unrelated failure) at `6635fd6`.

## Plan
1. `git merge origin/main` into local main (not rebase — preserves the existing merge-commit
   history style used throughout this session).
2. If conflicts appear in the 3 overlapping files: read both sides, reconcile by hand (keep
   both sets of real fixes where they don't contradict; if they fix the SAME issue, keep the
   more complete/correct version and say so).
3. Full test suite + the specific structural gates before pushing.
4. Push only after local tests are green.

## Rollback (if the merge goes wrong / needs abandoning)
```bash
git merge --abort              # if mid-conflict, before any commit
# OR, if already committed and needs full revert to this checkpoint:
git reset --hard 6635fd6
git push origin main --force-with-lease   # ONLY with explicit user confirmation — never silently
```
`6635fd6` is the last known-good, fully-tested local state before this merge began.
