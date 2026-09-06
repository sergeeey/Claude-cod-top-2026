"""Hook I/O protocol and lifecycle for Claude Code hooks.

WHY this file exists (split from hooks/utils.py, HS-01 in
artifacts/architecture-coupling/hotspots.json): utils.py's fan-in was 74
(68 hooks + 13 tests import it directly), making every bug here ripple
across 60+ hooks. Splitting by responsibility localizes blast radius.
See hooks/utils.py for the facade that keeps `from utils import X` working.

============================================================
BLOCKING PROTOCOL — which mechanism to use in which hook type
============================================================
PreToolUse hooks:
  → emit_permission_decision() from this module
  Correct files: pre_commit_guard.py, security_verify.py, input_guard.py, redact.py

  WHY NOT bare top-level {"decision": "block", ...} or {"tool_input": ...}:
  a live behavioral test (2026-07-01, see tests/test_pretooluse_output_schema.py
  and tests/test_redact_mcp_behavior.py) proved that legacy top-level
  `decision: block` still blocks (Claude Code kept it for backward compat),
  but legacy top-level `tool_input` mutation is SILENTLY DROPPED — the
  original unmodified tool_input reaches the downstream tool regardless of
  what a hook prints. This was a real, confirmed bug in redact.py's PII
  redaction: fake secrets written through an MCP tool came out unredacted.
  `hookSpecificOutput.updatedInput` is the only path proven to work.

PostToolUse hooks:
  → the tool has ALREADY run — no exit code can undo or block it. Per
    Claude Code's own hooks reference (verified 2026-08-29 against
    code.claude.com/docs/en/hooks): "PostToolUse — Can block? No — Shows
    stderr to Claude; the tool already ran." Exit code 2 is the STRONGEST
    available signal (surfaces stderr to Claude prominently) but is a
    strong warning, not a block. Exit code 1 is a plain non-blocking error
    with no special surfacing semantics.
  → sys.exit(2) — current convention for hooks that need Claude's attention.
    Correct files: skeptic_auto_trigger.py, goal_stub_detector.py.
  → sys.exit(1) — legacy pattern, now migrated off (was in
    validation_theater_guard.py, fixed 2026-08-29 to exit(2)).

  CORRECTION 2 (same date): the original list of "correct files" for this
  legacy exit(1) pattern also cited mcp_circuit_breaker_post.py -- checked
  and that file never called sys.exit(1) at all (class: info/OBSERVE, pure
  telemetry, falls through to an implicit exit(0)). That citation was
  already stale before this fix; removed rather than "corrected forward".

  CORRECTION (2026-08-29): this docstring previously said PostToolUse
  sys.exit(1) "signals Claude Code to suppress/flag the tool result" — that
  claim did not match Claude Code's documented behavior (exit 1 has no
  defined special semantics on PostToolUse) and predates this repo's own
  migration of some hooks to exit(2). Found via an external audit's specific,
  tool-verified claim; confirmed independently against the live docs before
  correcting here — see PR fixing this for the full verification trail.

WHY two mechanisms: Claude Code SDK uses different signals per hook type.
PreToolUse: exit code 2 blocks (this repo standardizes on the JSON
hookSpecificOutput path via emit_permission_decision() instead of a bare
exit code). PostToolUse: no exit code blocks; exit code is only a signal
of how loudly the failure is surfaced to Claude.
Do NOT mix mechanisms across hook types — it will silently fail.
============================================================
"""

import json
import re
import sys
from collections.abc import Callable

from .state import log_audit_event

# WHY (Y-17 pilot, 2026-09-06 — tooling-eval/LEDGER.md in sergeeey/Y-17-100-gipotez): three
# UserPromptSubmit keyword hooks (routing_floor_classifier, resource_router,
# submission_gate_guard) fired 9/9 times as NOISE in one session; 4 of those firings were on
# text the USER never wrote — harness-injected <system-reminder> / <task-notification> blocks
# (agent completion reports containing words like "hypothesis", "Falsif", "ready"). The
# hooks classify `data["prompt"]` verbatim and cannot tell user text from harness text.
_NON_USER_BLOCKS = re.compile(
    r"<system-reminder>.*?</system-reminder>|<task-notification>.*?</task-notification>",
    re.DOTALL | re.IGNORECASE,
)
_NON_USER_MARKER = "[SYSTEM NOTIFICATION - NOT USER INPUT]"


def strip_non_user_content(prompt: str) -> str:
    """Return only the user-authored part of a UserPromptSubmit prompt.

    Removes harness-injected ``<system-reminder>…</system-reminder>`` and
    ``<task-notification>…</task-notification>`` blocks, and anything from an unwrapped
    ``[SYSTEM NOTIFICATION - NOT USER INPUT]`` marker onward. Keyword classifiers should
    run on the result, never on the raw prompt. May return "" — callers already exit on
    an empty prompt, so a pure-notification event correctly injects nothing.
    """
    if not prompt:
        return ""
    text = _NON_USER_BLOCKS.sub("", prompt)
    if _NON_USER_MARKER in text:
        text = text.split(_NON_USER_MARKER, 1)[0]
    return text.strip()


class HookInputError(Exception):
    """Raised by parse_stdin(strict=True) when stdin can't be parsed as a
    JSON object. See parse_stdin() docstring for why this exists."""


