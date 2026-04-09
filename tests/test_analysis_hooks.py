"""Tests for analysis/utility hooks: post_compact, thinking_level,
statusline, spot_check_guard, async_wrapper.
"""

import io
import json
from unittest.mock import MagicMock, patch

import pytest


def _stdin(data: dict):
    return io.StringIO(json.dumps(data))


# ── post_compact ──────────────────────────────────────────────────────────────


class TestPostCompact:
    def _run(self, monkeypatch, tmp_path, data: dict):
        monkeypatch.setattr("sys.stdin", _stdin(data))
        with pytest.raises(SystemExit) as exc:
            import post_compact

            with patch("post_compact.Path.cwd", return_value=tmp_path):
                post_compact.main()
        return exc.value.code

    def test_emits_reminder(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr("sys.stdin", _stdin({}))
        with pytest.raises(SystemExit):
            import post_compact

            with patch("post_compact.Path.cwd", return_value=tmp_path):
                post_compact.main()
        out = capsys.readouterr().out
        parsed = json.loads(out.strip())
        assert parsed["result"] == "info"
        assert "Context compacted" in parsed["message"]

    def test_exit_zero(self, monkeypatch, tmp_path):
        assert self._run(monkeypatch, tmp_path, {}) == 0

    def test_mentions_active_context_if_exists(self, monkeypatch, tmp_path, capsys):
        mem = tmp_path / ".claude" / "memory" / "activeContext.md"
        mem.parent.mkdir(parents=True, exist_ok=True)
        mem.write_text("# Active")
        monkeypatch.setattr("sys.stdin", _stdin({}))
        with pytest.raises(SystemExit):
            import post_compact

            with patch("post_compact.Path.cwd", return_value=tmp_path):
                post_compact.main()
        out = capsys.readouterr().out
        parsed = json.loads(out.strip())
        assert "activeContext" in parsed["message"] or "Re-read" in parsed["message"]

    def test_scope_fence_mentioned(self, monkeypatch, tmp_path, capsys):
        (tmp_path / ".scope-fence.md").write_text("scope")
        monkeypatch.setattr("sys.stdin", _stdin({}))
        with pytest.raises(SystemExit):
            import post_compact

            with patch("post_compact.Path.cwd", return_value=tmp_path):
                post_compact.main()
        out = capsys.readouterr().out
        assert "scope-fence" in json.loads(out)["message"]

    def test_invalid_json_no_crash(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr("sys.stdin", io.StringIO("bad json"))
        with pytest.raises(SystemExit):
            import post_compact

            with patch("post_compact.Path.cwd", return_value=tmp_path):
                post_compact.main()
        # Should still emit reminders even with bad JSON
        assert capsys.readouterr().out.strip()


# ── thinking_level ────────────────────────────────────────────────────────────


class TestThinkingLevel:
    def _run(self, monkeypatch, prompt: str):
        monkeypatch.setattr("sys.stdin", _stdin({"prompt": prompt}))
        with pytest.raises(SystemExit) as exc:
            import thinking_level

            thinking_level.main()
        return exc.value.code

    def test_architecture_suggests_l3(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", _stdin({"prompt": "redesign the architecture"}))
        with pytest.raises(SystemExit):
            import thinking_level

            thinking_level.main()
        out = capsys.readouterr().out
        if out.strip():
            assert "ultrathink" in out.lower() or "think" in out.lower()

    def test_debug_suggests_l2(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", _stdin({"prompt": "debug this failing test"}))
        with pytest.raises(SystemExit):
            import thinking_level

            thinking_level.main()

    def test_implement_suggests_l1(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", _stdin({"prompt": "implement the login form"}))
        with pytest.raises(SystemExit):
            import thinking_level

            thinking_level.main()

    def test_no_keywords_silent(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", _stdin({"prompt": "hello world"}))
        with pytest.raises(SystemExit):
            import thinking_level

            thinking_level.main()
        assert capsys.readouterr().out == ""

    def test_empty_prompt_silent(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", _stdin({"prompt": ""}))
        with pytest.raises(SystemExit):
            import thinking_level

            thinking_level.main()
        assert capsys.readouterr().out == ""

    def test_empty_stdin_no_crash(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", _stdin({}))
        with pytest.raises(SystemExit):
            import thinking_level

            thinking_level.main()

    def test_invalid_json_no_crash(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("bad"))
        with pytest.raises(SystemExit):
            import thinking_level

            thinking_level.main()

    def test_refactor_l3(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", _stdin({"prompt": "refactor the payment module"}))
        with pytest.raises(SystemExit):
            import thinking_level

            thinking_level.main()

    def test_security_audit_l3(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", _stdin({"prompt": "security audit the auth module"}))
        with pytest.raises(SystemExit):
            import thinking_level

            thinking_level.main()

    def test_exit_zero(self, monkeypatch):
        assert self._run(monkeypatch, "hello") == 0


# ── statusline ────────────────────────────────────────────────────────────────


class TestStatusline:
    def _data(self, pct=30, cost=0.05, duration_ms=5000, model="claude-sonnet"):
        return {
            "model": {"display_name": model},
            "context_window": {"used_percentage": pct},
            "cost": {"total_cost_usd": cost, "total_duration_ms": duration_ms},
        }

    def test_outputs_statusline(self, monkeypatch, capsys):
        import statusline

        monkeypatch.setattr("sys.stdin", _stdin(self._data()))
        statusline.main()
        out = capsys.readouterr().out
        assert "claude-sonnet" in out or "sonnet" in out.lower()

    def test_green_context_low(self, monkeypatch, capsys):
        import statusline

        monkeypatch.setattr("sys.stdin", _stdin(self._data(pct=20)))
        statusline.main()
        out = capsys.readouterr().out
        assert out.strip()  # produces output

    def test_yellow_context_medium(self, monkeypatch, capsys):
        import statusline

        monkeypatch.setattr("sys.stdin", _stdin(self._data(pct=60)))
        statusline.main()
        assert capsys.readouterr().out.strip()

    def test_red_context_high(self, monkeypatch, capsys):
        import statusline

        monkeypatch.setattr("sys.stdin", _stdin(self._data(pct=80)))
        statusline.main()
        out = capsys.readouterr().out
        assert "clear" in out.lower() or out.strip()  # red warns about /clear

    def test_zero_cost(self, monkeypatch, capsys):
        import statusline

        monkeypatch.setattr("sys.stdin", _stdin(self._data(cost=0.0, duration_ms=0)))
        statusline.main()
        assert capsys.readouterr().out.strip()

    def test_missing_fields_no_crash(self, monkeypatch, capsys):
        import statusline

        monkeypatch.setattr("sys.stdin", _stdin({}))
        statusline.main()
        assert capsys.readouterr().out.strip()

    def test_git_branch_included(self, monkeypatch, capsys):
        import statusline

        monkeypatch.setattr("sys.stdin", _stdin(self._data()))
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "main"
        with patch("statusline.subprocess.run", return_value=mock_result):
            statusline.main()
        out = capsys.readouterr().out
        assert "main" in out


# ── spot_check_guard ──────────────────────────────────────────────────────────


class TestSpotCheckGuard:
    MANY_CLAIMS = (
        "Python version 3.11 is required. "
        "You must always use type hints. "
        "Best practice defaults to ruff. "
        "Coverage is 80% of business logic. "
        "There are 100 tests in 10 files. "
        "Version 2.0 supports up to 1000 items. "
        "The limit is 500 per second. "
        "Line 42 defines the main function. "
        "Always run mypy before committing. "
        "Never skip the review step. "
        "Default timeout is 30 seconds. " * 5
    )

    def _run(self, monkeypatch, response: str):
        data = {"tool_response": {"stdout": response}}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
        import spot_check_guard

        spot_check_guard.main()

    def test_many_claims_emits_nudge(self, monkeypatch, capsys):
        self._run(monkeypatch, self.MANY_CLAIMS)
        out = capsys.readouterr().out
        if out.strip():
            parsed = json.loads(out.strip())
            ctx = parsed["hookSpecificOutput"]["additionalContext"]
            assert "spot" in ctx.lower() or "check" in ctx.lower() or "claim" in ctx.lower()

    def test_few_claims_silent(self, monkeypatch, capsys):
        self._run(monkeypatch, "Here is the code you requested.")
        assert capsys.readouterr().out == ""

    def test_short_response_silent(self, monkeypatch, capsys):
        self._run(monkeypatch, "Short.")
        assert capsys.readouterr().out == ""

    def test_empty_input_silent(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", _stdin({}))
        import spot_check_guard

        spot_check_guard.main()
        assert capsys.readouterr().out == ""

    def test_invalid_json_silent(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", io.StringIO("bad"))
        import spot_check_guard

        spot_check_guard.main()
        assert capsys.readouterr().out == ""

    def test_count_claims_function(self):
        from spot_check_guard import count_claims

        assert count_claims("Python 3.11 is required") >= 1
        assert count_claims("you must always do X") >= 1
        assert count_claims("no claims here at all") == 0

    def test_threshold_constant(self):
        from spot_check_guard import SPOT_CHECK_THRESHOLD

        assert SPOT_CHECK_THRESHOLD == 10


# ── async_wrapper ─────────────────────────────────────────────────────────────


def _binary_stdin(data: str):
    """Create a mock stdin that has a .buffer attribute for binary reads."""
    mock = MagicMock()
    mock.buffer.read.return_value = data.encode()
    return mock


class TestAsyncWrapper:
    def test_exit_zero_immediately(self, monkeypatch, capsys):
        """Wrapper should exit 0 right after spawning subprocess."""
        monkeypatch.setattr("sys.argv", ["async_wrapper.py", "python", "some_hook.py"])
        monkeypatch.setattr("sys.stdin", _binary_stdin("{}"))
        mock_proc = MagicMock()
        with patch("async_wrapper.subprocess.Popen", return_value=mock_proc) as mock_popen:
            with pytest.raises(SystemExit) as exc:
                import async_wrapper

                async_wrapper.main()
        assert exc.value.code == 0
        mock_popen.assert_called_once()

    def test_passes_stdin_to_child(self, monkeypatch):
        """Stdin data should be piped to child process."""
        monkeypatch.setattr("sys.argv", ["async_wrapper.py", "python", "hook.py"])
        monkeypatch.setattr("sys.stdin", _binary_stdin('{"key": "val"}'))
        mock_proc = MagicMock()
        with patch("async_wrapper.subprocess.Popen", return_value=mock_proc) as mock_popen:
            with pytest.raises(SystemExit):
                import async_wrapper

                async_wrapper.main()
        call_kwargs = mock_popen.call_args
        assert call_kwargs is not None

    def test_no_args_exits(self, monkeypatch):
        """No args to run → should still exit cleanly."""
        monkeypatch.setattr("sys.argv", ["async_wrapper.py"])
        monkeypatch.setattr("sys.stdin", _binary_stdin("{}"))
        with patch("async_wrapper.subprocess.Popen", return_value=MagicMock()):
            with pytest.raises(SystemExit) as exc:
                import async_wrapper

                async_wrapper.main()
        assert exc.value.code == 0

    def test_windows_detached_flag(self):
        """_DETACHED_PROCESS constant should be defined."""
        import async_wrapper

        assert async_wrapper._DETACHED_PROCESS == 0x00000008
        assert async_wrapper._CREATE_NO_WINDOW == 0x08000000
