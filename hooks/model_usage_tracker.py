#!/usr/bin/env python3
"""PostToolUse hook — append-only tool usage metrics log.

WHY token proxy instead of real tokens: Anthropic API token counts are in
the HTTP response body, not passed to PostToolUse hooks. Response byte size
is the best available proxy (1 token ≈ 4 bytes, ~20% accuracy on short calls).

Log format: ~/.claude/logs/model_usage.jsonl (one JSON line per tool call).
Latency: ~0.2 ms per call (file append) — negligible vs API round-trips.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

LOG_FILE = Path.home() / ".claude" / "logs" / "model_usage.jsonl"


def main() -> None:
    # WHY: prevent recursion when hook fires inside a subagent invocation.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if not isinstance(data, dict):
        sys.exit(0)

    tool_name = data.get("tool_name", "unknown")
    session_id = str(data.get("session_id", ""))[:8]
    tool_response = data.get("tool_response", {})
    tool_input = data.get("tool_input", {})

    # WHY proxy: real tokens not available in hook scope.
    response_bytes = len(json.dumps(tool_response, ensure_ascii=False))
    input_bytes = len(json.dumps(tool_input, ensure_ascii=False))

    entry = {
        "ts": round(time.time(), 3),
        "sid": session_id,
        "tool": tool_name,
        "resp_bytes": response_bytes,
        "inp_bytes": input_bytes,
        # Rough proxy: 1 token ≈ 4 bytes. Accuracy ±20% for short outputs.
        "est_out_tok": response_bytes // 4,
        "est_in_tok": input_bytes // 4,
    }

    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # fail-open: never block user workflow


if __name__ == "__main__":
    main()
