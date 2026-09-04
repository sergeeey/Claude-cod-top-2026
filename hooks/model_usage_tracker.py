#!/usr/bin/env python3
"""PostToolUse hook — append-only tool usage metrics log.

WHY token proxy for most tool types: Anthropic API token counts are in the
HTTP response body, not passed to PostToolUse hooks in general. Response
byte size is the best available proxy (1 token ≈ 4 bytes, ~20% accuracy on
short calls).

WHY `Agent`-type calls are the exception (GitHub issue #227, verified
2026-07-24 via a live, marker-gated, reversible diagnostic on this exact
hook): `tool_response` for an `Agent` PostToolUse event already carries
`resolvedModel`/`totalTokens`/`totalDurationMs`/`totalToolUseCount` —
exact numbers, not proxies. Discarding them in favor of the byte estimate
was an unnecessary approximation for this one tool type. When present,
these fields are logged directly instead of the proxy; the proxy fields
are still computed and kept for every entry (including `Agent`) so
existing consumers (`scripts/otel_exporter.py`) keep working unchanged.
Unverified/out of scope: whether the same exact fields exist for other
tool types (`Bash`/`Read`/`WebFetch`) — this fix is `Agent`-specific.

Log format: ~/.claude/logs/model_usage.jsonl (one JSON line per tool call).
Latency: ~0.2 ms per call (file append) — negligible vs API round-trips.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from lib.state import rotate_log_if_large

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
        # Kept for every entry (even when exact fields are also present
        # below) so existing consumers reading these keys don't break.
        "est_out_tok": response_bytes // 4,
        "est_in_tok": input_bytes // 4,
    }

    if tool_name == "Agent" and isinstance(tool_response, dict):
        resolved_model = tool_response.get("resolvedModel")
        total_tokens = tool_response.get("totalTokens")
        total_duration_ms = tool_response.get("totalDurationMs")
        total_tool_use_count = tool_response.get("totalToolUseCount")
        if resolved_model is not None and total_tokens is not None:
            entry["resolved_model"] = resolved_model
            entry["total_tokens_exact"] = total_tokens
            entry["total_duration_ms"] = total_duration_ms
            entry["total_tool_use_count"] = total_tool_use_count
            entry["token_source"] = "exact"

    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        rotate_log_if_large(LOG_FILE)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # fail-open: never block user workflow


if __name__ == "__main__":
    main()
