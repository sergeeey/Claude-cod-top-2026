"""Hidden acceptance test for T2. Copied into the clone's tests/ only at grading time.

The arms never see this file. It pins the behaviour described in T2_prompt.txt.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import lib.state as state
import pytest

REPO = Path(__file__).resolve().parent.parent


def _lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
    monkeypatch.delenv("CLAUDE_LOGS_DIR", raising=False)


def test_t2_1_env_unset_uses_patched_attribute(tmp_path, monkeypatch):
    """Existing contract: tests patch lib.state.HOOK_TRIGGERS_LOG and expect writes there."""
    target = tmp_path / "attr" / "hook_triggers.jsonl"
    monkeypatch.setattr(state, "HOOK_TRIGGERS_LOG", target)
    state.log_hook_trigger("t2", "case1", "warning", "x")
    assert len(_lines(target)) == 1


def test_t2_2_env_set_after_import_wins(tmp_path, monkeypatch):
    """Env var read at call time and taking precedence over the module attribute."""
    attr_target = tmp_path / "attr" / "hook_triggers.jsonl"
    env_dir = tmp_path / "envdir"
    monkeypatch.setattr(state, "HOOK_TRIGGERS_LOG", attr_target)
    monkeypatch.setenv("CLAUDE_LOGS_DIR", str(env_dir))
    state.log_hook_trigger("t2", "case2", "warning", "x")
    assert len(_lines(env_dir / "hook_triggers.jsonl")) == 1
    assert _lines(attr_target) == []


def test_t2_3_env_dir_created_when_missing(tmp_path, monkeypatch):
    env_dir = tmp_path / "a" / "b" / "c"
    monkeypatch.setenv("CLAUDE_LOGS_DIR", str(env_dir))
    state.log_hook_trigger("t2", "case3", "warning", "x")
    assert len(_lines(env_dir / "hook_triggers.jsonl")) == 1


def test_t2_4_empty_env_is_treated_as_unset(tmp_path, monkeypatch):
    attr_target = tmp_path / "attr" / "hook_triggers.jsonl"
    monkeypatch.setattr(state, "HOOK_TRIGGERS_LOG", attr_target)
    monkeypatch.setenv("CLAUDE_LOGS_DIR", "")
    state.log_hook_trigger("t2", "case4", "warning", "x")
    assert len(_lines(attr_target)) == 1


def test_t2_5_default_path_unchanged_without_env():
    """In a fresh interpreter with the variable unset, the default stays ~/.claude/logs."""
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "import lib.state as s; print(s.HOOK_TRIGGERS_LOG.as_posix())"
    )
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_LOGS_DIR"}
    out = subprocess.run(
        [sys.executable, "-c", code, str(REPO / "hooks")],
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()
    assert out.endswith("/.claude/logs/hook_triggers.jsonl")


def test_t2_6_second_call_after_env_change(tmp_path, monkeypatch):
    """Changing the env var between calls changes where the next call writes."""
    d1, d2 = tmp_path / "one", tmp_path / "two"
    monkeypatch.setenv("CLAUDE_LOGS_DIR", str(d1))
    state.log_hook_trigger("t2", "c6a", "warning", "x")
    monkeypatch.setenv("CLAUDE_LOGS_DIR", str(d2))
    state.log_hook_trigger("t2", "c6b", "warning", "x")
    assert len(_lines(d1 / "hook_triggers.jsonl")) == 1
    assert len(_lines(d2 / "hook_triggers.jsonl")) == 1
