#!/usr/bin/env python3
"""TeammateIdle hook: redistribute tasks when a teammate finishes early.

WHY: In Agent Teams, idle teammates waste resources. Auto-redistribution
ensures all team members stay productive until the task is complete.
"""

from datetime import UTC, datetime
from pathlib import Path

from utils import emit_hook_result, parse_stdin


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    agent_type = data.get("agent_type", "unknown")
    agent_id = data.get("agent_id", "unknown")

    # WHY: log idle events for team performance analysis
    log_dir = Path.home() / ".claude" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "team_events.log"

    try:
        timestamp = datetime.now(UTC).isoformat()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | IDLE | {agent_type} | {agent_id}\n")
    except OSError:
        pass

    # WHY: emit context so the orchestrator knows a teammate is available
    emit_hook_result(
        "TeammateIdle",
        f"[team-rebalance] Teammate {agent_type} ({agent_id}) is idle. "
        "Consider assigning remaining tasks or merging results.",
    )


if __name__ == "__main__":
    main()
