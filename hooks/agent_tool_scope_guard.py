#!/usr/bin/env python3
"""PreToolUse(Edit|Write) hook: enforce each agent's declared `tools:` allowlist.

WHY this exists (found via a real boyko_eval run, 2026-07-24, scenario b-02 --
reproduced twice with a tool, not hypothetical): `agents/navigator.md`'s frontmatter
declares `tools: Read, Glob, Grep, Bash, WebSearch, WebFetch, Agent(...)` -- no Edit,
no Write. Its prose Context Boundary says "Must NOT do: implementation edits." Despite
both, a real `Agent(subagent_type='boyko-agent', ...)` invocation made 3 real Edit
calls to `hooks/resource_router.py`, and a second real re-run (after strengthening the
prose boundary) made a DIFFERENT unauthorized edit to the same file. Root cause,
verified by tabulating all 12 live `~/.claude/agents/*.md` files: every agent that
declares a `memory:` field (`user`/`project`/`local`) gets `Write`+`Edit` added to its
runtime tool grant regardless of what its `tools:` line says -- a platform behavior,
not a navigator.md content bug. Prose cannot override a tool grant; only a PreToolUse
hook that can see and deny the actual Edit/Write call can.

Mechanism (confirmed against Claude Code's own hooks docs, code.claude.com/docs/en/
hooks.md, "Common Input Fields" section, fetched directly twice): `agent_id` and
`agent_type` are present on EVERY hook event, not just SubagentStart/SubagentStop,
"when running with --agent or inside a subagent." `agent_type` is the agent's
frontmatter `name:` field (not its filename -- e.g. boyko-agent's file is
navigator.md). This hook reads that field off the PreToolUse(Edit|Write) payload,
resolves the invoking agent's OWN declared `tools:` line from its frontmatter, and
denies the call if Edit/Write is not literally present there.

Scope: Edit/Write/NotebookEdit are gated unconditionally (any use by an agent that
doesn't declare the tool is denied). Bash is gated conditionally -- only when the
command itself looks like a file write (redirect, `tee`, `cp`, `mv`, `sed -i`; see
_BASH_WRITE_PATTERNS) AND the agent's declared tools lack both Write and Edit. Plain
read-only Bash (git/gh checks, grep, ls) is never touched by this hook, for any agent
-- Bash is almost always legitimately declared for exactly that read-only use, so
gating on "is Bash declared" the way Edit/Write are gated would block the hook's own
intended users. permission_policy.py's DANGEROUS_PATTERNS is a separate, broader
Bash-safety gate (dangerous commands for ANY caller); this check is narrower and
specific to per-agent Write/Edit scope, reusing the same simple substring technique
permission_policy.py's own CHAIN_OPERATORS already established for redirect detection
(a bare ">" catches ">", ">>", "1>", "2>" for free; some false positives -- e.g. a
literal ">" inside a quoted argument -- are accepted, same tradeoff made there. A
false DENY here just makes a read-only agent report findings in text instead of
writing a file, same cheap fallback boyko-agent already used correctly the first
time this gap was exercised for real, 2026-08-04.)

Fail-open by design (matches every other hook in this repo's PreToolUse family that
gates on unresolved identity): if `agent_type` is absent (main session, not a
subagent), if no matching agent file can be found, or if the frontmatter can't be
parsed, this hook allows the call rather than guessing. It only denies when it can
positively confirm the invoking agent's own declared scope excludes the tool being
used -- a false ALLOW here is no worse than the status quo before this hook existed;
a false DENY would block a main-session tool call for a reason the main session never
opted into.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from utils import (
    emit_permission_decision,
    get_tool_input,
    hook_main,
    parse_stdin,
    shell_command_tokens,
)

GATED_TOOLS = frozenset({"Edit", "Write", "NotebookEdit"})

# WHY these five, and only these: each is an unambiguous file-write mechanism with
# low false-positive risk. Deliberately excludes anything requiring real shell
# parsing (e.g. distinguishing `dd of=file` from a read-only `dd if=file`) --
# YAGNI until a real gap is found, matching this repo's own stated anti-
# "ceremony before validating it helps" discipline.
_BASH_WRITE_PATTERNS: tuple[str, ...] = (
    ">",  # redirect: >, >>, 1>, 2> -- same technique as permission_policy.py's CHAIN_OPERATORS
    "tee ",
    "cp ",
    "mv ",
    "sed -i",
)

LOG_PATH = Path.home() / ".claude" / "logs" / "agent_tool_scope_guard.jsonl"

_NAME_RE = re.compile(r"^name:\s*(\S+)", re.MULTILINE)
_TOOLS_RE = re.compile(r"^tools:\s*(.+)$", re.MULTILINE)


def _agent_dirs() -> list[Path]:
    """Repo-relative `agents/` (dev/test context) first, then the live install."""
    dirs = []
    cwd_agents = Path.cwd() / "agents"
    if cwd_agents.is_dir():
        dirs.append(cwd_agents)
    live_agents = Path.home() / ".claude" / "agents"
    if live_agents.is_dir() and live_agents not in dirs:
        dirs.append(live_agents)
    return dirs


def _find_declared_tools(agent_type: str) -> set[str] | None:
    """Return the set of tool names literally declared in `<agent>.md`'s frontmatter,
    matched by the frontmatter `name:` field (not filename). None if no match found
    or frontmatter couldn't be parsed -- callers must treat None as "unknown", not
    "empty allowlist", to preserve fail-open behavior.
    """
    for directory in _agent_dirs():
        for md_file in directory.glob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not text.startswith("---"):
                continue
            frontmatter_end = text.find("\n---", 3)
            frontmatter = text[:frontmatter_end] if frontmatter_end != -1 else text[:2000]
            name_match = _NAME_RE.search(frontmatter)
            if not name_match or name_match.group(1).strip() != agent_type:
                continue
            tools_match = _TOOLS_RE.search(frontmatter)
            if not tools_match:
                return None
            # Strip Agent(...) sub-lists and any trailing inline comment before splitting --
            # e.g. "Read, Glob, Agent(builder)" must not count "builder" as a declared tool,
            # and "effort: medium  # comment" (seen in scope-guard.md/skill-suggester.md's own
            # style) must not leak a comment fragment into the tools set.
            raw = re.sub(r"Agent\([^)]*\)", "", tools_match.group(1))
            raw = raw.split("#", 1)[0]
            return {t.strip() for t in raw.split(",") if t.strip()}
    return None


def _bash_looks_like_write(command: str) -> bool:
    """True if `command` contains an unambiguous file-write pattern. Conservative
    by design -- see _BASH_WRITE_PATTERNS' own WHY comment for the accepted
    false-positive tradeoff.

    WHY tokenize before scanning (fixed 2026-08-24, falsification-pilot
    follow-up sweep; refactored the same day onto the shared
    `shell_command_tokens` utility in `hooks/lib/security.py` instead of
    this function's original ad-hoc quote-strip, once the sweep found two
    OTHER hooks -- including `pre_commit_guard.py`, already correct -- had
    independently faced the identical problem): a raw substring scan missed
    `t'e'e file`, `c'p' a b`, `sed -'i' ...` -- bash concatenates adjacent
    quoted/unquoted fragments into one word, so those execute identically to
    `tee file`/`cp a b`/`sed -i ...` but don't contain the literal pattern
    text. A miss here means this function returns False and main()
    immediately allows the call with NO scope check at all -- structurally
    the same full-bypass shape as the permission_policy.py sensitive-path
    finding this fix is modeled on. Independently reproduced before this
    fix: all three example commands above returned False. Real tokenization
    (`shlex.split(posix=True)`, via `shell_command_tokens`) reconstructs
    quote-split words exactly as bash would; joining with a single space is
    still a safe superset scan for substring membership, and this function
    only returns a boolean, so there's no spaced-path-extraction tradeoff to
    worry about (unlike security_verify.py's target-extraction case). Unlike
    permission_policy.py's DANGEROUS_PATTERNS scan, none of
    _BASH_WRITE_PATTERNS embed a chain operator, so the chain-splitting
    variant (`shell_command_tokens`, not the narrower `shell_statement_tokens`)
    is safe to use here without permission_policy.py's `curl | bash`-shaped
    caveat."""
    scan = " ".join(shell_command_tokens(command))
    return any(pattern in scan for pattern in _BASH_WRITE_PATTERNS)


def _log(entry: dict) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            import json

            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    tool_name = data.get("tool_name", data.get("tool", ""))

    bash_write_command: str | None = None
    if tool_name == "Bash":
        command = get_tool_input(data).get("command", "")
        if not _bash_looks_like_write(command):
            # Plain read-only Bash (git/gh checks, grep, ls, ...) -- never gated,
            # for any agent. See module docstring's Scope section for why.
            emit_permission_decision(decision="allow")
            return
        bash_write_command = command
    elif tool_name not in GATED_TOOLS:
        emit_permission_decision(decision="allow")
        return

    agent_type = data.get("agent_type", "")
    if not agent_type:
        # Not inside a subagent (or the field wasn't set) -- never gate main-session
        # tool calls; this hook only enforces per-agent declared scope.
        emit_permission_decision(decision="allow")
        return

    declared = _find_declared_tools(agent_type)
    if declared is None:
        # Unknown agent (plugin-scoped name, no matching file, unparsable frontmatter)
        # -- fail open, don't guess.
        emit_permission_decision(decision="allow")
        return

    if bash_write_command is not None:
        # The permission being checked is Write/Edit capability (the thing that
        # actually authorizes file mutation), not literal "Bash" -- Bash itself is
        # almost always declared, for legitimate read-only use.
        if "Write" in declared or "Edit" in declared:
            emit_permission_decision(decision="allow")
            return
        effective_tool = "Bash (file-write pattern)"
    else:
        if tool_name in declared:
            emit_permission_decision(decision="allow")
            return
        effective_tool = tool_name

    reason = (
        f"[agent-tool-scope-guard] '{agent_type}' called {effective_tool}, but its own "
        f"frontmatter tools: line does not declare Write/Edit (declared: "
        f"{sorted(declared) or 'none'}). Tool access from a memory: field does not "
        "imply authorization -- denied. Route this as a recommendation to `builder`/"
        "the orchestrator instead."
    )
    _log(
        {
            "ts": datetime.now(UTC).isoformat(),
            "agent_type": agent_type,
            "tool_name": tool_name,
            "bash_command": bash_write_command,
            "declared_tools": sorted(declared),
            "session_id": data.get("session_id"),
        }
    )
    emit_permission_decision(decision="deny", reason=reason)


if __name__ == "__main__":
    # WHY fail_closed=False: unlike permission_policy.py (which exists specifically to
    # deny known-dangerous Bash), this hook's job is a narrow, additive scope check on
    # top of whatever the platform already grants. If IT crashes or times out, falling
    # back to the platform's existing (pre-this-hook) behavior is strictly safer than
    # blocking every Edit/Write call in the whole session on this hook's own failure.
    hook_main(main, fail_closed=False)
