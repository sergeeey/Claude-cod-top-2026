#!/usr/bin/env python3
"""Claude Code status line — model, context, git branch, cost, duration.

Displays a persistent bar at the bottom of the terminal.
Reads JSON session data from stdin, outputs formatted string.
Zero token cost — runs locally as a shell command.

Usage in settings.json:
  "statusLine": {
    "type": "command",
    "command": "python $HOME/.claude/statusline.py"
  }
"""

import json
import subprocess
import sys


def main() -> None:
    data = json.load(sys.stdin)

    model = data.get("model", {}).get("display_name", "?")
    pct = int(data.get("context_window", {}).get("used_percentage") or 0)
    cost = float(data.get("cost", {}).get("total_cost_usd") or 0)
    duration_ms = int(data.get("cost", {}).get("total_duration_ms") or 0)

    # context bar (20 chars wide)
    filled = pct * 20 // 100
    bar = "\u2593" * filled + "\u2591" * (20 - filled)

    # color context by usage: green <50%, yellow 50-70%, red >70%
    if pct >= 70:
        color = "\033[31m"  # red — consider /clear
    elif pct >= 50:
        color = "\033[33m"  # yellow — getting full
    else:
        color = "\033[32m"  # green — plenty of room
    reset = "\033[0m"

    # git branch (best-effort, silent on failure)
    branch = ""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            branch = f" | {result.stdout.strip()}"
    except Exception:
        pass

    # active subagent (shown only while agent is running)
    agent_name = data.get("agent", {}).get("name") or ""
    agent_info = ""
    if agent_name:
        cyan = "\033[36m"
        agent_info = f" | {cyan}agent: {agent_name}{reset}"

    # duration
    mins = duration_ms // 60000
    secs = (duration_ms % 60000) // 1000

    print(
        f"[{model}] {color}{bar} {pct}%{reset}{branch} | ${cost:.2f} | {mins}m{secs}s{agent_info}"
    )


if __name__ == "__main__":
    main()
