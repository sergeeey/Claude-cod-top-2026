#!/usr/bin/env python3
"""
Example Hook — Living Documentation

PURPOSE:
This is a reference implementation showing how to write hooks in Claude Code.
Copy this file, modify event/logic, test → you have a working hook.

WHAT IS A HOOK:
Hooks intercept Claude Code events (SessionStart, PreToolUse, PostToolUse, Stop, etc.)
to add custom behavior: validation, logging, auto-capture, notifications, routing.

HOW HOOKS WORK:
1. Claude Code emits event (e.g., "UserPromptSubmit")
2. Claude Code finds hooks registered for that event (settings.json)
3. Runs each hook script with event data as JSON on stdin
4. Hook returns JSON on stdout (can block/modify/augment event)
5. Claude Code continues with hook's output

HOOK LIFECYCLE:
Input (stdin) → Parse JSON → Validate → Business Logic → Output (stdout)

WHEN TO USE HOOKS:
- Validation (block dangerous commands before execution)
- Logging (capture events to file/database)
- Auto-capture (extract patterns from sessions)
- Notifications (alert on errors/completions)
- Routing (redirect tasks to specialized agents)
- Context injection (add project-specific context)

WHEN NOT TO USE HOOKS:
- Heavy computation (hooks must be fast <100ms)
- External API calls (use agents instead)
- Complex state management (use memory files instead)
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


# ============================================================================
# SECTION 1: CONFIGURATION
# ============================================================================

# Hook metadata (used by validation tools)
HOOK_NAME = "example-hook"
HOOK_VERSION = "1.0.0"
HOOK_EVENTS = ["UserPromptSubmit"]  # Which events this hook handles

# Configuration paths
CLAUDE_HOME = Path.home() / ".claude"
MEMORY_DIR = CLAUDE_HOME / "memory"
LOGS_DIR = CLAUDE_HOME / "logs"

# Feature flags (disable features if needed)
ENABLE_LOGGING = True
ENABLE_VALIDATION = True


# ============================================================================
# SECTION 2: INPUT/OUTPUT HANDLING
# ============================================================================


def read_event() -> Dict[str, Any]:
    """
    Read event data from stdin (JSON).

    Claude Code passes event data as JSON on stdin:
    {
      "event": "UserPromptSubmit",
      "data": {
        "prompt": "user's message",
        "conversationId": "abc123",
        ...
      }
    }

    Returns:
        Parsed event dict

    Raises:
        json.JSONDecodeError if stdin is not valid JSON
    """
    try:
        event = json.load(sys.stdin)
        return event
    except json.JSONDecodeError as e:
        # If JSON invalid, log error and exit
        # Don't print to stdout (that's for hook output)
        print(f"ERROR: Invalid JSON on stdin: {e}", file=sys.stderr)
        sys.exit(1)


def write_output(result: Dict[str, Any]) -> None:
    """
    Write hook result to stdout (JSON).

    Hook output format:
    {
      "block": false,              # If true, blocks event from proceeding
      "message": "...",             # Message shown to user (if blocked)
      "data": {...},                # Modified event data (optional)
      "metadata": {...}             # Hook metadata (optional)
    }

    Args:
        result: Hook result dict
    """
    json.dump(result, sys.stdout)
    sys.stdout.flush()  # Important: flush to ensure Claude Code receives output


# ============================================================================
# SECTION 3: BUSINESS LOGIC
# ============================================================================


def validate_prompt(prompt: str) -> Optional[str]:
    """
    Validate user prompt for dangerous patterns.

    This is an example validation function. Real validation should check:
    - SQL injection patterns (DROP TABLE, etc.)
    - Command injection (rm -rf, etc.)
    - Secrets leakage (API keys, passwords)
    - PII in prompts (SSN, credit card numbers)

    Args:
        prompt: User's message

    Returns:
        Error message if validation fails, None if passes
    """
    if not ENABLE_VALIDATION:
        return None

    # Example: Block prompts containing dangerous shell commands
    dangerous_patterns = [
        "rm -rf /",
        "DROP TABLE",
        "sudo rm",
        "> /dev/sda",
    ]

    for pattern in dangerous_patterns:
        if pattern in prompt:
            return f"Blocked: Dangerous pattern detected: {pattern}"

    return None


def log_event(event_type: str, data: Dict[str, Any]) -> None:
    """
    Log event to file for debugging/analytics.

    Logs are written to ~/.claude/logs/example-hook.jsonl
    (JSONL = one JSON object per line, easy to parse)

    Args:
        event_type: Event name (e.g., "UserPromptSubmit")
        data: Event data
    """
    if not ENABLE_LOGGING:
        return

    log_file = LOGS_DIR / "example-hook.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Log entry format
    log_entry = {
        "timestamp": data.get("timestamp", "unknown"),
        "event": event_type,
        "conversationId": data.get("conversationId", "unknown"),
        "prompt_length": len(data.get("prompt", "")),
        # Don't log full prompt (may contain PII)
    }

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")


def process_user_prompt_submit(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle UserPromptSubmit event.

    This event fires when user submits a message (before Claude sees it).

    Use cases:
    - Validate prompt for dangerous content → block if needed
    - Log user activity for analytics
    - Inject context (e.g., add project-specific rules to prompt)
    - Route to specialized agent based on keywords

    Args:
        data: Event data containing "prompt", "conversationId", etc.

    Returns:
        Hook result dict (block=True to prevent prompt from proceeding)
    """
    prompt = data.get("prompt", "")

    # Step 1: Validate prompt
    error = validate_prompt(prompt)
    if error:
        return {
            "block": True,
            "message": error,
            "metadata": {"hook": HOOK_NAME, "reason": "validation_failed"},
        }

    # Step 2: Log event (for analytics)
    log_event("UserPromptSubmit", data)

    # Step 3: Pass through (don't block, don't modify)
    return {
        "block": False,
        "data": data,  # Pass data unchanged
        "metadata": {"hook": HOOK_NAME, "action": "passed"},
    }


