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
from datetime import UTC, datetime


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

    # project name + git branch (best-effort, silent on failure)
    project = ""
    branch = ""
    try:
        # WHY: git rev-parse gives repo root → folder name = project name.
        # Helps distinguish terminals when multiple projects are open.
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            import os

            project_name = os.path.basename(result.stdout.strip())
            bold = "\033[1m"
            project = f" {bold}{project_name}{reset} |"

        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            branch = f" {result.stdout.strip()}"
    except Exception:
        pass

    # active subagent (shown only while agent is running)
    agent_name = data.get("agent", {}).get("name") or ""
    agent_info = ""
    if agent_name:
        cyan = "\033[36m"
        agent_info = f" | {cyan}agent: {agent_name}{reset}"

    # rate limits (Pro/Max only — absent for API users)
    rate_info = ""
    rl = data.get("rate_limits", {})
    if rl:
        parts = []
        for window, label in (("five_hour", "5h"), ("seven_day", "7d")):
            w = rl.get(window, {})
            used = w.get("used_percentage")
            resets_ts = w.get("resets_at")
            if used is None:
                continue
            used = int(used)
            # color: green <60%, yellow 60-85%, red >85%
            if used >= 85:
                rl_color = "\033[31m"  # red
            elif used >= 60:
                rl_color = "\033[33m"  # yellow
            else:
                rl_color = "\033[32m"  # green
            # time until reset (best-effort)
            reset_str = ""
            if resets_ts:
                try:
                    resets_dt = datetime.fromtimestamp(int(resets_ts), tz=UTC)
                    delta = resets_dt - datetime.now(tz=UTC)
                    total_mins = max(0, int(delta.total_seconds()) // 60)
                    h, m = divmod(total_mins, 60)
                    reset_str = f"/{h}h{m:02d}m" if h else f"/{m}m"
                except Exception:
                    pass
            parts.append(f"{rl_color}{label}:{used}%{reset_str}{reset}")
        if parts:
            rate_info = " | " + " ".join(parts)

    # duration
    mins = duration_ms // 60000
    secs = (duration_ms % 60000) // 1000

    status = (
        f"[{model}]{project} {color}{bar} {pct}%{reset}"
        f" |{branch} | ${cost:.2f} | {mins}m{secs}s{agent_info}{rate_info}"
    )
    print(status)


if __name__ == "__main__":
    main()
