# Hooks — Local Rules

## Architecture
Shared code lives in `hooks/lib/{runtime,state,discovery,security}.py`, grouped by
responsibility (hook I/O protocol, state files/locking, project discovery,
sanitization/secrets) — split out 2026-08-22 from a single `utils.py` that had grown
to 36 symbols and fan-in 74 (HS-01, `artifacts/architecture-coupling/hotspots.json`).

`hooks/utils.py` still exists as a backward-compatible facade re-exporting every
symbol, so old `from utils import X` call sites keep working — but it is a facade,
not the source. **New code should import directly from `hooks/lib/{runtime,state,
discovery,security}.py`**, not from `utils`. Never duplicate these symbols elsewhere.

## Critical Patterns

### stdout is the hook protocol
`emit_hook_result()` writes JSON to stdout → Claude Code reads it.
If a hook runs via `async_wrapper.py`, stdout goes to DEVNULL → emit_hook_result silently fails.
**Never wrap a hook in async_wrapper if it needs to inject context.**

### Recursion guard
Every hook that calls Claude or reads memory must check:
```python
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)
```
Missing this = infinite loop when Claude Code invokes subagents.

### Blocking protocol — two different mechanisms, do not mix

Claude Code SDK uses a different signal per hook type (full detail:
`hooks/lib/runtime.py`'s module docstring):

- **PreToolUse** — call `emit_permission_decision()` from `hooks/lib/runtime.py`
  (JSON `hookSpecificOutput` to stdout). `sys.exit(1)` does NOT block a
  PreToolUse call. Correct examples: `pre_commit_guard.py`, `security_verify.py`,
  `input_guard.py`, `redact.py`.
- **PostToolUse** — `sys.exit(1)` signals Claude Code to suppress/flag the
  tool result. Correct examples: `validation_theater_guard.py`,
  `mcp_circuit_breaker_post.py`.

### Exit codes
- `sys.exit(0)` — success or skip (no action needed)
- `sys.exit(1)` — PostToolUse-only signal (see above; on PreToolUse this
  does nothing — use `emit_permission_decision()` instead)
- Never raise unhandled exceptions — hook dies silently

## Adding a New Hook
1. Import `from lib.runtime import emit_hook_result, hook_main, parse_stdin`
2. Add recursion guard if hook reads memory or calls Claude
3. Register in `settings.json` with `__PYTHON_CMD__ __CLAUDE_HOME__/hooks/<name>.py`
4. Add entry to README hook table

## Known Anti-Patterns
- `async_wrapper` + `emit_hook_result` = silent failure (learned 2026-04-19)
- Missing `CLAUDE_INVOKED_BY` guard = Agent SDK infinite loop
- `datetime.utcnow()` mixed with timezone-aware datetimes = TypeError at runtime
