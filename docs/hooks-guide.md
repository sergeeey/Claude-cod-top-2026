# Hooks Guide

## What are Hooks

Hooks are scripts that run automatically at specific moments during Claude Code operation.
Unlike CLAUDE.md instructions (which the model can ignore), hooks execute 100% of the time.

## 14 Hook Events (v3.0.0)

| Event | When | Our hooks |
|-------|------|-----------|
| **SessionStart** | Start/resume/clear/compact | `session_start.py` |
| **PreCompact** | Before context compaction | `pre_compact.py` |
| **PreToolUse** | Before tool call | `pre_commit_guard.py`, `read_before_edit.py`, `security_verify.py`, `input_guard.py`, `mcp_circuit_breaker.py`, `mcp_locality_guard.py`, `redact.py` |
| **PostToolUse** | After tool call | `mcp_circuit_breaker_post.py`, `post_format.py` (async), `plan_mode_guard.py`, `drift_guard.py`, `memory_guard.py`, `checkpoint_guard.py`, `post_commit_memory.py`, `pattern_extractor.py` (async), `auto_capture.py` |
| **UserPromptSubmit** | Before prompt submission | `keyword_router.py`, `thinking_level.py`, `prompt_wiki_inject.py` |
| **Stop** | Agent stop | `session_save.py` (async), `webhook_notify.py` (async), `wiki_reminder.py` |
| **Notification** | Task complete | Audio beep (powershell) |
| **PermissionRequest** | Permission decision | `permission_policy.py` |
| **FileChanged** | File modified externally | `env_reload.py` |
| **CwdChanged** | Directory changed | `direnv_loader.py` |
| **SubagentStart** | Subagent starts | `agent_lifecycle.py --start` |
| **SubagentStop** | Subagent stops | `agent_lifecycle.py --stop`, `subagent_verify.py` |
| **ConfigChange** | Settings modified | `config_audit.py` |
| **TeammateIdle** | Agent idle in team | `team_rebalance.py` |

## Description of Each Hook

### session_start.py (SessionStart)
Loads the current project's activeContext.md and outputs it into context.
Allows Claude to "remember" where it left off.

### pre_compact.py (PreCompact)
Before context compaction, saves the current state to activeContext.md.
Progressive compression: preserves critical sections (errors, decisions).

### pre_commit_guard.py (PreToolUse → Bash)
Scans Bash commands for dangerous patterns:
- `git push --force`, `git reset --hard`
- `DROP TABLE`, `TRUNCATE TABLE`
- `rm -rf /`, `chmod 777`
Blocks execution (exit code 2) with a warning.

### read_before_edit.py (PreToolUse → Edit|Write)
Blocks Edit tool calls if the file hasn't been Read first in the session.
Prevents blind edits.

### security_verify.py (PreToolUse → Edit|Write)
Auto-warns when editing sensitive files (.env, auth, payment, secret, migration, crypto).
Suggests running sec-auditor agent before proceeding. Uses centralized `is_sensitive_file()` from utils.py.

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

### redact.py (PreToolUse → external MCP)
PII redaction before sending to external MCP servers.
Clears: national IDs, email, phone numbers, API keys (12 patterns).
Exceptions: ClinVar ID, dbSNP, genomic coordinates, git SHA.

### post_format.py (PostToolUse → Edit|Write, **async**)
Automatically formats files after editing.
Python: ruff. JS/TS: prettier. Runs via async_wrapper — non-blocking.

### plan_mode_guard.py (PostToolUse → Edit|Write)
Warns if 3+ files edited without entering Plan Mode first.

### drift_guard.py (PostToolUse → Skill|Agent)
Detects scope drift by matching tool/skill names against NOT NOW keywords
from Scope Fence in activeContext.md. Lightweight: string matching, no LLM.

### memory_guard.py (PostToolUse → Bash)
After significant Bash operations, reminds to update project memory.
Triggers: git commit, npm/pip install, docker operations.

### checkpoint_guard.py (PostToolUse → Bash)
Detects risky operations and reminds to create a checkpoint.
Triggers: rebase, merge, DB migrations, rm -rf.

### post_commit_memory.py (PostToolUse → Bash)
After git commit, automatically logs to activeContext.md.

### pattern_extractor.py (PostToolUse → Bash, **async**)
After `fix:` commits, searches patterns.md for similar bugs.
Suggests counter increment [×N] or new pattern block template. Runs via async_wrapper.

### keyword_router.py (UserPromptSubmit)
Auto-suggests skills based on keywords in user prompt:
tdd → tdd-workflow, security → security-audit, brainstorm → brainstorming, etc.

### thinking_level.py (UserPromptSubmit)
Auto-suggests `/think ultrathink` for complex tasks (architecture, debugging, multi-file).

