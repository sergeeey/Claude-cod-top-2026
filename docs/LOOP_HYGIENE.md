# Loop Hygiene

## Problem

Agent loops that prompt without verifying create a new failure mode.
Not Validation Theater (fake tests) — **Loop Theater**:
recurring agents that appear to monitor, but surface only noise or nothing actionable.

Loop Theater symptoms:
- "Weekly check complete. No issues found." — every week, even when the repo is broken
- Finding listed with no suggested action
- Loop fires on every SessionStart regardless of whether anything changed
- Exception during check → silently skips the whole audit

## Loop Spec Template

Every loop must fill this spec before implementation:

```md
## Loop Spec: <loop-name>

| Field | Value |
|-------|-------|
| **Trigger** | When does this fire? (SessionStart / PostToolUse / cron) |
| **Interval** | How often? (weekly / daily / per-commit) |
| **Input source** | What data does it read? (files, registry, state, git log) |
| **Agent task** | What specifically does it check? (one clear question) |
| **Evidence required** | What constitutes a real finding? (not just "file exists") |
| **Allowed actions** | What can it do? (read, emit additionalContext, write state file) |
| **Forbidden actions** | What can it NOT do? (edit project files, git push, send) |
| **Output format** | How does it report? (additionalContext / stderr / silent) |
| **Stop condition** | When is it healthy? (silent = healthy — no output needed) |
| **Escalation** | What triggers human review? (zombie >30d, overdue pearl) |
| **Memory update** | Does it write anything? (state file path only) |
| **Autonomy budget** | See .claude/rules/autonomy-budget.md |
```

## Three Hygiene Rules

### Rule 1: Silent When Healthy

A loop that always emits is noise. A loop that emits **only on real findings**
trains the user to pay attention.

```python
message = _format_message(findings)
if message:
    emit_hook_result("SessionStart", message)
# if not findings → emit nothing, exit 0
```

Bad: `"Weekly check complete. No issues found."` → user stops reading after week 2.
Good: silence → user knows: if the loop surfaced something, it is real.

### Rule 2: Actionable or Silent

Every finding must include a suggested action:

```
→ Run /research-audit to close this zombie experiment
→ Open pearl_registry/INDEX.md and update next_check
→ Add decision.md with PROMOTE / REJECT / ARCHIVE verdict
```

A finding without a `→ action` line is noise dressed as signal.

### Rule 3: Fail-Open

Any exception → `sys.exit(0)`. Loops must never block the host event.

```python
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[loop-name] fatal: {e}", file=sys.stderr)
        sys.exit(0)  # never block SessionStart
```

Operational failure is not a user-facing error at startup.

## Loop Registry (this repo)

| Loop | File | Trigger | Interval | Status |
|------|------|---------|----------|--------|
| Research Health | `hooks/research_health_loop.py` | SessionStart | weekly | ✅ live (PR #137) |
| Project Focus | — | SessionStart | weekly | planned |
| Anti-fraud Signal | — | SessionStart | daily | planned |

## Anatomy of a Good Loop (from research_health_loop.py)

```
Timer check         → skip if <7 days since last run
Project root        → find_file_upward("CLAUDE.md") — respects any project
Focused audit       → zombies (open >30d) + pearls (overdue / unanchored)
Conditional emit    → None if healthy, formatted block if issues
State write         → ~/.claude/state/last_research_health.txt
Fail-open wrapper   → try/except → exit 0
```

Each step is independently testable. 26 tests cover all branches.
See `tests/test_research_health_loop.py`.

## Loop vs Hook (when to use which)

| | Hook (event-driven) | Loop (periodic) |
|---|---|---|
| Trigger | every tool call / file edit / commit | weekly / daily timer |
| Purpose | gate or validate a specific action | ambient health monitoring |
| Latency | must be fast (≤2s) | can be thorough (≤8s) |
| Output | block / allow / additionalContext | additionalContext only |
| Example | `pre_commit_guard.py` | `research_health_loop.py` |

Loops are hooks on a timer. All three hygiene rules apply to both.

## Anti-Patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| Emits every run regardless | noise → ignored | emit only when action needed |
| No stop condition defined | "healthy" undefined | `if not issues: return None` |
| Finding without `→ action` | user doesn't know what to do | append action line to every finding |
| Loop edits project files | data corruption risk | read-only + one state file only |
| No fail-open wrapper | blocks SessionStart on exception | wrap `main()` → `sys.exit(0)` |
| State file inside repo | leaks personal timing into git | state in `~/.claude/state/`, not repo |
| Re-checks without timer | fires on every session | weekly/daily timer via state file |

## Evidence Level for Loop Output

Loop findings carry `[INFERRED]` by default — the loop reads files and infers state.
A loop cannot produce `[VERIFIED-REAL]` without an external oracle (test run, CI output, API).

If a loop claims something is healthy, that is `[INFERRED]` from file contents.
Not `[VERIFIED]`. Mark accordingly when escalating to decisions.
