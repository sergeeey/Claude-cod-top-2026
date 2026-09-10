"""Tests for model_switch_tracker.py — the PostModelSwitch observer.

WHY these specific cases: the hook exists to make the resource router
checkable, which means its log is only worth anything if the rows are
trustworthy. Each test below pins one property that, if it silently broke,
would leave the file looking fine while answering the wrong question:

  - a switch is recorded at all, with both endpoints
  - an initial/restore switch (no from_model) is DISTINGUISHABLE from a
    mid-session one, rather than both collapsing to a null
  - a row that cannot name the resulting model is not written at all
  - the recursion guard prevents double-counting inside a subagent
  - nothing about a broken environment can raise out of the hook

The last one matters more than it looks: this is telemetry attached to a
PostModelSwitch event, and a crash here would surface as a hook failure on
an ordinary model change.
"""

from __future__ import annotations

import io
import json


def _run(monkeypatch, tmp_path, data: dict):
    import model_switch_tracker

    log_path = tmp_path / "model_switches.jsonl"
    monkeypatch.setattr(model_switch_tracker, "LOG_FILE", log_path)
    monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
    model_switch_tracker.main()
    if not log_path.exists():
        return None
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    return json.loads(lines[-1]) if lines else None


class TestRecording:
    def test_mid_session_switch_records_both_endpoints(self, monkeypatch, tmp_path):
        entry = _run(
            monkeypatch,
            tmp_path,
            {
                "session_id": "abc12345def",
                "from_model": "claude-sonnet-5",
                "to_model": "claude-opus-5",
                "cwd": "/repo",
            },
        )
        assert entry is not None
        assert entry["from_model"] == "claude-sonnet-5"
        assert entry["to_model"] == "claude-opus-5"
        assert entry["is_initial"] is False
        assert entry["sid"] == "abc12345"  # truncated to 8, like model_usage_tracker
        assert entry["cwd"] == "/repo"
        assert entry["ts"]

    def test_initial_or_restore_switch_is_distinguishable(self, monkeypatch, tmp_path):
        """No from_model means a session start or a resume-restore.

        That is NOT the same event as a human switching mid-task, and the
        difference has to be readable from the row itself -- deriving it from a
        null months later is guesswork.
        """
        entry = _run(
            monkeypatch,
            tmp_path,
            {"session_id": "zz999999", "to_model": "claude-opus-5"},
        )
        assert entry is not None
        assert entry["is_initial"] is True
        assert entry["from_model"] is None

    def test_row_without_a_resulting_model_is_not_written(self, monkeypatch, tmp_path):
        """A row that cannot say what the model became answers nothing.

        Writing it as a null is how a telemetry file stops being trustworthy:
        every later reader has to guess whether the null means "unknown" or
        "genuinely absent".
        """
        assert _run(monkeypatch, tmp_path, {"session_id": "aa", "from_model": "x"}) is None

    def test_appends_rather_than_overwrites(self, monkeypatch, tmp_path):
        import model_switch_tracker

        log_path = tmp_path / "model_switches.jsonl"
        monkeypatch.setattr(model_switch_tracker, "LOG_FILE", log_path)
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        for to in ("claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5-20251001"):
            monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"to_model": to})))
            model_switch_tracker.main()
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        assert [json.loads(x)["to_model"] for x in lines] == [
            "claude-sonnet-5",
            "claude-opus-5",
            "claude-haiku-4-5-20251001",
        ]


class TestResilience:
    def test_recursion_guard_suppresses_subagent_double_count(self, monkeypatch, tmp_path):
        import model_switch_tracker

        log_path = tmp_path / "model_switches.jsonl"
        monkeypatch.setattr(model_switch_tracker, "LOG_FILE", log_path)
        monkeypatch.setenv("CLAUDE_INVOKED_BY", "parent-session")
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"to_model": "claude-opus-5"})))
        model_switch_tracker.main()
        assert not log_path.exists()

    def test_malformed_stdin_does_not_raise(self, monkeypatch, tmp_path):
        import model_switch_tracker

        monkeypatch.setattr(model_switch_tracker, "LOG_FILE", tmp_path / "model_switches.jsonl")
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        monkeypatch.setattr("sys.stdin", io.StringIO("not json at all"))
        model_switch_tracker.main()  # must not raise

    def test_unwritable_log_does_not_raise(self, monkeypatch, tmp_path):
        """Telemetry is never worth failing a session over."""
        import model_switch_tracker

        monkeypatch.setattr(model_switch_tracker, "LOG_FILE", tmp_path / "model_switches.jsonl")
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"to_model": "claude-opus-5"})))

        def _boom(*a, **k):
            raise OSError("disk full")

        monkeypatch.setattr("builtins.open", _boom)
        model_switch_tracker.main()  # must not raise