### session_save.py (Stop, **async**)
When the agent stops, warns if activeContext.md is stale. Runs via async_wrapper.

### webhook_notify.py (Stop, **async**)
Sends session event notifications to Slack/Telegram webhook.
SSRF-protected: validates URL (blocks localhost, private IPs, file:// scheme).
Auto-redacts secrets (password, token, key) from payloads before sending.

### permission_policy.py (PermissionRequest)
Programmatic permission decisions — reduces prompts by ~75%:
- **Auto-allow**: Read, Glob, Grep, safe Bash prefixes (git status, pytest, ruff, ls, etc.)
- **Auto-deny**: 39 dangerous patterns (rm -rf, DROP TABLE, sudo, mkfs, eval, python -c, etc.)
- **Chain-operator protection**: detects &&, ||, ;, | BEFORE prefix matching
- **Default**: ask the user

### env_reload.py (FileChanged)
Watches .env/.envrc/.env.local/.env.development for changes.
Safe parsing: regex validates KEY=VALUE format, shlex.quote() prevents command injection.
Path boundary check prevents traversal attacks.

### direnv_loader.py (CwdChanged)
When working directory changes, loads .env from the new directory.
Uses `parse_env_file_safe()` from utils.py. Path traversal protection via `is_safe_path()`.

### agent_lifecycle.py (SubagentStart / SubagentStop)
- **--start**: Injects project context (activeContext.md) into the starting agent.
- **--stop**: Logs agent completion to `~/.claude/logs/agent_lifecycle.log` audit trail.
Uses explicit CLI flags instead of fragile payload heuristics.

### config_audit.py (ConfigChange)
Logs all configuration changes to `~/.claude/logs/config_audit.jsonl` (append-only).
Provides audit trail for settings modifications.

### team_rebalance.py (TeammateIdle)
Logs idle agent events and notifies orchestrator for task redistribution.
Supports Agent Teams workflow (review-squad, build-squad, research-squad).

### auto_capture.py (PostToolUse → Bash)
Captures knowledge from git commits and pytest failures mid-session as raw notes
in `~/.claude/memory/raw/`. Fills the gap when session crashes before session_save runs.
Idempotent: same slug won't be written twice. Sanitizes filenames to prevent path traversal.

### prompt_wiki_inject.py (UserPromptSubmit)
Per-prompt wiki context injection. Searches wiki/index.md for keywords matching the
user's prompt and injects up to 2 relevant articles (max 1200 chars each) as context.
Skips short prompts (<15 chars). Stop-word filtered. Zero cost when wiki is empty.

### wiki_reminder.py (Stop)
Detects 3+ architectural decision keywords in the last assistant response and fires
a systemMessage nudge to save to wiki/decisions.md. Debounced to 5 minutes to avoid
reminder fatigue. Self-contained, no imports beyond stdlib.

### subagent_verify.py (SubagentStop)
Verifies agent output quality: checks for empty responses, suspiciously short output
(<50 chars), and apology markers ("I apologize", "unable to complete"). Logs verdict
(PASS/FAIL) to `~/.claude/logs/subagent_verify.jsonl`. Warns orchestrator on FAIL.

### instructions_audit.py (InstructionsLoaded)
Logs which CLAUDE.md and rules files load each session to `~/.claude/logs/instructions.jsonl`.
Helps debug config drift across machines and sessions.

### async_wrapper.py (utility)
Universal non-blocking launcher for background hooks.
Reads stdin, spawns the actual hook as a detached subprocess, exits immediately.
Windows: uses DETACHED_PROCESS + CREATE_NO_WINDOW flags. Unix: start_new_session=True.

### statusline.py (utility)
Persistent bar at bottom of terminal: model, context %, git branch, cost, duration.
Zero token cost. Color-coded: green <50%, yellow 50-70%, red >70%.

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
    }],
    "Stop": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "python ~/.claude/hooks/async_wrapper.py python ~/.claude/hooks/session_save.py",
        "timeout": 5
      }]
    }]
  }
}
```

## How to Create Your Own Hook

1. Write a Python script
2. The script receives context via stdin (JSON)
3. Exit code 0 = OK, exit code 2 = block the action
4. Output JSON to stdout for structured responses
5. For slow hooks, wrap with `async_wrapper.py` to avoid blocking
6. Register in settings.json under the appropriate event

## Matchers

- `"Bash"` — Bash commands only
- `"Edit|Write"` — Edit or Write
- `"mcp__*"` — all MCP servers
- `"mcp__ollama|mcp__ncbi"` — specific MCP servers
- `"Skill|Agent"` — Skill or Agent tool calls
- `"*"` — all tools
- `""` (empty) — catch-all for events without tool context
- `"startup|resume|clear|compact"` — session start sub-events
- `".env|.envrc|.env.local|.env.development"` — FileChanged file patterns
