# Git Worktree Isolation — Pattern

## Purpose
Enable agents to work in **isolated copies of the repository** without conflicts. Multiple agents can modify code simultaneously without stepping on each other's changes.

**Key benefit:** Parallel builds. builder + tester can run at the same time, each in their own worktree.

**Pattern source:** Everything Claude Code repo, implemented in Claude Code Agent tool.

---

## How It Works

### Basic Mechanism
When you invoke an Agent with `isolation: worktree`:

```markdown
---
name: builder
isolation: worktree
---
```

**Claude Code automatically:**
1. Creates temporary git worktree (`git worktree add <path> <branch>`)
2. Agent works in isolated directory
3. On completion:
   - If agent made changes → worktree path + branch returned for review
   - If no changes → worktree auto-deleted (cleanup)

**User flow:**
```
User: "Build feature X"
    ↓
Agent(builder, isolation="worktree")
    ↓
Claude Code: creates .claude/worktrees/builder-abc123/
    ↓
Builder works in isolation (Read, Edit, Write)
    ↓
Builder done → changes committed to branch builder-abc123
    ↓
Return: {path: ".claude/worktrees/builder-abc123", branch: "builder-abc123"}
    ↓
User reviews changes, merges or discards
```

---

## Currently Using Worktree Isolation

| Agent | Why | Benefit |
|-------|-----|---------|
| **builder** | Writes code according to spec | No main branch pollution, safe experimentation |
| **tester** | Writes tests + runs coverage | Parallel with builder, no test file conflicts |

**Team usage:** build-squad (builder + tester) runs both in parallel worktrees → 2x faster than sequential.

---

## When To Use Worktree Isolation

### ✅ Good Fit (use `isolation: worktree`)
- **builder** — writes implementation code
- **tester** — writes test files
- **refactor agent** — large-scale code changes
- **experiment agent** — trying risky approach (easy to discard)
- **migration agent** — schema/API migrations (test in isolation first)

### ❌ Not Needed (use default isolation)
- **reviewer** — read-only, no writes
- **explorer** — search/grep, no changes
- **architect** — planning, no code yet
- **skeptic** — red-team analysis, read-only

**Rule:** If agent writes code → consider worktree. If read-only → no worktree needed.

---

## Best Practices

### 1. Cleanup После Работы
Worktrees без changes auto-delete. Worktrees с changes остаются → review and merge OR manually delete.

**Check active worktrees:**
```bash
git worktree list
```

**Remove abandoned worktree:**
```bash
git worktree remove .claude/worktrees/builder-abc123
git branch -D builder-abc123  # optional: delete branch
```

**Periodic cleanup (weekly):**
```bash
# In project root
git worktree prune
```

### 2. Parallel Agent Teams
When spawning multiple agents in parallel:
```markdown
Agent(builder, isolation="worktree", description="Implement feature X")
Agent(tester, isolation="worktree", description="Write tests for X")
```

Both work simultaneously, no conflicts. Merge both branches after review.

### 3. Branch Naming Convention
Auto-generated branches: `<agent-name>-<random-id>`
- `builder-abc123`
- `tester-def456`
- `refactor-ghi789`

**Do NOT push** these branches to remote — they're temporary experiment branches.

### 4. Disk Space Management
Each worktree = full copy of working directory (not .git).

**Example:** 100 MB project → 10 worktrees = 1 GB disk usage.

**Mitigation:**
- Auto-cleanup (no changes → delete)
- Manual cleanup weekly (`git worktree prune`)
- Max 5 worktrees per project (configurable)

---

## Advanced: Custom Worktree Agents

Creating new agent with worktree isolation:

```markdown
---
name: migration-agent
description: Run database migrations in isolation
isolation: worktree
tools: Read, Edit, Write, Bash
model: sonnet
---

## Task
Apply database migration, run tests in isolation, then merge if successful.

## Workflow
1. Read migration script
2. Apply to test DB (in worktree)
3. Run integration tests
4. If pass → commit + return branch
5. If fail → rollback, worktree auto-deleted
```