# ============================================================================
# SECTION 4: EVENT ROUTER
# ============================================================================


def handle_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Route event to appropriate handler.

    Each hook can handle multiple events. Route by event type.

    Args:
        event: Event dict with "event" and "data" fields

    Returns:
        Hook result dict
    """
    event_type = event.get("event", "unknown")
    data = event.get("data", {})

    # Route to handler
    if event_type == "UserPromptSubmit":
        return process_user_prompt_submit(data)

    # Add more handlers here:
    # elif event_type == "PostToolUse":
    #     return process_post_tool_use(data)

    # Default: pass through (no-op)
    return {
        "block": False,
        "data": data,
        "metadata": {"hook": HOOK_NAME, "action": "no_handler"},
    }


# ============================================================================
# SECTION 5: MAIN ENTRY POINT
# ============================================================================


def main():
    """
    Main entry point for hook.

    Workflow:
    1. Read event from stdin (JSON)
    2. Route to handler
    3. Write result to stdout (JSON)
    4. Exit with code 0 (success) or 1 (error)
    """
    try:
        # Read event from stdin
        event = read_event()

        # Handle event
        result = handle_event(event)

        # Write result to stdout
        write_output(result)

        # Exit success
        sys.exit(0)

    except Exception as e:
        # If hook crashes, log error and return pass-through result
        # (don't block event due to hook bug)
        error_result = {
            "block": False,
            "message": f"Hook error: {str(e)}",
            "metadata": {"hook": HOOK_NAME, "error": str(e)},
        }
        write_output(error_result)
        print(f"ERROR in {HOOK_NAME}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()


# ============================================================================
# TESTING THE HOOK
# ============================================================================

"""
To test this hook:

