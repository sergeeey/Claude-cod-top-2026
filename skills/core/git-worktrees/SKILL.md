---
name: git-worktrees
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-13]
  USE when needing isolated workspace for experiments or parallel development.
  Triggers: worktree, experiment, parallel branch, isolated copy,
  isolated branch, parallel work.
---

# Skill: Git Worktrees

## When to Load
- Experiment with uncertain outcome (may require rollback)
- Parallel work on 2+ tasks
- Large refactor while needing to keep a working version

## Principle
Worktree = isolated working copy. Cheaper than stash/switch, safer than working in one tree.

---

## Decision Matrix: branch vs worktree

| Situation | Branch | Worktree | Why |
|-----------|--------|----------|-----|
| Bug fix in 1-2 files | v | | Worktree overhead not justified |
| Experiment (may not be needed) | | v | Clean rollback = delete the folder |
| Parallel work (2 tasks) | | v | No stash/switch needed |
| Large refactor 5+ files | | v | Main branch stays working |
| Regular feature 3-5 files | v | | Worktree = overkill |
| CI/CD check on another branch | | v | Does not interrupt current work |

**Rule:** worktree = recommendation, not mandate. Regular branch covers 80% of cases.

---

## Workflow

### 1. Create worktree
```bash
# EnterWorktree creates a worktree automatically (Claude Code built-in)
# Or manually:
git worktree add ../project-experiment feature/experiment
cd ../project-experiment
```

### 2. Work in worktree
- Worktree = full working copy with a separate HEAD
- Can work in parallel in main tree and worktree
- Commits in the worktree go to their own branch

### 3. Merge result
```bash
# From the main tree:
git merge feature/experiment
# Or cherry-pick specific commits:
git cherry-pick <commit-hash>
```

### 4. Cleanup
```bash
git worktree remove ../project-experiment
# Or if branch is no longer needed:
git worktree remove ../project-experiment
git branch -d feature/experiment
```

---

## Claude Code Integration

Claude Code has a built-in `EnterWorktree` tool:
- Automatically creates a worktree in a sibling directory
- Switches context to the new tree
- After completion — merge and cleanup

**When to use EnterWorktree:**
1. Plan contains 5+ steps with high risk of cascading errors
2. User asks to "try it, but keep rollback possible"
3. Parallel task while current one is unfinished

---

## Anti-patterns

| Don't do | Why |
|----------|-----|
| Worktree for every minor edit | Overhead > benefit |
| Forgetting cleanup after merge | Dead directories accumulate |
| Working in worktree without a branch | Detached HEAD = lost commits |
| Multiple worktrees on one branch | Git won't allow it (and rightly so) |
