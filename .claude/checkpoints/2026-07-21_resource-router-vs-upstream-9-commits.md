# Checkpoint — resource_router.py merge vs 9-commit upstream divergence

**Date:** 2026-07-21
**Branch:** main (local, 2 commits ahead of merge-base)
**Task:** merge origin/main (advanced 9 commits, `e66ce5c..f201ae4`, while this session worked
locally) into local main before pushing `resource_router.py`.

## State before this operation
- Local main HEAD: `b8d9788` (merge of `feat/resource-router-advisory-tier-classifier`), on
  top of merge-base `e66ce5c`.
- `origin/main` HEAD: `f201ae4`, 9 commits ahead of the same merge-base.
- Push rejected (non-fast-forward) -- origin advanced independently again.
- File-overlap check (`git diff --name-only e66ce5c <ref>`): 7 of my 9 changed files also
  touched upstream: `.claude-plugin/marketplace.json`, `.claude-plugin/plugin.json`,
  `README.md`, `docs/architecture.md`, `hooks/registry.yaml`, `hooks/settings.json`,
  `marketplace.json` -- mostly doc-count metadata (expected, both sides likely added
  hooks/tests independently), but `hooks/settings.json`/`registry.yaml` could carry real
  structural conflicts if upstream also added hooks.
- Local full suite was green before this point (2386 passed, ruff/mypy clean,
  check_architecture --check exit 0) at `b8d9788`.

## Plan
1. `git merge origin/main` into local main.
2. If conflicts: read both sides, reconcile (keep both sets of real changes where they
   don't contradict; for metadata counts, resync via `scripts/sync_doc_counts.py` after).
3. IMPORTANT lesson from the 63-commit reconciliation earlier this session: do NOT
   `git checkout -b` while a merge is in progress (MERGE_HEAD is not preserved across a
   branch switch, silently producing a 1-parent commit instead of a proper 2-parent merge).
   If pre_commit_guard blocks a bare `git commit` on main, branch BEFORE starting the next
   merge attempt, not mid-merge -- or resolve+stage, then attempt commit, and if blocked,
   `git branch <name> HEAD` (a plain ref creation, not checkout) followed by resetting main
   only via the already-proven-safe `branch -f` technique, never `git checkout -b` mid-merge.
4. Full test suite + ruff + mypy + check_architecture before pushing.
5. Push only after local tests are green.

## Rollback (if the merge goes wrong / needs abandoning)
```bash
git merge --abort              # if mid-conflict, before any commit
# OR, if already committed and needs full revert to this checkpoint:
git reset --hard b8d9788
git push origin main --force-with-lease   # ONLY with explicit user confirmation
```
`b8d9788` is the last known-good, fully-tested local state before this merge began.
