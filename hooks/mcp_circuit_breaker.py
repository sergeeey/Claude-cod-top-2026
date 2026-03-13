"""
MCP Circuit Breaker — PreToolUse hook (claude-code-config).

Реализует паттерн Circuit Breaker для MCP-серверов: при повторных сбоях
сервер временно блокируется, Claude получает fallback-предложение.

Состояния:
  CLOSED    — нормальная работа
  OPEN      — заблокирован после N сбоев (сервер не вызывается)
  HALF_OPEN — тестовый пропуск после таймаута восстановления
"""

import json
import sys
import time
from pathlib import Path

# --- Конфигурация -----------------------------------------------------------

FAILURE_THRESHOLD = 3
RECOVERY_TIMEOUT = 60  # секунды
STATE_FILE = Path.home() / ".claude" / "cache" / "mcp_circuit_state.json"

# ПОЧЕМУ: fallback-строки хранятся здесь, а не в внешнем конфиге —
# хук должен работать без зависимостей при любом состоянии MCP
FALLBACKS: dict[str, str] = {
    "context7": "Use WebSearch or WebFetch for documentation",
    "playwright": "Use WebFetch for static content",
    "basic-memory": "Use Read/Write for file-based memory",
    "ollama": "Skip local inference, use cloud model",
}
DEFAULT_FALLBACK = "Try alternative approach"


# --- Работа с состоянием ----------------------------------------------------


def load_state() -> dict:
    """Загружает состояние circuit breaker из JSON-файла."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict) -> None:
    """Сохраняет состояние circuit breaker в JSON-файл."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# --- Логика Circuit Breaker -------------------------------------------------


def get_server_name(tool_name: str) -> str | None:
    """Извлекает имя MCP-сервера из имени инструмента вида mcp__<server>__<method>."""
    parts = tool_name.split("__")
    # ПОЧЕМУ: паттерн всегда содержит минимум 3 части; не-MCP инструменты пропускаем
    if len(parts) >= 3 and parts[0] == "mcp":
        return parts[1]
    return None


def get_circuit_status(entry: dict) -> str:
    """Определяет текущее состояние цепи для конкретного сервера."""
    failures = entry.get("failures", 0)
    opened_at = entry.get("opened_at")

    if failures < FAILURE_THRESHOLD:
        return "CLOSED"

    if opened_at and (time.time() - opened_at) >= RECOVERY_TIMEOUT:
        # ПОЧЕМУ: HALF_OPEN позволяет одному запросу пройти для проверки
        # восстановления сервера без полного сброса счётчика
        return "HALF_OPEN"

    return "OPEN"


def record_open(state: dict, server: str) -> dict:
    """Переводит цепь сервера в состояние OPEN, фиксируя время блокировки."""
    entry = state.get(server, {})
    entry["failures"] = entry.get("failures", 0) + 1
    if entry["failures"] >= FAILURE_THRESHOLD and "opened_at" not in entry:
        entry["opened_at"] = time.time()
    state[server] = entry
    return state


# --- Точка входа ------------------------------------------------------------


def main() -> None:
    """Обрабатывает PreToolUse-событие от Claude Code."""
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        # Не можем разобрать ввод — пропускаем без блокировки
        print("{}")
        return

    tool_name: str = event.get("tool_name", "")
    server = get_server_name(tool_name)

    if server is None:
        # Не MCP-инструмент — circuit breaker не применяется
        print("{}")
        return

    state = load_state()
    entry = state.get(server, {})
    status = get_circuit_status(entry)

    if status == "OPEN":
        fallback = FALLBACKS.get(server, DEFAULT_FALLBACK)
        result = {
            "decision": "block",
            "reason": f"Circuit OPEN for '{server}' ({entry.get('failures', 0)} failures). "
            f"Fallback: {fallback}",
        }
        print(json.dumps(result))
        return

    if status == "HALF_OPEN":
        # ПОЧЕМУ: сбрасываем opened_at чтобы дать один шанс — если снова
        # упадёт, PreToolUse снова запишет opened_at при следующем вызове
        entry.pop("opened_at", None)
        state[server] = entry
        save_state(state)

    # CLOSED или HALF_OPEN — разрешаем вызов
    print("{}")


if __name__ == "__main__":
    main()
