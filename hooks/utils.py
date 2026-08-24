"""Shared utilities for Claude Code hooks — backward-compatible facade.

WHY this file is now a facade (2026-08-22, HS-01 in
artifacts/architecture-coupling/hotspots.json): this module used to hold all
36 symbols directly, with a fan-in of 74 (68 hooks + 13 tests importing it).
Every bug here rippled across 60+ hooks, and any interface change had a
repo-wide blast radius. The implementation now lives in hooks/lib/{runtime,
state,discovery,security}.py, grouped by responsibility (hook I/O protocol,
state files/locking, project discovery, sanitization/secrets). This file
re-exports every symbol so every existing `from utils import X` call site
(68 hooks + 13 tests) keeps working unchanged — zero call-site migration
required.

New code should prefer importing directly from
hooks/lib/{runtime,state,discovery,security}.py instead of this facade.

See docs/architecture-coupling/09-target-options.md (Option A) and
docs/architecture-coupling/12-refactoring-roadmap.md (step 5) for the
target design this follows.
"""

from lib.discovery import (
    extract_command_cwd,
    find_file_upward,
    find_project_claude_dir,
    find_project_memory,
    find_scope_fence,
    parse_scope_fence,
    run_git,
)
from lib.runtime import (
    HookInputError,
    emit_hook_result,
    emit_permission_decision,
    extract_tool_response,
    get_mcp_server_name,
    get_tool_input,
    hook_main,
    is_failed_commit,
    log_hook_timing,
    parse_stdin,
    parse_stdin_raw,
)
from lib.security import (
    SENSITIVE_PATTERNS,
    fence_untrusted_content,
    is_safe_path,
    is_sensitive_file,
    parse_env_file_safe,
    redact_secrets,
    sanitize_text,
    secure_append_env_file,
    send_webhook,
    shell_command_tokens,
    shell_statement_tokens,
    split_shell_statements,
)
from lib.state import (
    CB_FAILURE_THRESHOLD,
    CB_RECOVERY_TIMEOUT,
    CB_STATE_FILE,
    HOOK_TRIGGERS_LOG,
    atomic_write_json,
    atomic_write_text,
    file_lock,
    load_json_state,
    log_audit_event,
    log_hook_trigger,
    rotate_log_if_large,
    save_json_state,
)

__all__ = [
    "CB_FAILURE_THRESHOLD",
    "CB_RECOVERY_TIMEOUT",
    "CB_STATE_FILE",
    "HOOK_TRIGGERS_LOG",
    "SENSITIVE_PATTERNS",
    "HookInputError",
    "atomic_write_json",
    "atomic_write_text",
    "emit_hook_result",
    "emit_permission_decision",
    "extract_command_cwd",
    "extract_tool_response",
    "fence_untrusted_content",
    "file_lock",
    "find_file_upward",
    "find_project_claude_dir",
    "find_project_memory",
    "find_scope_fence",
    "get_mcp_server_name",
    "get_tool_input",
    "hook_main",
    "is_failed_commit",
    "is_safe_path",
    "is_sensitive_file",
    "load_json_state",
    "log_audit_event",
    "log_hook_timing",
    "log_hook_trigger",
    "parse_env_file_safe",
    "parse_scope_fence",
    "parse_stdin",
    "parse_stdin_raw",
    "redact_secrets",
    "rotate_log_if_large",
    "run_git",
    "sanitize_text",
    "save_json_state",
    "secure_append_env_file",
    "send_webhook",
    "shell_command_tokens",
    "shell_statement_tokens",
    "split_shell_statements",
]
