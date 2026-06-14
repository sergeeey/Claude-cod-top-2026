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
patterns.md      — WHAT works ([REPEAT]/[AVOID]/[×N] register)
learning_log.md  — WHAT was learned (concepts + tip-tracker)
goals.md         — WHERE we are heading
decisions.md     — WHY decisions were made
```

### Canonical paths — IMPORTANT for discoverability

Each global file MAY live at one of two locations. This dual-path setup
exists for historical reasons (auto-extracted files lived in `_auto/`,
human-edited files at root). When SEARCHING for a file, always check
BOTH paths before declaring missing.

| File | Canonical (preferred for new edits) | Legacy (auto-generated location) |
|------|-------------------------------------|----------------------------------|
| patterns.md | `~/.claude/memory/patterns.md` | `~/.claude/memory/_auto/patterns.md` |
| decisions.md | `~/.claude/memory/decisions.md` | `~/.claude/memory/_auto/decisions.md` |
| playbook.md | `~/.claude/memory/playbook.md` | `~/.claude/memory/_auto/playbook.md` |
| learning_log.md | `~/.claude/memory/learning_log.md` | `~/.claude/memory/_auto/learning_log.md` |
| wiki/ (entries) | `~/.claude/memory/_auto/wiki/` | n/a (auto-only) |
| raw/ (inbox) | `~/.claude/memory/raw/` | n/a |

**Resolution rule** (implemented by `knowledge_librarian.py:_resolve_memory_file`):
check canonical first, fall back to legacy `_auto/`. Either path is valid.
Prevents the "audit hallucination" failure mode where an LLM looks in one
location, gets `not found`, and reports the file as missing — when it
exists at the other path. Observed historically in this repo with patterns.md.

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
