#!/usr/bin/env python3
"""
MCP Circuit Breaker — PostToolUse hook (claude-code-config).

Записывает результат MCP-вызова: success → сброс счётчика, error → инкремент.
Работает в паре с mcp_circuit_breaker.py (PreToolUse).
"""

import sys
import time
from pathlib import Path

from utils import get_mcp_server_name, load_json_state, parse_stdin_raw, save_json_state

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


def is_error(result: str) -> bool:
    """Проверяет наличие индикаторов ошибки в результате вызова."""
    lower = result.lower()
    return any(indicator in lower for indicator in ERROR_INDICATORS)


def main() -> None:
    event = parse_stdin_raw()
    if not event:
        return

    tool_name: str = event.get("tool_name", "")
    server = get_mcp_server_name(tool_name)
    if server is None:
        return

    tool_result: str = str(event.get("tool_result", ""))
    state = load_json_state(STATE_FILE)
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
    save_json_state(STATE_FILE, state)


if __name__ == "__main__":
    main()
