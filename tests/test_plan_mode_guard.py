"""Unit tests for hooks/plan_mode_guard.py."""

from __future__ import annotations

import io
import json
import sys

import plan_mode_guard


def _run_main_with_stdin(payload: dict) -> None:
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        plan_mode_guard.main()
    finally:
        sys.stdin = old_stdin


class TestPlanModeGuard:
    def test_missing_file_path_skips(self, capsys):
        _run_main_with_stdin({"session_id": "s1", "tool_input": {}})
        assert capsys.readouterr().out == ""

    def test_tracker_path_sanitizes_session_id(self, tmp_path, monkeypatch):
        monkeypatch.setattr(plan_mode_guard.tempfile, "gettempdir", lambda: str(tmp_path))
        p = plan_mode_guard.get_tracker_path("a/b\\c")
        assert "a_b_c" in str(p)
        assert p.parent == tmp_path

    def test_warns_on_third_unique_file(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(plan_mode_guard.tempfile, "gettempdir", lambda: str(tmp_path))
        monkeypatch.setattr(plan_mode_guard, "has_active_plan", lambda: False)

        session_id = "s1"
        for i in range(3):
            _run_main_with_stdin(
                {"session_id": session_id, "tool_input": {"file_path": str(tmp_path / f"f{i}.py")}}
            )

        out = capsys.readouterr().out
        parsed = json.loads(out)
        msg = parsed["hookSpecificOutput"]["additionalContext"]
        assert "3 unique files edited" in msg
        assert parsed["hookSpecificOutput"]["hookEventName"] == "PostToolUse"

    def test_warns_more_strongly_on_fifth_unique_file(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(plan_mode_guard.tempfile, "gettempdir", lambda: str(tmp_path))
        monkeypatch.setattr(plan_mode_guard, "has_active_plan", lambda: False)

        session_id = "s2"
        for i in range(5):
            _run_main_with_stdin(
                {"session_id": session_id, "tool_input": {"file_path": str(tmp_path / f"g{i}.py")}}
            )

        out = capsys.readouterr().out
        last = out.strip().splitlines()[-1]
        parsed = json.loads(last)
        msg = parsed["hookSpecificOutput"]["additionalContext"]
        assert "WARNING" in msg
        assert "5 unique files edited" in msg

    def test_active_plan_suppresses_warning(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(plan_mode_guard.tempfile, "gettempdir", lambda: str(tmp_path))
        monkeypatch.setattr(plan_mode_guard, "has_active_plan", lambda: True)

        session_id = "s3"
        for i in range(5):
            _run_main_with_stdin(
                {"session_id": session_id, "tool_input": {"file_path": str(tmp_path / f"h{i}.py")}}
            )

        assert capsys.readouterr().out == ""

