"""Shared fixtures for Claude Code Config tests."""

import json
import sys
from pathlib import Path

import pytest

# Add hooks/ and scripts/ to path for direct imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "scripts"))


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
