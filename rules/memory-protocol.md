# Memory Protocol

## Project memory (in each project)
```
<project>/.claude/memory/activeContext.md  — what we are doing now
<project>/.claude/memory/decisions.md      — architectural decisions
<project>/.claude/checkpoints/             — save points
```

## Global memory (~/.claude/memory/)
```
user_profile.md  — WHO the user is
patterns.md      — WHAT works
learning_log.md  — WHAT was learned
goals.md         — WHERE we are heading
decisions.md     — WHY decisions were made
```

## After each git commit
1. Update activeContext.md
2. Complex bug → patterns.md
3. Architectural decision → decisions.md

## Context Overflow (70% threshold)
1. Update activeContext.md
2. /clear
3. Load context → continue

## Checkpoints — before risky operations
- git rebase/merge into main, large-scale refactoring
- DB migration, architecture change, release
- checkpoint_guard.py will remind you automatically
