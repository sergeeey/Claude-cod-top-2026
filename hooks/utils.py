"""Shared utilities for Claude Code hooks.

WHY: DRY — these functions were duplicated across 6+ hook files.
Centralizing them here reduces ~150 lines of duplication and ensures
consistent behavior (e.g., error handling in run_git, path traversal).
"""

import json
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC
from pathlib import Path

# ============================================================
# BLOCKING PROTOCOL — which mechanism to use in which hook type
# ============================================================
# PreToolUse hooks:
#   → emit_permission_decision() from this module
#   Correct files: pre_commit_guard.py, security_verify.py, input_guard.py, redact.py
#
#   WHY NOT bare top-level {"decision": "block", ...} or {"tool_input": ...}:
#   a live behavioral test (2026-07-01, see tests/test_pretooluse_output_schema.py
#   and tests/test_redact_mcp_behavior.py) proved that legacy top-level
#   `decision: block` still blocks (Claude Code kept it for backward compat),
#   but legacy top-level `tool_input` mutation is SILENTLY DROPPED — the
#   original unmodified tool_input reaches the downstream tool regardless of
#   what a hook prints. This was a real, confirmed bug in redact.py's PII
#   redaction: fake secrets written through an MCP tool came out unredacted.
#   `hookSpecificOutput.updatedInput` is the only path proven to work.
#
# PostToolUse hooks:
#   → sys.exit(1)   (signals Claude Code to suppress/flag the tool result)
#   Correct files: validation_theater_guard.py, mcp_circuit_breaker_post.py
#
# WHY two mechanisms: Claude Code SDK uses different signals per hook type.
# PreToolUse: hookSpecificOutput JSON to stdout. PostToolUse: exit code.
# Do NOT mix mechanisms across hook types — it will silently fail.
# ============================================================

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
        # WHY: global vault uses _auto/ subfolder, but project-level vaults
        # keep activeContext.md directly in memory/. Check both paths.
        for subpath in [
            ".claude" / Path("memory") / "_auto" / "activeContext.md",
            ".claude" / Path("memory") / "activeContext.md",
        ]:
            candidate = parent / subpath
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
        # WHY: check _auto/ (global vault v2) then direct (project-level vaults)
        for subpath in [
            ".claude" / Path("memory") / "_auto" / "activeContext.md",
            ".claude" / Path("memory") / "activeContext.md",
        ]:
            if (parent / subpath).exists():
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
        str(Path(".claude") / "memory" / "_auto" / "activeContext.md"),
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