1. Manual test (simulate Claude Code event):
   echo '{"event": "UserPromptSubmit", "data": {"prompt": "test message", "conversationId": "test123"}}' | python example-hook.py

   Expected output:
   {"block": false, "data": {"prompt": "test message", "conversationId": "test123"}, "metadata": {"hook": "example-hook", "action": "passed"}}

2. Test validation (dangerous pattern):
   echo '{"event": "UserPromptSubmit", "data": {"prompt": "rm -rf /", "conversationId": "test123"}}' | python example-hook.py

   Expected output:
   {"block": true, "message": "Blocked: Dangerous pattern detected: rm -rf /", "metadata": {"hook": "example-hook", "reason": "validation_failed"}}

3. Integration test (register in settings.json):
   Add to ~/.claude/settings.json:
   {
     "hooks": {
       "UserPromptSubmit": {
         "script": "example-hook.py",
         "python": "/path/to/python"
       }
     }
   }

   Then use Claude Code normally. Hook will run on every user message.

4. Validation test:
   python scripts/validate-hooks.py --config ~/.claude/settings.json

   Should report 0 errors.
"""


# ============================================================================
# HOOK REGISTRATION (settings.json format)
# ============================================================================

"""
To register this hook in Claude Code:

1. Add to ~/.claude/settings.json:

{
  "hooks": {
    "UserPromptSubmit": {
      "script": "example-hook.py",
      "python": "/usr/bin/python3",
      "timeout": 5000
    }
  }
}

2. Test with validation tool:
   python scripts/validate-hooks.py

3. Restart Claude Code or reload config

4. Hook will run on every UserPromptSubmit event


MULTIPLE HOOKS FOR SAME EVENT:

{
  "hooks": {
    "UserPromptSubmit": [
      {"script": "validation-hook.py", "python": "/usr/bin/python3"},
      {"script": "example-hook.py", "python": "/usr/bin/python3"},
      {"script": "logging-hook.py", "python": "/usr/bin/python3"}
    ]
  }
}

Hooks run in order. If any hook blocks (block=true), event stops.


HOOK EVENTS AVAILABLE:

- SessionStart: Claude Code session starts
- SessionEnd: Claude Code session ends
- UserPromptSubmit: User sends message
- PreToolUse: Before tool executes (can block tool)
- PostToolUse: After tool executes (can validate output)
- PostToolUseFailure: Tool execution failed
- Stop: Agent finishes response
- PreCompact: Before context compaction
- PostCompact: After context compaction
- PermissionRequest: Permission prompt shown to user
- SubagentStart: Subagent invoked
- SubagentStop: Subagent finished
- ConfigChange: Settings changed
- TaskCreated: Task created
- TaskCompleted: Task completed
- Notification: Notification shown
- InstructionsLoaded: CLAUDE.md loaded
"""


# ============================================================================
# BEST PRACTICES
# ============================================================================

"""
1. Keep hooks FAST (<100ms)
   - No heavy computation
   - No external API calls (or make them async)
   - No file I/O in hot path (log async)

2. Hooks should be IDEMPOTENT
   - Running twice should not cause issues
   - Don't rely on external state

3. NEVER block on errors
   - If hook crashes, pass event through (don't block user)
   - Log error, return {block: false}

4. LOG everything
   - Use JSONL for easy parsing
   - Include timestamp, conversationId, event type
   - Don't log PII (truncate prompts, redact secrets)

5. VALIDATE aggressively
   - Check for dangerous patterns
   - Block early (PreToolUse, not PostToolUse)
   - Return clear error messages

6. TEST thoroughly
   - Unit test validation functions
   - Integration test with Claude Code
   - Test error cases (invalid JSON, missing data)

7. VERSION hooks
   - Include version in metadata
   - Document breaking changes
   - Support rollback (keep old version)

8. DOCUMENT usage
   - What events it handles
   - What it validates/logs/modifies
   - How to configure
   - How to test
"""
