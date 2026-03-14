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
2. Complex bug → patterns.md (auto-prompted by pattern_extractor.py for fix: commits)
3. Architectural decision → decisions.md

## Pattern tags in patterns.md
- `[REPEAT]` — proven approach, use again in similar situations
- `[AVOID]` — mistake or anti-pattern, do not repeat
- `[×N]` — occurrence counter. [×3] = seen 3 times, treat as hard rule
- When a known pattern recurs: increment counter [×N] → [×N+1], add "- Recurrence [date]: ..."

## Feedback memory
When the user corrects your approach ("no, don't do that", "instead do X"):
1. Save immediately to auto memory as type `feedback`
2. Include WHY the user gave this feedback
3. Include WHEN to apply it (context/trigger)
4. Check existing feedback memories first — update instead of duplicating

## Context Overflow (70% threshold)
1. Update activeContext.md
2. /clear
3. Load context → continue

## Checkpoints — before risky operations
- git rebase/merge into main, large-scale refactoring
- DB migration, architecture change, release
- checkpoint_guard.py will remind you automatically
