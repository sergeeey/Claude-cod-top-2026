# Hooks Guide

## What are Hooks

Hooks are scripts that run automatically at specific moments during Claude Code operation.
Unlike CLAUDE.md instructions (which the model can ignore), hooks execute 100% of the time.

## 14 Available Events

| Event | When | Our hooks |
|-------|------|-----------|
| SessionStart | Start/resume/clear/compact | `session_start.py` |
| SessionEnd | Session end | — |
| UserPromptSubmit | Before prompt submission | — |
| **PreToolUse** | Before tool call | `pre_commit_guard.py`, `redact.py`, `read_before_edit.py`, `input_guard.py`, `mcp_circuit_breaker.py`, `mcp_locality_guard.py` |
| PermissionRequest | Permission request | — |
| **PostToolUse** | After tool call | `post_format.py`, `plan_mode_guard.py`, `memory_guard.py`, `checkpoint_guard.py`, `post_commit_memory.py`, `pattern_extractor.py`, `drift_guard.py`, `mcp_circuit_breaker_post.py` |
| PostToolUseFailure | After tool error | — |
| **PreCompact** | Before context compaction | `pre_compact.py` |
| Stop | Agent stop | `session_save.py` |
| SubagentStart | Subagent start | — |
| SubagentStop | Subagent stop | — |
| Notification | Notification | — |
| Setup | First run | — |
| InstructionsLoaded | Instructions loaded | — |

## Description of Each Hook

### session_start.py (SessionStart)
Loads the current project's activeContext.md and outputs it into context.
Allows Claude to "remember" where it left off.

### pre_compact.py (PreCompact)
Before context compaction, saves the current state to activeContext.md.
Protects against losing important information during automatic compaction.

### pre_commit_guard.py (PreToolUse → Bash)
Scans Bash commands for dangerous patterns:
- `git push --force`, `git reset --hard`
- `DROP TABLE`, `TRUNCATE TABLE`
- `rm -rf /`, `chmod 777`
Blocks execution (exit code 2) with a warning.

### redact.py (PreToolUse → MCP)
PII redaction before sending to external MCP servers.
Clears: IIN, email, phone numbers, API keys.
Exceptions: ClinVar ID, dbSNP, genomic coordinates, git SHA.

### post_format.py (PostToolUse → Edit/Write)
Automatically formats files after editing.
Python: black/ruff. JS/TS: prettier.

### plan_mode_guard.py (PostToolUse → Edit/Write)
If Claude is in Plan Mode — warns about an attempt to edit files.
Plan Mode = planning only, no code changes.

### memory_guard.py (PostToolUse → Bash)
After significant Bash operations, reminds to update project memory.
Triggers: git commit, npm/pip install, docker operations.

### checkpoint_guard.py (PostToolUse → Bash)
Detects risky operations and reminds to create a checkpoint.
Triggers: rebase, merge, DB migrations, rm -rf.

### post_commit_memory.py (PostToolUse → Bash)
After git commit, automatically suggests updating activeContext.md.

### input_guard.py (PreToolUse → MCP)
Prompt injection detection in MCP inputs. 7 pattern categories:
system override, jailbreak, encoding attacks, data exfil, role injection,
credential harvest, command injection. Two-level response: LOW=warn, HIGH=block.

### mcp_circuit_breaker.py (PreToolUse → MCP)
Circuit Breaker pattern (CLOSED/OPEN/HALF_OPEN) for MCP servers.
Prevents cascading failures: 3 failures → OPEN for 60s → HALF_OPEN → test.

### mcp_circuit_breaker_post.py (PostToolUse → MCP)
Records success/failure after MCP calls to update circuit breaker state.

### mcp_locality_guard.py (PreToolUse → MCP)
Enforces "local before MCP" policy — warns when MCP is used for tasks
that could be done with local tools (Read, Grep, Bash).

### read_before_edit.py (PreToolUse → Edit)
Blocks Edit tool calls if the file hasn't been Read first in the session.
Prevents blind edits.

### drift_guard.py (PostToolUse → Skill|Agent)
Detects scope drift by matching tool/skill names against NOT NOW keywords
from Scope Fence in activeContext.md. Lightweight: string matching, no LLM.

### pattern_extractor.py (PostToolUse → Bash)
After `fix:` commits, searches patterns.md for similar bugs.
Suggests counter increment [×N] or new pattern block template.

### session_save.py (Stop)
When the agent stops, saves the current session state.

## Configuration in settings.json

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "startup|resume|clear|compact",
      "hooks": [{
        "type": "command",
        "command": "python ~/.claude/hooks/session_start.py",
        "timeout": 10
      }]
    }],
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "python ~/.claude/hooks/pre_commit_guard.py",
        "timeout": 15
      }]
    }]
  }
}
```

## How to Create Your Own Hook

1. Write a Python/Bash script
2. The script receives context via stdin (JSON)
3. Exit code 0 = OK, exit code 2 = block the action
4. stderr → message to the user
5. Register in settings.json

## Matchers

- `"Bash"` — Bash commands only
- `"Edit|Write"` — Edit or Write
- `"mcp__ollama|mcp__ncbi"` — specific MCP servers
- `"*"` — all tools
- `"startup|resume|clear|compact"` — session events
