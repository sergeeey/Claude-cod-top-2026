#!/usr/bin/env python3
"""SubagentStop hook: verify deliverables before accepting agent output.

WHY: Agents sometimes return empty or low-quality results. Verifying
that the last_assistant_message is non-trivial catches wasted agent runs
and prompts the orchestrator to retry or escalate.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from utils import parse_stdin

# WHY: short responses often indicate the agent failed silently
MIN_RESPONSE_LENGTH = 50


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    agent_type = data.get("agent_type", "unknown")
    agent_id = data.get("agent_id", "unknown")
    last_message = data.get("last_assistant_message", "")
    session_id = data.get("session_id", "unknown")

    issues: list[str] = []

    # Check 1: non-empty response
    if not last_message or not last_message.strip():
        issues.append("empty response")

    # Check 2: suspiciously short response
    elif len(last_message.strip()) < MIN_RESPONSE_LENGTH:
        issues.append(f"response too short ({len(last_message.strip())} chars)")

    # Check 3: agent returned an error/apology instead of deliverable
    apology_markers = [
        "I apologize",
        "I'm sorry",
        "I cannot",
        "I wasn't able to",
        "unable to complete",
    ]
    if any(marker.lower() in last_message.lower() for marker in apology_markers):
        issues.append("response contains apology/failure markers")

    # Log result
    log_dir = Path.home() / ".claude" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "subagent_verify.jsonl"

    try:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_type": agent_type,
            "agent_id": agent_id,
            "session_id": session_id,
            "response_length": len(last_message.strip()) if last_message else 0,
            "issues": issues,
            "verdict": "FAIL" if issues else "PASS",
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass

    # Warn orchestrator if issues found
    if issues:
        warning = (
            f"[subagent-verify] WARNING: {agent_type} agent returned "
            f"low-quality output: {', '.join(issues)}. "
            f"Consider retrying or escalating."
        )
        print(json.dumps({"result": "info", "message": warning}))


if __name__ == "__main__":
    main()
