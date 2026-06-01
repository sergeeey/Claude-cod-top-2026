#!/usr/bin/env python
"""Context Asymmetry Hook for adversarial agents.

Event: PreToolUse(Agent)

Purpose:
  When orchestrator spawns adversarial reviewer agents (skeptic, skeptic-auditor,
  reviewer), Claude Code automatically inherits the orchestrator's reasoning chain
  and system context. This creates agreeableness bias — the "skeptic" sees WHY
  the artifact was built and tends to validate it.

  Per rules/falsification-ladder.md Context Asymmetry Rule and
  rules/doubt-driven-development.md (FL skeptic protocol), adversarial agents
  MUST receive ONLY:
    - explicit prompt
    - artifact references (claim.md + raw code)
  And must NOT receive:
    - session reasoning chain
    - prior agent outputs
    - "background context"

Mechanism:
  Claude Code does NOT expose an API to rewrite Agent tool payload from a
  PreToolUse hook. We therefore INJECT a system warning via additionalContext
  (stdout JSON protocol) instructing the orchestrator and the spawned agent
  about the asymmetry requirement, and we log every adversarial spawn for
  audit.

  This is a soft enforcement: warns + logs + advises. Hard enforcement would
  require a Claude Code SDK feature that does not exist as of this writing.

Recursion guard:
  If CLAUDE_INVOKED_BY is set, the current process is already nested inside
  an agent execution — skip silently to avoid recursive triggering.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- Configuration ------------------------------------------------------------

ADVERSARIAL_AGENTS = frozenset(
    {
        "skeptic",
        "skeptic-auditor",
        "reviewer",
    }
)

LOG_PATH = Path.home() / ".claude" / "memory" / "context_asymmetry_log.jsonl"

WARNING_TEMPLATE = (
    "[CONTEXT-ASYMMETRY GUARD] Spawning adversarial agent '{subagent}'. "
    "Per rules/falsification-ladder.md: this agent must receive ONLY the "
    "explicit prompt and artifact references (claim.md, raw code). "
    "Do NOT pass session reasoning chain, success logs, agent's own "
    "confidence statements, or 'background context' about why the approach "
    "was chosen. Asymmetric context = independent falsification = stronger "
    "review. Agreeableness bias is the failure mode."
)

# --- Helpers ------------------------------------------------------------------


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()


def _log(entry: dict) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        # Logging must never block the tool call.
        pass


def _extract_subagent(tool_input: dict) -> str:
    # Claude Code Agent tool uses either "subagent_type" or "agent_type".
    for key in ("subagent_type", "agent_type", "agent", "type"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value.strip().lower()
    return ""


# --- Main ---------------------------------------------------------------------


def main() -> int:
    # Recursion guard: if we're nested in an agent invocation, skip.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        return 0

    try:
        raw = sys.stdin.read()
        if not raw.strip():
            _emit({"continue": True})
            return 0
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        # Malformed payload — never block the tool, just exit clean.
        _emit({"continue": True})
        return 0

    tool_name = data.get("tool_name") or data.get("tool") or ""
    if tool_name != "Agent":
        _emit({"continue": True})
        return 0

    tool_input = data.get("tool_input") or data.get("input") or {}
    if not isinstance(tool_input, dict):
        _emit({"continue": True})
        return 0

    subagent = _extract_subagent(tool_input)
    if subagent not in ADVERSARIAL_AGENTS:
        # Silent for non-adversarial agents (builder, navigator, explorer, ...).
        _emit({"continue": True})
        return 0

    # Log the spawn for audit / metrics.
    _log(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "adversarial_agent_spawn",
            "subagent": subagent,
            "session_id": data.get("session_id"),
            "cwd": data.get("cwd"),
            "prompt_preview": (tool_input.get("prompt") or "")[:200],
        }
    )

    # Emit the asymmetry warning via additionalContext so orchestrator + agent
    # both see the requirement.
    _emit(
        {
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": WARNING_TEMPLATE.format(subagent=subagent),
            },
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
