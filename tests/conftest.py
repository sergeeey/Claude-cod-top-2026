"""Shared fixtures for Claude Code Config tests."""

import json
import sys
from pathlib import Path

import pytest

# Add hooks/, scripts/, and boyko_eval/ to path for direct imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "boyko_eval"))


@pytest.fixture
def make_hook_input():
    """Factory: creates JSON string mimicking Claude Code hook stdin."""

    def _make(tool_name: str, tool_input: dict | None = None) -> str:
        return json.dumps({"tool_name": tool_name, "tool_input": tool_input or {}})

    return _make


@pytest.fixture
def tmp_state_file(tmp_path):
    """Temporary circuit breaker state file."""
    return tmp_path / "mcp_circuit_state.json"


@pytest.fixture(autouse=True)
def _isolate_hook_trigger_log(tmp_path_factory, monkeypatch):
    """Keep tests out of the live ~/.claude/logs/hook_triggers.jsonl.

    Without this every pytest run appended synthetic hook triggers (about 85%
    of the live log) and skewed the noise metrics. Tests that assert on the
    log patch the same attribute themselves and win, as they run later.
    """
    try:
        import lib.state as _state
    except ImportError:
        return
    log = tmp_path_factory.mktemp("hook_triggers_log") / "hook_triggers.jsonl"
    monkeypatch.setattr(_state, "HOOK_TRIGGERS_LOG", log)


@pytest.fixture(autouse=True)
def _isolate_hook_telemetry(tmp_path, monkeypatch):
    """Hook trigger telemetry from in-process hook runs goes to a per-test file.

    WHY (2026-11-25): 2321 of 2720 input_guard rows in the live ~/.claude/logs/hook_triggers.jsonl
    were test fixtures (mcp__untrusted__* in tests/test_integration.py and test_coverage_boost.py),
    which made the production telemetry look like false positives. Reuses the monkeypatch pattern
    already in tests/test_hook_triggers_telemetry.py. Subprocess-based hook tests are NOT covered
    by this fixture (they inherit the real HOME); see the report for that remaining path.
    """
    import lib.state as state

    monkeypatch.setattr(state, "HOOK_TRIGGERS_LOG", tmp_path / "hook_triggers.jsonl")