def atomic_write_json(path: Path, data: object, *, indent: int | None = None) -> None:
    """Atomically persist data as JSON at path.

    WHY: plain open("w") + json.dump truncates the file on write start;
    a kill-9 or OOM between truncation and final flush produces an empty
    or partial file — data loss on every state file (circuit breaker state,
    wiki entries, memory snapshots). tmp + fsync + os.replace is atomic on
    POSIX and best-effort on Windows (os.replace is atomic within the same
    volume). PID suffix prevents collisions when two processes write the
    same path concurrently (e.g. parallel hook invocations).
    """
    import os

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=indent, ensure_ascii=False))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically write a text file. Same guarantees as atomic_write_json."""
    import os

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def save_json_state(path: Path, state: dict) -> None:
    """Save dict as JSON state file, creating parent dirs.

    WHY: Duplicated in mcp_circuit_breaker and mcp_circuit_breaker_post.
    Delegates to atomic_write_json for crash-safe writes.
    """
    atomic_write_json(path, state, indent=2)


def emit_hook_result(event_name: str, context: str) -> None:
    """Print hook result JSON to stdout (Claude Code protocol).

    WHY: Almost every hook constructs this dict manually — 30+ lines saved.
    Emits additionalContext (informational — does NOT block tool execution).
    For blocking/asking, use emit_permission_decision() instead.
    """
    result = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": context,
        }
    }
    print(json.dumps(result))


def emit_permission_decision(
    decision: str,
    reason: str = "",
    context: str = "",
    updated_input: dict | None = None,
) -> None:
    """Print PreToolUse permissionDecision JSON to stdout (Claude Code SDK protocol).

    WHY: The proper SDK-level way to allow/deny/ask in PreToolUse hooks.
    Preferred over sys.exit(2) and over bare top-level {"decision": ...} /
    {"tool_input": ...}, both legacy shapes. A live behavioral test
    (2026-07-01) proved bare top-level `tool_input` mutation is silently
    dropped by Claude Code — only `hookSpecificOutput.updatedInput` reaches
    the downstream tool. See tests/test_pretooluse_output_schema.py.

    Parameters
    ----------
    decision : str
        "allow" | "deny" | "ask"
        - "allow"  → proceed (optionally with updated_input), no user prompt
        - "deny"   → block tool execution (replaces sys.exit(2))
        - "ask"    → prompt user to allow/deny before proceeding
    reason : str
        Shown to user as the explanation for this decision. Required for
        "deny"/"ask"; usually omitted for a silent "allow".
    context : str
        Optional additionalContext injected into Claude's context window.
    updated_input : dict | None
        Replacement tool_input (e.g. sanitized/redacted). Only meaningful
        with decision="allow" — Claude Code uses this in place of the
        original arguments before the tool runs.
    """
    output: dict = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
        }
    }
    if reason:
        output["hookSpecificOutput"]["permissionDecisionReason"] = reason
    if context:
        output["hookSpecificOutput"]["additionalContext"] = context
    if updated_input is not None:
        output["hookSpecificOutput"]["updatedInput"] = updated_input
    print(json.dumps(output))


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


def rotate_log_if_large(path: Path, max_bytes: int = 5 * 1024 * 1024, backups: int = 3) -> None:
    """Rotate `path` to `path.1` (shifting older backups up) before it grows past max_bytes.

    WHY: hook_triggers.jsonl, model_usage.jsonl, hook_events.jsonl, audit.log,
    and sessions.log are append-only and were never rotated — on a long-lived
    machine they grow without bound (model_usage.jsonl appends once per tool
    call). This is a plain size-based logrotate equivalent, checked before each
    append so no background process or cron job is needed.

    Behavior
    --------
    * Checked BEFORE the write that would grow the file, so a single append
      never pushes the file past max_bytes by more than one line's worth.
    * Rotates by shifting existing backups: path.(backups-1) -> path.backups,
      ..., path -> path.1. The oldest backup (path.<backups>) is discarded.
    * A file under max_bytes (including one that doesn't exist yet) is left
      untouched — this only ever acts on a file that has already grown past
      the threshold, never on today's normal-sized logs.
    * Silent on failure (OSError) — log rotation must never break a hook.

    Known limitations (accepted, not bugs):
    * TOCTOU race under concurrent hook invocations (two Claude Code sessions
      on the same machine): both can pass the size check before either
      rotates. On POSIX the second `rename` silently clobbers the first's
      `.1` backup (one generation lost, no crash). On Windows it raises
      `FileExistsError`, caught by the `except OSError` below — a missed
      rotation, not data loss or a crash. Acceptable for a fail-open,
      best-effort log; not worth a lock file for this use case.
    * Rotation is rename-based, so a process doing `tail -f` on one of these
      logs will stop seeing new lines after a rotation (the fd it holds now
      points at the renamed `.1` file). Inherent to size-based log rotation,
      not specific to this implementation.
    """
    try:
        if not path.exists() or path.stat().st_size < max_bytes:
            return
        oldest = path.with_name(f"{path.name}.{backups}")
        if oldest.exists():
            oldest.unlink()
        for i in range(backups - 1, 0, -1):
            src = path.with_name(f"{path.name}.{i}")
            if src.exists():
                src.rename(path.with_name(f"{path.name}.{i + 1}"))
        path.rename(path.with_name(f"{path.name}.1"))
    except OSError:
        pass


def log_audit_event(event_type: str, details: str) -> None:
    """Append an audit event to ~/.claude/logs/audit.log.

    WHY: config_audit.py and other hooks need consistent audit logging.
    Centralized here to ensure uniform format and directory creation.
    """
    from datetime import datetime

    log_dir = Path.home() / ".claude" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "audit.log"
    rotate_log_if_large(log_file)
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


# --- Hook Trigger Telemetry --------------------------------------------------
# WHY: without per-trigger telemetry, hooks like validation_theater_guard and
# evidence_guard cannot prove precision/recall on real sessions. Audit log
# captures timing only — this function records WHAT pattern fired and on
# WHICH sample, so we can compute metrics later (true positives, false
# positives, distribution per session, drift over time).
#
# Cascading-hallucination context (2026-05-03): two consecutive Claude
# sessions made unverified claims about hook events count without grepping
# settings.json. Telemetry would have anchored those claims to actual
# trigger logs instead of guesses.

HOOK_TRIGGERS_LOG = Path.home() / ".claude" / "logs" / "hook_triggers.jsonl"

# WHY: telemetry samples come from real tool output (Bash stdout, MCP responses,
# user prompts). These can contain API keys, tokens, OAuth secrets, AWS creds.
# sanitize_text only truncates — it does NOT scrub secrets. Without redact_secrets
# a leaked AWS key in a Bash error message would land in plaintext inside
# ~/.claude/logs/hook_triggers.jsonl, persisting across sessions and surviving
# `claude --resume` rotations. The patterns below cover the most common shapes
# (per AWS / OpenAI / Anthropic / GitHub / Slack docs); not exhaustive but
# raises the bar from "any string" to "specific known-secret shapes".
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = ()  # populated lazily


def _compile_secret_patterns() -> tuple[tuple[re.Pattern[str], str], ...]:
    """Lazy compile so module import stays cheap; called at first use."""
    return (
        # AWS access key IDs are 20-char [A-Z0-9]; secret access keys 40-char base64.
        (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED-AWS-KEY]"),
        (re.compile(r"aws_secret_access_key\s*=\s*\S+", re.IGNORECASE), "[REDACTED-AWS-SECRET]"),
        # OpenAI / Anthropic / generic sk-* tokens.
        (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "[REDACTED-API-KEY]"),
        (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "[REDACTED-ANTHROPIC-KEY]"),
        # GitHub PATs (classic ghp_, fine-grained github_pat_).
        (re.compile(r"ghp_[A-Za-z0-9]{36}"), "[REDACTED-GITHUB-PAT]"),
        (re.compile(r"github_pat_[A-Za-z0-9_]{82}"), "[REDACTED-GITHUB-PAT]"),
        # Slack tokens (xoxb-, xoxp-, xoxa-).
        (re.compile(r"xox[abprs]-[A-Za-z0-9\-]{10,}"), "[REDACTED-SLACK-TOKEN]"),
        # Generic Bearer tokens, JWTs, basic auth headers.
        (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE), "Bearer [REDACTED]"),
        (re.compile(r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), "[REDACTED-JWT]"),
        (
            re.compile(r"Authorization:\s*Basic\s+\S+", re.IGNORECASE),
            "Authorization: Basic [REDACTED]",
        ),
        # Common env-var assignment for secrets (catch-all for *_TOKEN / *_KEY / *_SECRET).
        (
            re.compile(
                r"(?P<k>(?:[A-Z][A-Z0-9_]*_(?:TOKEN|KEY|SECRET|PASSWORD|PASSWD|PWD)))\s*=\s*\S+"
            ),
            r"\g<k>=[REDACTED]",
        ),
        # ── PII patterns ────────────────────────────────────────────────────────
        # WHY: secrets (tokens/keys) and PII (personal data) are separate GDPR
        # categories. Both must be scrubbed from logs before telemetry or MCP calls.
        # Email addresses.
        (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "[REDACTED-EMAIL]"),
        # Russian mobile / landline: +7 or 8 prefix, various separators.
        (  # Russian mobile / landline pattern split for line length
            re.compile(r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"),
            "[REDACTED-PHONE]",
        ),
        # International phone: +<country> followed by 6-14 digits.
        (re.compile(r"\+(?!7\b)\d{1,3}[\s\-]?\d{6,14}"), "[REDACTED-PHONE]"),
        # Payment card numbers: 4 groups of 4 digits (space or dash separated).
        # WHY: intentionally broad — false positive on a comment is safer than a missed card number.
        (re.compile(r"\b(?:\d{4}[\s\-]?){3}\d{4}\b"), "[REDACTED-CARD]"),
        # Russian passport: 4-digit series + 6-digit number (with optional space).
        (re.compile(r"\b\d{4}\s\d{6}\b"), "[REDACTED-PASSPORT]"),
        # СНИЛС: 123-456-789 01
        (re.compile(r"\b\d{3}-\d{3}-\d{3}\s?\d{2}\b"), "[REDACTED-SNILS]"),
    )


def redact_secrets(text: str) -> str:
    """Replace common secret shapes with [REDACTED-*] tokens.

    WHY: telemetry log samples must not ship secrets. This is a defense-in-depth
    layer — the primary defense is `input_guard` blocking secrets from entering
    tool inputs, but a `Bash` PostToolUse hook can still see raw stderr/stdout
    that includes credentials from misconfigured CI scripts, .env echoes, or
    error tracebacks. Better to over-redact than to leak.

    Not exhaustive — covers AWS, OpenAI/Anthropic/sk-* keys, GitHub PATs,
    Slack tokens, Bearer/JWT/Basic auth, and `*_TOKEN/_KEY/_SECRET/_PASSWORD`
    env-var assignments. Caller stays on Path of Last Resort: never put raw
    secrets in `sample` to begin with; this is a safety net.
    """
    global _SECRET_PATTERNS
    if not _SECRET_PATTERNS:
        _SECRET_PATTERNS = _compile_secret_patterns()
    out = text
    for pattern, replacement in _SECRET_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


def log_hook_trigger(
    hook_name: str,
    trigger_type: str,
    action: str,
    sample: str = "",
    session_id: str | None = None,
) -> None:
    """Record one hook trigger to ~/.claude/logs/hook_triggers.jsonl.

    Parameters
    ----------
    hook_name : str
        Stable hook identifier, e.g. ``"validation_theater_guard"``.
    trigger_type : str
        Pattern category that fired, e.g. ``"perfect_score"``,
        ``"synthetic_data"``, ``"missing_evidence_marker"``.
    action : str
        What the hook did. One of: ``"warning"``, ``"block"``, ``"sanitize"``,
        ``"info"``. Free-form so callers can report richer state, but stick
        to these four for dashboard aggregation.
    sample : str
        Up to 200 chars of the matched text. Truncated automatically — never
        log full tool output (privacy + log size).
    session_id : str | None
        Claude Code session id when available. Pulled from hook stdin payload.

    Behavior
    --------
    * Silent on failure (OSError/etc). Hooks must never break tool calls
      because telemetry directory is unwritable.
    * Recursion-guarded via ``CLAUDE_INVOKED_BY`` env var so subagent runs
      don't double-count the parent's triggers.
    * Atomic append (single ``write``) — concurrent hooks won't interleave.
    """
    import os
    from datetime import datetime

    if os.environ.get("CLAUDE_INVOKED_BY"):
        return

    try:
        HOOK_TRIGGERS_LOG.parent.mkdir(parents=True, exist_ok=True)
        rotate_log_if_large(HOOK_TRIGGERS_LOG)
        # WHY: redact BEFORE truncate. Truncating first could split a secret
        # in half and leave a partial token visible (e.g. "sk-ab" without the
        # tail) — still a fingerprint and still useful for an attacker who
        # can guess the rest. Order is: redact_secrets → sanitize_text.
        safe_sample = sanitize_text(redact_secrets(sample), max_len=200)
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "hook": hook_name,
            "trigger": trigger_type,
            "action": action,
            "sample": safe_sample,
            "session_id": session_id or "",
        }
        # WHY: single write() call = atomic on POSIX/Windows for <= PIPE_BUF
        # bytes. Our JSONL line is ~300 bytes, well under the 4096 limit.
        with open(HOOK_TRIGGERS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        # WHY: telemetry must never break the hook. If logs/ is read-only or
        # disk is full, hooks should keep guarding (warnings still emit).
        pass
