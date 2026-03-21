"""Shared utilities for Claude Code hooks.

WHY: DRY — these functions were duplicated across 6+ hook files.
Centralizing them here reduces ~150 lines of duplication and ensures
consistent behavior (e.g., error handling in run_git, path traversal).
"""

import json
import subprocess
import sys
from pathlib import Path


def parse_stdin() -> dict:
    """Parse JSON from stdin (Claude Code hook protocol).

    Returns empty dict on parse failure — hooks should exit gracefully.
    WHY: Every hook does this identically. Centralizing prevents
    inconsistent error handling (some used EOFError, some didn't).
    """
    try:
        result = json.load(sys.stdin)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, EOFError, ValueError):
        return {}


def parse_stdin_raw() -> dict:
    """Parse JSON from stdin using read() instead of load().

    WHY: mcp_circuit_breaker uses sys.stdin.read() explicitly.
    Some hooks need this variant for compatibility.
    """
    try:
        raw = sys.stdin.read()
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def get_tool_input(data: dict) -> dict:
    """Extract tool_input from hook data, supporting both nested and flat formats.

    WHY: Claude Code sends tool_input as a nested dict, but some older
    hook protocols use flat format. This handles both consistently.
    """
    tool_input = data.get("tool_input", data)
    return tool_input if isinstance(tool_input, dict) else data


def run_git(args: list[str], timeout: int = 10) -> str:
    """Run git command and return stdout.

    WHY: Duplicated identically in pre_commit_guard, post_commit_memory,
    pattern_extractor (3 copies, 36 lines total).
    """
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def find_project_memory() -> Path | None:
    """Find activeContext.md walking up from CWD.

    WHY: Duplicated in memory_guard, checkpoint_guard, post_commit_memory,
    session_save, pre_compact (5 copies with slight variations).
    """
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".claude" / "memory" / "activeContext.md"
        if candidate.exists():
            return candidate
    return None


def find_project_claude_dir() -> Path | None:
    """Find .claude/memory/ directory walking up from CWD.

    WHY: session_start.py variant — returns directory, not file.
    Also checks for CLAUDE.md as project root marker.
    """
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".claude" / "memory" / "activeContext.md"
        if candidate.exists():
            return parent / ".claude" / "memory"
        if (parent / "CLAUDE.md").exists():
            claude_mem = parent / ".claude" / "memory"
            if claude_mem.exists():
                return claude_mem
    return None


def find_scope_fence() -> Path | None:
    """Find Scope Fence file, searching multiple tool-agnostic locations.

    Search order (first found wins):
    1. .scope-fence.md at project root (universal)
    2. .claude/memory/activeContext.md (Claude Code)
    3. .cursor/memory_bank/activeContext.md (Cursor)

    WHY: Duplicated in drift_guard.py and session_start.py (identical logic).
    """
    cwd = Path.cwd()
    candidates = [
        ".scope-fence.md",
        str(Path(".claude") / "memory" / "activeContext.md"),
        str(Path(".cursor") / "memory_bank" / "activeContext.md"),
    ]
    for parent in [cwd, *cwd.parents]:
        for rel in candidates:
            full = parent / rel
            if full.exists():
                return full
    return None


def parse_scope_fence(content: str) -> dict[str, str]:
    """Extract Scope Fence fields from file content.

    Returns dict with keys: goal, boundary, done_when, not_now.
    WHY: Used by both drift_guard and session_start.
    """
    fence: dict[str, str] = {}
    in_fence = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "## Scope Fence":
            in_fence = True
            continue
        if in_fence and stripped.startswith("## "):
            break
        if not in_fence:
            continue

        if stripped.startswith("Goal:"):
            fence["goal"] = stripped[5:].strip()
        elif stripped.startswith("Boundary:"):
            fence["boundary"] = stripped[9:].strip()
        elif stripped.startswith("Done when:"):
            fence["done_when"] = stripped[10:].strip()
        elif stripped.startswith("NOT NOW:"):
            fence["not_now"] = stripped[8:].strip()

    return fence


def find_file_upward(relative_path: str) -> Path | None:
    """Find a file by walking up the directory tree from CWD.

    WHY: Generic version of find_project_memory/find_checkpoints_dir.
    Reduces the need for one-off search functions.
    """
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        full = parent / relative_path
        if full.exists():
            return full
    return None


def get_mcp_server_name(tool_name: str) -> str | None:
    """Extract MCP server name from tool name (mcp__<server>__<method>).

    WHY: Duplicated in mcp_circuit_breaker.py and mcp_circuit_breaker_post.py.
    """
    parts = tool_name.split("__")
    if len(parts) >= 3 and parts[0] == "mcp":
        return parts[1]
    return None


def load_json_state(path: Path) -> dict:
    """Load JSON state file, returning empty dict on any error.

    WHY: Duplicated in mcp_circuit_breaker and mcp_circuit_breaker_post
    (identical load_state functions).
    """
    if not path.exists():
        return {}
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_json_state(path: Path, state: dict) -> None:
    """Save dict as JSON state file, creating parent dirs.

    WHY: Duplicated in mcp_circuit_breaker and mcp_circuit_breaker_post.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def emit_hook_result(event_name: str, context: str) -> None:
    """Print hook result JSON to stdout (Claude Code protocol).

    WHY: Almost every hook constructs this dict manually — 30+ lines saved.
    """
    result = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": context,
        }
    }
    print(json.dumps(result))


def sanitize_text(text: str, max_len: int = 200) -> str:
    """Strip newlines and limit length to prevent prompt injection.

    WHY: Duplicated in pattern_extractor (sanitize_commit_msg)
    and input_guard (sanitize). Unified version.
    """
    clean = text.replace("\n", " ").replace("\r", " ").strip()
    if len(clean) > max_len:
        clean = clean[:max_len] + "..."
    return clean


def extract_tool_response(data: dict) -> str:
    """Extract tool response text from hook data, handling multiple formats.

    WHY: Duplicated in memory_guard, post_commit_memory, pattern_extractor
    (identical response extraction with fallbacks).
    """
    tool_response = data.get("tool_response", data.get("tool_result", {}))
    if isinstance(tool_response, dict):
        return str(tool_response.get("stdout", tool_response.get("output", "")))
    elif isinstance(tool_response, str):
        return tool_response
    else:
        return str(tool_response)


def is_failed_commit(response_text: str) -> bool:
    """Check if a git commit actually failed.

    WHY: Simple 'error' substring matching causes false positives on commits
    about error handling features. Use specific git error patterns instead.
    """
    text = response_text.lower()
    git_error_patterns = [
        "nothing to commit",
        "fatal:",
        "error:",
        "failed to",
        "cannot ",
        "could not",
        "not a git repository",
        "pre-commit hook",
    ]
    return any(pattern in text for pattern in git_error_patterns)
