#!/usr/bin/env python3
"""SessionStart hook — recommend best model based on current usage.

Does NOT auto-switch (Claude Code session model is set by user / CLI flag).
Instead emits a clear recommendation via additionalContext when usage is high.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

USAGE_FILE = Path.home() / ".claude" / "memory" / "model_usage.json"
TOOL = Path.home() / ".claude" / "tools" / "model-status.py"


def main() -> None:
    # WHY: prevent recursion when this hook fires inside a subagent's SessionStart
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    if not TOOL.exists():
        sys.exit(0)

    # Get usage snapshot from CLI tool
    try:
        result = subprocess.run(
            [sys.executable, str(TOOL), "--json"], capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            sys.exit(0)
        data = json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError, ValueError, OSError):
        sys.exit(0)

    # Build warning if any model > 80%
    warnings = []
    suggestions = []
    for model, status in data.items():
        if status.get("weekly_pct", 0) >= 80:
            short = model.split("-")[1].capitalize()
            warnings.append(f"{short}: {status['weekly_pct']:.0f}%")

    if not warnings:
        sys.exit(0)  # all good, stay silent

    # Get best alternative for default task type
    try:
        sug_result = subprocess.run(
            [sys.executable, str(TOOL), "--suggest", "implement"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if sug_result.returncode == 0:
            best = sug_result.stdout.strip().split("#")[0].strip()
            suggestions.append(f"recommended: /model {best.split('-')[1]}")
    except subprocess.SubprocessError:
        pass

    msg = f"[model-router] ⚠️ Usage high: {', '.join(warnings)}"
    if suggestions:
        msg += f" — {'; '.join(suggestions)}"

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": msg,
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
