#!/usr/bin/env python3
"""SubagentStart/SubagentStop hook: agent lifecycle management.

WHY: Agents need project context at start and cleanup at stop.
Manual setup is error-prone; automated lifecycle ensures consistency.

Usage: python agent_lifecycle.py --start  (for SubagentStart)
       python agent_lifecycle.py --stop   (for SubagentStop)
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

from utils import emit_hook_result, find_project_memory, parse_stdin


def on_start(data: dict) -> None:
    """Inject project context when agent starts."""
    agent_type = data.get("agent_type", "unknown")

    # WHY: load activeContext.md so the agent knows current project state
    memory = find_project_memory()
    if memory and memory.exists():
        try:
            content = memory.read_text(encoding="utf-8")[:2000]
            emit_hook_result(
                "SubagentStart",
                f"[agent-lifecycle] Project context for {agent_type}:\n{content}",
            )
        except OSError:
            pass


def on_stop(data: dict) -> None:
    """Cleanup when agent stops."""
    agent_type = data.get("agent_type", "unknown")
    agent_id = data.get("agent_id", "unknown")

    # WHY: log agent completion for debugging and audit trail
    log_dir = Path.home() / ".claude" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "agent_lifecycle.log"

    try:
        timestamp = datetime.now(UTC).isoformat()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | STOP | {agent_type} | {agent_id}\n")
    except OSError:
        pass


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    # WHY: use explicit --start/--stop flag from settings.json command
    # instead of fragile payload heuristic. This is robust against
    # Claude Code protocol changes that add new fields.
    if "--stop" in sys.argv:
        on_stop(data)
    else:
        # WHY: default to on_start for backward compatibility
        on_start(data)


if __name__ == "__main__":
    main()
