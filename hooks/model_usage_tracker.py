#!/usr/bin/env python3
"""PostToolUse hook — track per-model token usage.

Increments weekly counter for the current model based on tokens reported
in the hook input. Resets weekly counter automatically every 7 days.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

USAGE_FILE = Path.home() / ".claude" / "memory" / "model_usage.json"
WEEKLY_RESET_DAYS = 7


def main() -> None:
    """Parse hook stdin, increment usage for active model, persist atomically."""
    # WHY: prevent recursion when hook fires inside a subagent invocation.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # WHY: token info may live under "tokens" or under "usage.total_tokens".
    tokens_used = 0
    if isinstance(data, dict):
        if "tokens" in data:
            try:
                tokens_used = int(data.get("tokens", 0))
            except (TypeError, ValueError):
                tokens_used = 0
        elif isinstance(data.get("usage"), dict):
            try:
                tokens_used = int(data["usage"].get("total_tokens", 0))
            except (TypeError, ValueError):
                tokens_used = 0

    if tokens_used <= 0:
        sys.exit(0)

    model = os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-4-5"

    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        usage = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
        usage = {"weekly": {}, "weekly_reset_at": datetime.now().isoformat()}

    # WHY: weekly counter resets after 7 days from last reset timestamp.
    try:
        reset_at = datetime.fromisoformat(usage.get("weekly_reset_at", ""))
        if datetime.now() - reset_at > timedelta(days=WEEKLY_RESET_DAYS):
            usage["weekly"] = {}
            usage["weekly_reset_at"] = datetime.now().isoformat()
    except (ValueError, TypeError, KeyError):
        usage["weekly_reset_at"] = datetime.now().isoformat()

    usage.setdefault("weekly", {})
    usage["weekly"][model] = int(usage["weekly"].get(model, 0)) + tokens_used

    # WHY: atomic write avoids corrupting state if process is killed mid-write.
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(USAGE_FILE.parent), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(usage, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, USAGE_FILE)
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