def parse_stdin(strict: bool = False) -> dict:
    """Parse JSON from stdin (Claude Code hook protocol).

    Default (strict=False): returns empty dict on parse failure — hooks
    should exit gracefully. WHY: Every advisory hook does this identically.
    Centralizing prevents inconsistent error handling (some used EOFError,
    some didn't).

    strict=True: raises HookInputError instead of returning {}. WHY (issue
    #195, following the F-10 fix in input_guard.py, external audit
    2026-07-15): a security-critical PreToolUse hook (e.g. pre_vault_write.py)
    that does `if not parse_stdin(): return` cannot distinguish "nothing to
    check" from "could not parse the input at all" — both look identical
    (falsy {}). That silently defeats hook_main(fail_closed=True): no
    exception ever propagates, so fail_closed's timeout/crash handling never
    sees the failure. Security-critical callers should use strict=True and
    catch HookInputError explicitly to emit their own deny decision, exactly
    like a genuine policy violation would.
    """
    try:
        result = json.load(sys.stdin)
        if not isinstance(result, dict):
            if strict:
                raise HookInputError(f"stdin JSON is not an object: {type(result).__name__}")
            return {}
        return result
    except (json.JSONDecodeError, EOFError, ValueError) as e:
        if strict:
            raise HookInputError(str(e)) from e
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


def get_mcp_server_name(tool_name: str) -> str | None:
    """Extract MCP server name from tool name (mcp__<server>__<method>).

    WHY: Duplicated in mcp_circuit_breaker.py and mcp_circuit_breaker_post.py.
    """
    parts = tool_name.split("__")
    if len(parts) >= 3 and parts[0] == "mcp":
        return parts[1]
    return None


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


def hook_main(fn: "Callable[[], None]", timeout: int = 30, fail_closed: bool = False) -> None:
    """Run hook main() with a hard timeout.

    WHY: Hooks that hang (network partition during MCP call, slow git)
    would block Claude Code indefinitely. signal.alarm is Unix-only,
    so we use a daemon thread which is killed when the process exits.

    fail_closed (F-10, external audit 2026-07-15): default is still fail-open
    (exit 0) — correct for advisory hooks (notifications, telemetry) whose
    unavailability costs nothing. But a hook whose actual JOB is to DENY
    dangerous actions (input_guard, mcp_response_guard) previously fail-opened
    on timeout/crash exactly like every advisory hook — a resource-exhaustion
    condition or unusually slow environment could silently ALLOW the very
    tool call the hook exists to block, with zero indication beyond a stderr
    line nobody reads in the moment. fail_closed=True makes those specific
    hooks emit an explicit `deny` permissionDecision instead of allowing by
    omission when they can't finish. Opt-in, not default: most hooks in this
    repo are advisory and must stay fail-open, matching every other
    fail-open convention documented in hooks/CLAUDE.md.
    """
    import os
    import threading

    done = threading.Event()
    exc: list[BaseException] = []
    exit_code: list[int] = []

    def _target() -> None:
        try:
            fn()
        except SystemExit as e:
            # CORRECTED (2026-08-29, /boyko-project-radar bottleneck #2 fix +
            # independent reviewer catch): this used to be a bare `pass`,
            # silently discarding fn()'s exit code entirely. SystemExit
            # raised inside a thread only terminates that thread, not the
            # process -- previously, ANY fn() that called sys.exit(N) for
            # N != 0 as its OWN signal (not via emit_permission_decision)
            # had that code silently replaced with the process's default
            # exit(0) once wrapped in hook_main. Confirmed as a live
            # regression in goal_stub_detector.py: sys.exit(2) (its post-hoc
            # warning signal to Claude -- PostToolUse, so it was never a
            # true block to begin with) became exit(0) after wrapping,
            # defeating the hook entirely, not just on crash. Now captured
            # and propagated below instead of discarded.
            code = e.code
            if isinstance(code, int):
                exit_code.append(code)
            elif code is None:
                exit_code.append(0)
            else:
                # WHY print here (P2, independent reviewer catch): a real
                # `sys.exit("message")` prints the message to stderr before
                # exiting 1 -- matching that so a future fn() using this
                # form doesn't lose its diagnostic. No hook currently does
                # this (verified via repo-wide grep), so this branch is
                # unreached today; kept correct for when one does.
                print(str(code), file=sys.stderr)
                exit_code.append(1)
        except Exception as e:
            exc.append(e)
        finally:
            done.set()

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    fired = done.wait(timeout=timeout)

    if not fired:
        print(f"[hook-timeout] timed out after {timeout}s, exiting.", file=sys.stderr)
        if fail_closed:
            emit_permission_decision(
                decision="deny",
                reason=f"[hook-timeout] security hook timed out after {timeout}s — failing closed.",
            )
        os._exit(0)  # hard exit — daemon thread is killed automatically

    if exc:
        print(f"[hook-error] unhandled exception: {exc[0]}", file=sys.stderr)
        if fail_closed:
            emit_permission_decision(
                decision="deny",
                reason=f"[hook-error] security hook crashed ({exc[0]}) — failing closed.",
            )
            os._exit(0)  # permissionDecision already communicates the block
        else:
            os._exit(1)

    if exit_code and exit_code[0] != 0:
        os._exit(exit_code[0])  # propagate fn()'s own exit code (e.g. PostToolUse exit(2))
    # exit_code == [0] or fn() returned without calling sys.exit: fall through,
    # process exits 0 naturally -- no change from prior behavior for this case.


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
