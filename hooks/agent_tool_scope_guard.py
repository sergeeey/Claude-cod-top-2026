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

Scope, deliberately narrow: only Edit/Write/NotebookEdit are gated (the tools that
directly mutate files). Bash-based file mutation (e.g. `echo >> file`) is a known,
separate, adjacent gap -- not covered here; permission_policy.py's DANGEROUS_PATTERNS
is the existing (also incomplete) defense for that surface. Widening this hook to Bash
is future work, not bundled into this fix.

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

from utils import emit_permission_decision, hook_main, parse_stdin

GATED_TOOLS = frozenset({"Edit", "Write", "NotebookEdit"})

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
    if tool_name not in GATED_TOOLS:
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

    if tool_name in declared:
        emit_permission_decision(decision="allow")
        return

    reason = (
        f"[agent-tool-scope-guard] '{agent_type}' called {tool_name}, but its own "
        f"frontmatter tools: line does not declare {tool_name} (declared: "
        f"{sorted(declared) or 'none'}). Tool access from a memory: field does not "
        "imply authorization -- denied. Route this as a recommendation to `builder`/"
        "the orchestrator instead."
    )
    _log(
        {
            "ts": datetime.now(UTC).isoformat(),
            "agent_type": agent_type,
            "tool_name": tool_name,
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
