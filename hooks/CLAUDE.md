# Hooks — Local Rules

## Architecture
All hooks share utils.py (parse_stdin, emit_hook_result, hook_main).
Never duplicate these — import from utils.

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

### Exit codes
- `sys.exit(0)` — success or skip (no action needed)
- `sys.exit(1)` — block the tool call (PreToolUse only)
- Never raise unhandled exceptions — hook dies silently

## Adding a New Hook
1. Import `from utils import emit_hook_result, hook_main, parse_stdin`
2. Add recursion guard if hook reads memory or calls Claude
3. Register in `settings.json` with `__PYTHON_CMD__ __CLAUDE_HOME__/hooks/<name>.py`
4. Add entry to README hook table

## Known Anti-Patterns
- `async_wrapper` + `emit_hook_result` = silent failure (learned 2026-04-19)
- Missing `CLAUDE_INVOKED_BY` guard = Agent SDK infinite loop
- `datetime.utcnow()` mixed with timezone-aware datetimes = TypeError at runtime
