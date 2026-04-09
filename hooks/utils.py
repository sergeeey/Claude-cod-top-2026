"""Shared utilities for Claude Code hooks.

WHY: DRY — these functions were duplicated across 6+ hook files.
Centralizing them here reduces ~150 lines of duplication and ensures
consistent behavior (e.g., error handling in run_git, path traversal).
"""

import json
import subprocess
import sys
from datetime import UTC
from pathlib import Path

# --- Circuit Breaker shared constants ----------------------------------------
# WHY: both mcp_circuit_breaker.py and mcp_circuit_breaker_post.py need
# identical values. Single source of truth prevents threshold drift.
CB_FAILURE_THRESHOLD = 3
CB_RECOVERY_TIMEOUT = 60  # seconds
CB_STATE_FILE = Path.home() / ".claude" / "cache" / "mcp_circuit_state.json"


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


# --- Sensitive file detection ------------------------------------------------
# WHY: security_verify.py needs these patterns. Centralized here so
# other hooks can reuse the same detection logic.
SENSITIVE_PATTERNS: tuple[str, ...] = (
    ".env",
    "secret",
    "migration",
    "auth",
    "payment",
    "credential",
    "token",
    "password",
    "crypto",
)


def is_sensitive_file(path: str) -> bool:
    """Check if a file path matches sensitive patterns (case-insensitive).

    WHY: Edits to auth/payment/secret files are high-risk.
    Centralizing detection prevents pattern drift between hooks.
    """
    lower = path.lower()
    return any(p in lower for p in SENSITIVE_PATTERNS)


def send_webhook(url: str, payload: dict, timeout: int = 5) -> bool:
    """Send HTTP POST to a webhook URL. Returns True on success.

    WHY: webhook_notify.py needs fire-and-forget HTTP calls.
    Centralized here for reuse by other notification hooks.
    """
    import urllib.request

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False


def log_audit_event(event_type: str, details: str) -> None:
    """Append an audit event to ~/.claude/logs/audit.log.

    WHY: config_audit.py and other hooks need consistent audit logging.
    Centralized here to ensure uniform format and directory creation.
    """
    from datetime import datetime

    log_dir = Path.home() / ".claude" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "audit.log"
    timestamp = datetime.now(UTC).isoformat()
    entry = {"timestamp": timestamp, "event": event_type, "details": details}
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def parse_env_file_safe(path: Path) -> list[str]:
    """Parse .env file and return safe export lines.

    WHY: Raw .env parsing is vulnerable to command injection via shell
    metacharacters ($, `, ;, |, &&). This function validates each line
    against a strict KEY=VALUE pattern and quotes values with shlex.
    Also blocks dangerous env key names that can hijack process execution.
    """
    import re
    import shlex

    safe_key = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    dangerous_chars = re.compile(r"[`$;|&()<>{}!\\]")
    # WHY: these env vars can hijack process execution regardless of value.
    # LD_PRELOAD injects shared libraries, PATH redirects all commands,
    # PYTHONPATH/NODE_OPTIONS inject code into interpreters.
    dangerous_keys = frozenset(
        {
            "LD_PRELOAD",
            "LD_LIBRARY_PATH",
            "DYLD_INSERT_LIBRARIES",
            "DYLD_LIBRARY_PATH",
            "PYTHONPATH",
            "PYTHONSTARTUP",
            "NODE_OPTIONS",
            "NODE_PATH",
            "PERL5LIB",
            "RUBYLIB",
            "PATH",
            "SHELL",
            "HOME",
            "USER",
            "LOGNAME",
            "PROMPT_COMMAND",
            "ENV",
            "BASH_ENV",
            "CLASSPATH",
            "JAVA_TOOL_OPTIONS",
        }
    )
    exports: list[str] = []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # WHY: reject keys with shell metacharacters or invalid names
        if not safe_key.match(key):
            continue
        # WHY: reject dangerous env var names that hijack process execution
        if key.upper() in dangerous_keys:
            continue
        # WHY: reject values with obvious injection payloads
        if dangerous_chars.search(value):
            continue
        # WHY: shlex.quote prevents shell interpretation of the value
        exports.append(f"export {key}={shlex.quote(value)}")

    return exports


def is_safe_path(path: Path, boundary: Path | None = None) -> bool:
    """Check that a resolved path is within the user's home directory.

    WHY: Prevents path traversal attacks where an attacker can
    craft paths like ../../etc/ to escape the project tree.
    Uses is_relative_to() instead of string prefix to avoid
    false positives like C:\\Users\\sboi vs C:\\Users\\sboiEVIL.
    """
    try:
        resolved = path.resolve()
        home = (boundary or Path.home()).resolve()
        # WHY: is_relative_to (Python 3.9+) is path-aware, not string-aware.
        # str.startswith would match /home/user against /home/user_evil.
        return resolved == home or resolved.is_relative_to(home)
    except (OSError, ValueError):
        return False


def hook_main(fn: "Callable[[], None]", timeout: int = 30) -> None:
    """Run hook main() with a hard timeout — fail-open on hang.

    WHY: Hooks that hang (network partition during MCP call, slow git)
    would block Claude Code indefinitely. signal.alarm is Unix-only,
    so we use a daemon thread which is killed when the process exits.
    Fail-open (exit 0) to never block user workflow.
    """
    import os
    import threading
    from typing import Callable

    done = threading.Event()
    exc: list[BaseException] = []

    def _target() -> None:
        try:
            fn()
        except SystemExit:
            pass  # sys.exit() inside hook is expected
        except Exception as e:  # noqa: BLE001
            exc.append(e)
        finally:
            done.set()

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    fired = done.wait(timeout=timeout)

    if not fired:
        print(f"[hook-timeout] timed out after {timeout}s, exiting.", file=sys.stderr)
        os._exit(0)  # hard exit — daemon thread is killed automatically

    if exc:
        print(f"[hook-error] unhandled exception: {exc[0]}", file=sys.stderr)
        os._exit(1)


def log_hook_timing(hook_name: str, duration_ms: float, blocked: bool = False) -> None:
    """Log hook execution time to audit.log for observability.

    WHY: Without timing data there is no way to detect hooks that are
    silently slow (>500ms adds latency to every Claude tool call).
    """
    log_audit_event(
        "hook_execution",
        f"hook={hook_name} duration_ms={duration_ms:.0f} blocked={blocked}",
    )


def is_failed_commit(response_text: str) -> bool:
    """Check if a git commit actually failed.

    WHY: Simple 'error:' substring matching causes false positives on commits
    about error handling features. Use line-start git error patterns instead.
    """
    for line in response_text.lower().splitlines():
        stripped = line.strip()
        # WHY: git errors start with these prefixes at line beginning.
        # Matching anywhere would false-positive on commit messages like
        # "fix: improve error: handling in parser".
        if stripped.startswith(("fatal:", "error:")):
            return True
        if any(
            p in stripped
            for p in (
                "nothing to commit",
                "not a git repository",
                "pre-commit hook",
            )
        ):
            return True
    return False
