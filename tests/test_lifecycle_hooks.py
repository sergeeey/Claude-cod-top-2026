"""Tests for lifecycle hooks: team_rebalance, worktree_lifecycle, stop_failure,
session_end, post_tool_failure, agent_lifecycle, subagent_verify.
"""

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def _stdin(data: dict):
    return io.StringIO(json.dumps(data))


# ── team_rebalance ───────────────────────────────────────────────────────────


class TestTeamRebalance:
    def test_emits_hook_result(self, monkeypatch, tmp_path, capsys):
        import team_rebalance

        monkeypatch.setattr("sys.stdin", _stdin({"agent_type": "builder", "agent_id": "a-1"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            team_rebalance.main()
        out = capsys.readouterr().out
        parsed = json.loads(out.strip())
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "builder" in ctx

    def test_empty_input(self, monkeypatch, tmp_path):
        import team_rebalance

        monkeypatch.setattr("sys.stdin", _stdin({}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            team_rebalance.main()

    def test_invalid_json(self, monkeypatch, tmp_path):
        import team_rebalance

        monkeypatch.setattr("sys.stdin", io.StringIO("bad"))
        with patch("pathlib.Path.home", return_value=tmp_path):
            team_rebalance.main()

    def test_logs_idle_event(self, monkeypatch, tmp_path, capsys):
        import team_rebalance

        monkeypatch.setattr("sys.stdin", _stdin({"agent_type": "tester", "agent_id": "t-5"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            team_rebalance.main()
        log = tmp_path / ".claude" / "logs" / "team_events.log"
        assert log.exists()
        assert "IDLE" in log.read_text()

    def test_oserror_silenced(self, monkeypatch, tmp_path, capsys):
        import team_rebalance

        monkeypatch.setattr("sys.stdin", _stdin({"agent_type": "x"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("builtins.open", side_effect=OSError):
                team_rebalance.main()


# ── worktree_lifecycle ───────────────────────────────────────────────────────


class TestWorktreeLifecycle:
    def _run(self, monkeypatch, tmp_path, data: dict):
        monkeypatch.setattr("sys.stdin", _stdin(data))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with pytest.raises(SystemExit) as exc:
                import worktree_lifecycle

                worktree_lifecycle.main()
        return exc.value.code

    def test_create_event_exit_zero(self, monkeypatch, tmp_path):
        code = self._run(
            monkeypatch, tmp_path, {"hook_event": "WorktreeCreate", "worktree_path": "/tmp/wt1"}
        )
        assert code == 0

    def test_remove_event_exit_zero(self, monkeypatch, tmp_path):
        code = self._run(
            monkeypatch, tmp_path, {"hook_event": "WorktreeRemove", "worktree_path": "/tmp/wt2"}
        )
        assert code == 0

    def test_logs_create(self, monkeypatch, tmp_path):
        self._run(
            monkeypatch, tmp_path, {"hook_event": "WorktreeCreate", "worktree_path": "/tmp/exp"}
        )
        log = tmp_path / ".claude" / "logs" / "worktrees.jsonl"
        assert log.exists()
        entry = json.loads(log.read_text().strip())
        assert entry["event"] == "create"

    def test_logs_remove(self, monkeypatch, tmp_path):
        self._run(
            monkeypatch, tmp_path, {"hook_event": "WorktreeRemove", "worktree_path": "/tmp/exp"}
        )
        log = tmp_path / ".claude" / "logs" / "worktrees.jsonl"
        entry = json.loads(log.read_text().strip())
        assert entry["event"] == "remove"

    def test_invalid_json_exits_zero(self, monkeypatch, tmp_path):
        monkeypatch.setattr("sys.stdin", io.StringIO("bad json"))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with pytest.raises(SystemExit) as exc:
                import worktree_lifecycle

                worktree_lifecycle.main()
        assert exc.value.code == 0

    def test_oserror_silenced(self, monkeypatch, tmp_path):
        monkeypatch.setattr("sys.stdin", _stdin({"hook_event": "WorktreeCreate"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("builtins.open", side_effect=OSError):
                with pytest.raises(SystemExit) as exc:
                    import worktree_lifecycle

                    worktree_lifecycle.main()
        assert exc.value.code == 0


# ── stop_failure ─────────────────────────────────────────────────────────────


class TestStopFailure:
    def _run(self, monkeypatch, tmp_path, data: dict):
        monkeypatch.setattr("sys.stdin", _stdin(data))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with pytest.raises(SystemExit) as exc:
                import stop_failure

                stop_failure.main()
        return exc.value.code

    def test_rate_limit_stderr(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr("sys.stdin", _stdin({"error_type": "rate_limit", "error": "429"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with pytest.raises(SystemExit):
                import stop_failure

                stop_failure.main()
        assert "Rate limit" in capsys.readouterr().err

    def test_auth_error_stderr(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr("sys.stdin", _stdin({"error_type": "auth_error", "error": "401"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with pytest.raises(SystemExit):
                import stop_failure

                stop_failure.main()
        assert "Auth error" in capsys.readouterr().err

    def test_generic_error_stderr(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr("sys.stdin", _stdin({"error_type": "unknown", "error": "something"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with pytest.raises(SystemExit):
                import stop_failure

                stop_failure.main()
        assert "Logged" in capsys.readouterr().err

    def test_exit_zero(self, monkeypatch, tmp_path):
        code = self._run(monkeypatch, tmp_path, {"error_type": "x"})
        assert code == 0

    def test_invalid_json_exits(self, monkeypatch, tmp_path):
        monkeypatch.setattr("sys.stdin", io.StringIO("bad"))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with pytest.raises(SystemExit) as exc:
                import stop_failure

                stop_failure.main()
        assert exc.value.code == 0

    def test_rate_in_error_msg(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr("sys.stdin", _stdin({"error_type": "other", "error": "429 rate"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with pytest.raises(SystemExit):
                import stop_failure

                stop_failure.main()
        assert "Rate limit" in capsys.readouterr().err


# ── session_end ──────────────────────────────────────────────────────────────


class TestSessionEnd:
    def _run(self, monkeypatch, tmp_path, data: dict):
        monkeypatch.setattr("sys.stdin", _stdin(data))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with pytest.raises(SystemExit) as exc:
                import session_end

                session_end.main()
        return exc.value.code

    def test_logs_session_end(self, monkeypatch, tmp_path):
        self._run(monkeypatch, tmp_path, {"matcher": "user_exit"})
        log = tmp_path / ".claude" / "logs" / "sessions.jsonl"
        assert log.exists()
        entry = json.loads(log.read_text().strip())
        assert entry["event"] == "session_end"
        assert entry["reason"] == "user_exit"

    def test_exit_zero(self, monkeypatch, tmp_path):
        assert self._run(monkeypatch, tmp_path, {}) == 0

    def test_invalid_json_exits(self, monkeypatch, tmp_path):
        monkeypatch.setattr("sys.stdin", io.StringIO("bad"))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with pytest.raises(SystemExit) as exc:
                import session_end

                session_end.main()
        assert exc.value.code == 0

    def test_trims_large_log(self, monkeypatch, tmp_path):
        """Log files > 100 lines should be trimmed to last 100."""
        log_dir = tmp_path / ".claude" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        big_log = log_dir / "tool_failures.jsonl"
        big_log.write_text("\n".join(f'{{"n": {i}}}' for i in range(150)) + "\n")
        self._run(monkeypatch, tmp_path, {})
        lines = big_log.read_text().strip().split("\n")
        assert len(lines) == 100
        # Last 100 lines kept
        assert json.loads(lines[-1])["n"] == 149

    def test_small_log_not_trimmed(self, monkeypatch, tmp_path):
        log_dir = tmp_path / ".claude" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        small_log = log_dir / "api_errors.jsonl"
        small_log.write_text("\n".join(f'{{"n": {i}}}' for i in range(50)) + "\n")
        self._run(monkeypatch, tmp_path, {})
        lines = small_log.read_text().strip().split("\n")
        assert len(lines) == 50


# ── post_tool_failure ────────────────────────────────────────────────────────


class TestPostToolFailure:
    def _run(self, monkeypatch, tmp_path, data: dict, capsys=None):
        monkeypatch.setattr("sys.stdin", _stdin(data))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with pytest.raises(SystemExit) as exc:
                import post_tool_failure

                # Reset FAILURE_LOG to tmp_path
                post_tool_failure.FAILURE_LOG = (
                    tmp_path / ".claude" / "logs" / "tool_failures.jsonl"
                )
                post_tool_failure.main()
        return exc.value.code

    def test_logs_failure(self, monkeypatch, tmp_path):
        self._run(monkeypatch, tmp_path, {"tool_name": "Bash", "error": "timeout"})
        log = tmp_path / ".claude" / "logs" / "tool_failures.jsonl"
        assert log.exists()

    def test_exit_zero(self, monkeypatch, tmp_path):
        assert self._run(monkeypatch, tmp_path, {"tool_name": "Read"}) == 0

    def test_invalid_json(self, monkeypatch, tmp_path):
        monkeypatch.setattr("sys.stdin", io.StringIO("bad"))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with pytest.raises(SystemExit) as exc:
                import post_tool_failure

                post_tool_failure.main()
        assert exc.value.code == 0

    def test_nudge_after_3_failures(self, monkeypatch, tmp_path, capsys):
        """After 3 failures of same tool → emit JSON nudge."""
        import post_tool_failure

        log = tmp_path / ".claude" / "logs" / "tool_failures.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        # Pre-populate 2 failures for Bash
        log.write_text('{"tool": "Bash", "error": "e1"}\n{"tool": "Bash", "error": "e2"}\n')
        monkeypatch.setattr("sys.stdin", _stdin({"tool_name": "Bash", "error": "e3"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            post_tool_failure.FAILURE_LOG = log
            with pytest.raises(SystemExit):
                post_tool_failure.main()
        out = capsys.readouterr().out
        if out.strip():
            parsed = json.loads(out.strip())
            assert "Bash" in parsed["message"]


# ── agent_lifecycle ──────────────────────────────────────────────────────────


class TestAgentLifecycle:
    def test_start_no_memory_no_crash(self, monkeypatch, tmp_path):
        """--start with no activeContext.md should not crash."""
        import agent_lifecycle

        monkeypatch.setattr("sys.argv", ["agent_lifecycle.py", "--start"])
        monkeypatch.setattr("sys.stdin", _stdin({"agent_type": "builder"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            agent_lifecycle.main()

    def test_start_with_memory(self, monkeypatch, tmp_path):
        """--start with activeContext.md emits context."""
        import agent_lifecycle

        mem = tmp_path / ".claude" / "memory" / "activeContext.md"
        mem.parent.mkdir(parents=True, exist_ok=True)
        mem.write_text("# Active\nCurrent focus: testing")
        monkeypatch.setattr("sys.argv", ["agent_lifecycle.py", "--start"])
        monkeypatch.setattr("sys.stdin", _stdin({"agent_type": "reviewer"}))
        with patch("agent_lifecycle.find_project_memory", return_value=mem):
            agent_lifecycle.main()

    def test_stop_logs(self, monkeypatch, tmp_path):
        """--stop should log completion."""
        import agent_lifecycle

        monkeypatch.setattr("sys.argv", ["agent_lifecycle.py", "--stop"])
        monkeypatch.setattr("sys.stdin", _stdin({"agent_type": "tester", "agent_id": "t-1"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            agent_lifecycle.main()

    def test_no_args_defaults_start(self, monkeypatch, tmp_path):
        import agent_lifecycle

        monkeypatch.setattr("sys.argv", ["agent_lifecycle.py"])
        monkeypatch.setattr("sys.stdin", _stdin({"agent_type": "explorer"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            agent_lifecycle.main()

    def test_empty_stdin(self, monkeypatch, tmp_path):
        import agent_lifecycle

        monkeypatch.setattr("sys.argv", ["agent_lifecycle.py", "--start"])
        monkeypatch.setattr("sys.stdin", _stdin({}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            agent_lifecycle.main()

    def test_start_oserror_on_read_is_swallowed(self, monkeypatch, tmp_path):
        """OSError when reading activeContext.md must not crash the hook."""
        import agent_lifecycle

        bad_path = tmp_path / "unreadable.md"
        bad_path.write_text("x")
        monkeypatch.setattr("sys.argv", ["agent_lifecycle.py", "--start"])
        monkeypatch.setattr("sys.stdin", _stdin({"agent_type": "builder"}))
        # WHY: patch find_project_memory to return a Path whose read_text raises
        broken = type(
            "_P",
            (),
            {
                "exists": lambda s: True,
                "read_text": lambda s, **k: (_ for _ in ()).throw(OSError("disk full")),
            },
        )()
        with patch("agent_lifecycle.find_project_memory", return_value=broken):
            agent_lifecycle.main()  # must not raise

    def test_stop_oserror_on_write_is_swallowed(self, monkeypatch, tmp_path):
        """OSError when writing the log file must not crash the hook."""
        import agent_lifecycle

        monkeypatch.setattr("sys.argv", ["agent_lifecycle.py", "--stop"])
        monkeypatch.setattr("sys.stdin", _stdin({"agent_type": "tester", "agent_id": "t-99"}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("builtins.open", side_effect=OSError("disk full")):
                agent_lifecycle.main()  # must not raise

    def test_main_entrypoint_via_runpy(self, monkeypatch, tmp_path):
        """Cover __main__ guard (line 69) via runpy execution."""
        import runpy

        monkeypatch.setattr("sys.argv", ["agent_lifecycle.py", "--start"])
        monkeypatch.setattr("sys.stdin", _stdin({}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            runpy.run_path("hooks/agent_lifecycle.py", run_name="__main__")


# ── subagent_verify ──────────────────────────────────────────────────────────


class TestSubagentVerify:
    def test_empty_response_warns(self, monkeypatch, tmp_path, capsys):
        import subagent_verify

        monkeypatch.setattr(
            "sys.stdin",
            _stdin(
                {
                    "agent_type": "builder",
                    "agent_id": "b-1",
                    "last_assistant_message": "",
                    "session_id": "s-1",
                }
            ),
        )
        with patch("pathlib.Path.home", return_value=tmp_path):
            subagent_verify.main()
        out = capsys.readouterr().out
        if out.strip():
            assert "empty" in json.loads(out)["message"].lower()

    def test_short_response_warns(self, monkeypatch, tmp_path, capsys):
        import subagent_verify

        monkeypatch.setattr(
            "sys.stdin", _stdin({"agent_type": "tester", "last_assistant_message": "ok"})
        )
        with patch("pathlib.Path.home", return_value=tmp_path):
            subagent_verify.main()

    def test_good_response_silent(self, monkeypatch, tmp_path, capsys):
        import subagent_verify

        monkeypatch.setattr(
            "sys.stdin",
            _stdin(
                {"agent_type": "reviewer", "last_assistant_message": "A" * 200, "session_id": "s-2"}
            ),
        )
        with patch("pathlib.Path.home", return_value=tmp_path):
            subagent_verify.main()

    def test_apology_detected(self, monkeypatch, tmp_path, capsys):
        import subagent_verify

        monkeypatch.setattr(
            "sys.stdin",
            _stdin(
                {
                    "agent_type": "builder",
                    "last_assistant_message": "I'm sorry, I cannot complete this task as requested.",
                    "session_id": "s-3",
                }
            ),
        )
        with patch("pathlib.Path.home", return_value=tmp_path):
            subagent_verify.main()

    def test_empty_stdin_no_crash(self, monkeypatch, tmp_path):
        import subagent_verify

        monkeypatch.setattr("sys.stdin", _stdin({}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            subagent_verify.main()

    def test_invalid_json_no_crash(self, monkeypatch, tmp_path):
        import subagent_verify

        monkeypatch.setattr("sys.stdin", io.StringIO("bad"))
        with patch("pathlib.Path.home", return_value=tmp_path):
            subagent_verify.main()
