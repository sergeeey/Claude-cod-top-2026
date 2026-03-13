#!/usr/bin/env python3
"""
MCP Circuit Breaker — PostToolUse hook (claude-code-config).

Записывает результат MCP-вызова: success → сброс счётчика, error → инкремент.
Работает в паре с mcp_circuit_breaker.py (PreToolUse).
"""

import json
import sys
import time
from pathlib import Path

FAILURE_THRESHOLD = 3
STATE_FILE = Path.home() / ".claude" / "cache" / "mcp_circuit_state.json"

# ПОЧЕМУ: эти подстроки в tool_result указывают на сбой MCP-сервера,
# а не на штатный пустой ответ (который тоже может быть валидным).
ERROR_INDICATORS = [
    "error",
    "timed out",
    "connection refused",
    "ECONNREFUSED",
    "ETIMEDOUT",
    "503",
    "502",
    "500",
    "failed to connect",
]


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def get_server_name(tool_name: str) -> str | None:
    parts = tool_name.split("__")
    if len(parts) >= 3 and parts[0] == "mcp":
        return parts[1]
    return None


def is_error(result: str) -> bool:
    """Проверяет наличие индикаторов ошибки в результате вызова."""
    lower = result.lower()
    return any(indicator in lower for indicator in ERROR_INDICATORS)


def main() -> None:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return

    tool_name: str = event.get("tool_name", "")
    server = get_server_name(tool_name)
    if server is None:
        return

    tool_result: str = str(event.get("tool_result", ""))
    state = load_state()
    entry = state.get(server, {})

    if is_error(tool_result):
        # Инкремент failures, при пороге — фиксируем opened_at
        failures = entry.get("failures", 0) + 1
        entry["failures"] = failures
        if failures >= FAILURE_THRESHOLD and "opened_at" not in entry:
            entry["opened_at"] = time.time()
            print(
                f"[circuit-breaker] {server}: OPEN after {failures} failures",
                file=sys.stderr,
            )
    else:
        # Success — полный сброс (восстановление из HALF_OPEN)
        if entry.get("failures", 0) > 0:
            print(
                f"[circuit-breaker] {server}: recovered, resetting",
                file=sys.stderr,
            )
        entry = {"failures": 0}

    state[server] = entry
    save_state(state)


if __name__ == "__main__":
    main()
