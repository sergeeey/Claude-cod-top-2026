"""Structural check: no hook may be registered under a Claude Code hook event
that can never fire given this repo's own static permissions configuration.

WHY (SEC-03, 2026-07-18): hooks/permission_policy.py was registered under
PermissionRequest, whose docs (code.claude.com/docs/en/hooks, verified via
WebFetch) state it fires only "when a permission dialog appears". This
repo's own permissions.allow has a blanket rule for every built-in tool
(Bash(*), Read(*), ...) and, at the time of the bug, zero `ask` rules --
meaning no permission dialog could EVER appear, for ANY tool, so the hook
silently never ran (including the entire DANGEROUS_PATTERNS deny list).
Caught only by manual cross-referencing of primary-source docs against
settings.json; nothing in CI would have caught it, and nothing would catch
a recurrence with a different hook/tool pairing. This test generalizes the
finding into a standing structural gate rather than a one-off fix.

Reachability rule (deterministic, computed from settings.json's own static
`permissions` block -- no runtime command-matching needed): a PermissionRequest
hook registered with matcher M is DEAD for tool T if T is named or implied by
M, permissions.allow has an unconditional rule for T (bare `T` or `T(*)`),
and permissions.ask has NO rule mentioning T at all. Per Claude Code's own
precedence (deny > ask > allow -- code.claude.com/docs/en/permissions), only
a matching ask/deny rule can force a dialog once an unconditional allow rule
exists for T; with zero ask rules for T, no call to T can ever need one, so
PermissionRequest structurally cannot fire for it.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "hooks" / "settings.json"

# WHY this list, not introspecting Claude Code itself: these are the
# built-in tool names this repo's own permissions.allow/deny blocks
# reference (see hooks/settings.json's own arrays) -- an MCP tool
# (mcp__server__tool) is never blanket-allowed here, so it can never be
# flagged dead by this check regardless of whether it's enumerated.
ALL_BUILTIN_TOOLS = (
    "Bash",
    "Read",
    "Write",
    "Edit",
    "Grep",
    "Glob",
    "Task",
    "WebFetch",
    "WebSearch",
    "Skill",
    "NotebookEdit",
    "Agent",
    "TaskCreate",
    "TaskUpdate",
    "TaskList",
    "TaskGet",
)


def _load_settings() -> dict:
    return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))


def _is_blanket_allow(rule: str, tool: str) -> bool:
    """True if `rule` is an unconditional allow for `tool` -- bare `Tool` or
    `Tool(*)`. A scoped rule like `Bash(git status)` does NOT count: it only
    ever allows ONE specific call, so a dialog can still appear for every
    other call to that tool."""
    return rule == tool or rule == f"{tool}(*)"


def _has_ask_rule_for(ask_rules, tool: str) -> bool:
    """True if ANY ask rule could ever match a call to `tool` -- a bare
    `Tool` rule, or a scoped `Tool(...)` rule. Even one matching ask rule
    means a dialog CAN appear for that tool, so PermissionRequest is not
    fully dead for it (conservative: avoids flagging a hook that is merely
    rarely triggered as if it were structurally impossible to trigger)."""
    return any(r == tool or r.startswith(f"{tool}(") for r in ask_rules)


def _matcher_tool_names(matcher: str) -> list:
    """Expand a hook matcher into the tool name(s) it targets. Empty string
    is Claude Code's own convention for "matches every tool" (see e.g. this
    repo's Notification/UserPromptSubmit registrations, matcher: "")."""
    if matcher == "":
        return list(ALL_BUILTIN_TOOLS)
    return [m.strip() for m in matcher.split("|") if m.strip()]


def dead_tools_for_permission_request(settings: dict, matcher: str) -> list:
    """Return the subset of `matcher`'s target tools for which a
    PermissionRequest hook is guaranteed to never fire, given `settings`'s
    static permissions.allow/ask arrays."""
    perms = settings.get("permissions", {})
    allow_rules = perms.get("allow", [])
    ask_rules = perms.get("ask", [])

    dead = []
    for tool in _matcher_tool_names(matcher):
        has_blanket_allow = any(_is_blanket_allow(r, tool) for r in allow_rules)
        if has_blanket_allow and not _has_ask_rule_for(ask_rules, tool):
            dead.append(tool)
    return dead


class TestNoDeadPermissionRequestHooks:
    def test_no_hook_registered_under_permissionrequest_is_structurally_dead(self):
        settings = _load_settings()
        pr_entries = settings.get("hooks", {}).get("PermissionRequest", [])

        dead_registrations = []
        for entry in pr_entries:
            matcher = entry.get("matcher", "")
            dead_tools = dead_tools_for_permission_request(settings, matcher)
            if dead_tools:
                for h in entry.get("hooks", []):
                    dead_registrations.append(
                        f"{h.get('command', '?')} (matcher={matcher!r}, "
                        f"dead for: {', '.join(dead_tools)})"
                    )

        assert not dead_registrations, (
            "Hook(s) registered under PermissionRequest that can never fire, "
            "given this repo's own permissions.allow/ask (SEC-03 regression "
            "class):\n" + "\n".join(f"  - {d}" for d in dead_registrations) + "\n"
            "PermissionRequest only fires when a permission dialog appears "
            "(code.claude.com/docs/en/hooks); with a blanket allow rule and no "
            "ask rule for the affected tool(s), no dialog is ever shown. "
            "Register the hook under PreToolUse instead -- it fires "
            "unconditionally and can override an allow rule via "
            "hookSpecificOutput.permissionDecision (see hooks/permission_policy.py)."
        )

    def test_reachability_helper_flags_the_original_sec03_shape(self):
        """Regression pin: reconstruct the exact pre-fix configuration
        (Bash(*) allow, zero ask rules, PermissionRequest matcher="") and
        assert the helper flags Bash as dead -- proves this check would have
        caught SEC-03 before merge, not just after the fact."""
        broken_settings = {"permissions": {"allow": ["Bash(*)"], "ask": [], "deny": []}}
        dead = dead_tools_for_permission_request(broken_settings, "")
        assert "Bash" in dead

    def test_reachability_helper_does_not_false_positive_on_scoped_allow(self):
        """A narrow allow rule (not a blanket one) must NOT be flagged --
        `Bash(git status)` still lets every other Bash command reach a
        dialog, so PermissionRequest is genuinely reachable there."""
        scoped_settings = {"permissions": {"allow": ["Bash(git status)"], "ask": [], "deny": []}}
        dead = dead_tools_for_permission_request(scoped_settings, "")
        assert "Bash" not in dead

    def test_reachability_helper_respects_an_existing_ask_rule(self):
        """If an ask rule exists for the tool, PermissionRequest CAN still
        fire for calls that rule matches -- not dead."""
        settings_with_ask = {
            "permissions": {"allow": ["Bash(*)"], "ask": ["Bash(rm *)"], "deny": []}
        }
        dead = dead_tools_for_permission_request(settings_with_ask, "")
        assert "Bash" not in dead

    def test_reachability_helper_handles_missing_ask_key(self):
        """permissions.ask is optional in settings.json (this repo doesn't
        define one) -- the helper must not crash on its absence."""
        settings_no_ask_key = {"permissions": {"allow": ["Bash(*)"], "deny": []}}
        dead = dead_tools_for_permission_request(settings_no_ask_key, "Bash")
        assert dead == ["Bash"]