**Benefit:** Failed migrations don't pollute main branch.

---

## Comparison: Worktree vs Branch vs Stash

| Approach | Pros | Cons | When to Use |
|----------|------|------|------------|
| **Worktree** | Full isolation, parallel work | Disk space (1x repo per worktree) | Parallel agents, large changes |
| **Branch** | Lightweight, no extra disk | Sequential only, switch cost | Single agent, small changes |
| **Stash** | Temporary save, zero disk | Limited to one stash active | Quick context switch |

**For agents:** Worktree > Branch because agents work in parallel.

---

## Real-World Example: Build-Squad

**Scenario:** User requests "Implement login endpoint + tests"

**Sequential (old way):**
```
builder: 10 min (implement endpoint)
    ↓
tester: 8 min (write tests)
    ↓
Total: 18 min
```

**Parallel (worktree way):**
```
builder (worktree A): 10 min
tester (worktree B): 8 min (starts immediately, no wait)
    ↓
Total: 10 min (limited by slowest agent)
```

**Speedup:** 1.8x (18 min → 10 min)

**Why safe:** No conflicts — builder writes `auth.py`, tester writes `test_auth.py`, different worktrees.

---

## Integration With Other Patterns

### Pattern 1: Agent Swarm + Worktree
Fan-out multiple builders to implement different modules in parallel:
```markdown
Agent(builder, isolation="worktree", prompt="Implement auth module")
Agent(builder, isolation="worktree", prompt="Implement payment module")
Agent(builder, isolation="worktree", prompt="Implement notification module")
```

All 3 work simultaneously. Merge all 3 branches after review.

### Pattern 2: Experiment + Fallback
Try risky approach in worktree:
```markdown
Agent(experiment, isolation="worktree", prompt="Try async refactor")
```

- If experiment succeeds → merge branch
- If fails → discard worktree (auto-deleted), no damage to main

### Pattern 3: Worktree + File-Level Locks
When multiple agents MUST edit same file sequentially:
```markdown
1. Agent A: worktree + file lock (auth.py)
2. Agent B: waits for lock release
3. Agent A done → merge → release lock
4. Agent B: worktree + acquire lock
```

**Rare case** — usually agents работают на разных файлах.

---

## Troubleshooting

### Problem: "worktree already exists"
**Cause:** Previous agent left worktree without cleanup.

**Fix:**
```bash
git worktree remove --force .claude/worktrees/<name>
```

### Problem: "branch already exists"
**Cause:** Previous worktree branch not deleted.

**Fix:**
```bash
git branch -D <agent-name>-<id>
```

### Problem: Disk space full
**Cause:** Too many worktrees accumulated.

**Fix:**
```bash
git worktree prune
du -sh .claude/worktrees/*  # check sizes
```

**Prevention:** Weekly cleanup in Monday routine.

---

## Metrics

Track worktree effectiveness:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Parallel speedup | 1.5-2x | Time(sequential) / Time(parallel) |
| Worktree cleanups | 0 manual/week | Count `git worktree prune` needs |
| Disk usage | <500 MB | `du -sh .claude/worktrees/` |
| Merge conflicts | <5% | Failed merges / Total worktree merges |

---

## Future Enhancements

### Enhancement 1: Auto-Merge Safe Changes
If builder + tester work on different files → auto-merge both branches (no conflicts possible).

### Enhancement 2: Worktree Pool
Pre-create 3 worktrees at session start → agents reuse them (faster startup).

### Enhancement 3: Remote Worktree Support
For distributed teams — worktrees синхронизируются через shared storage.

---

## References
- Git documentation: `man git-worktree`
- Everything Claude Code repo — original pattern source
- agents/builder.md — production usage example
- agents/tester.md — production usage example
- agents/teams/build-squad.md — parallel team usage

---

**Status:** ACTIVE — used in production (builder, tester agents)  
**Adoption:** 2/16 agents (12.5%), expandable to ~4-6 agents  
**Next review:** After adding worktree to refactor/migration agents  
**Last updated:** 2026-05-11
