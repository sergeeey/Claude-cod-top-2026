"""Coverage tests: statusline, session_end, wiki_reminder extra paths, post_tool_failure extra."""

import io
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))


# ─── statusline ───────────────────────────────────────────────────────────────


class TestStatusline:
    def setup_method(self):
        import statusline

        self.mod = statusline

    def _run_main(self, data: dict) -> str:
        with patch("sys.stdin", io.StringIO(json.dumps(data))):
            with patch("builtins.print") as mock_print:
                self.mod.main()
        return mock_print.call_args[0][0] if mock_print.called else ""

    def test_basic_output_contains_model(self):
        data = {
            "model": {"display_name": "claude-3"},
            "context_window": {"used_percentage": 30},
            "cost": {"total_cost_usd": 0.05, "total_duration_ms": 3000},
        }
        result = self._run_main(data)
        assert "claude-3" in result

    def test_context_green_below_50(self):
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 40},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
        }
        result = self._run_main(data)
        assert "32m" in result  # green ANSI

    def test_context_yellow_50_to_70(self):
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 60},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
        }
        result = self._run_main(data)
        assert "33m" in result  # yellow ANSI

    def test_context_red_above_70(self):
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 75},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
        }
        result = self._run_main(data)
        assert "31m" in result  # red ANSI

    def test_agent_info_shown(self):
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 10},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
            "agent": {"name": "builder"},
        }
        result = self._run_main(data)
        assert "agent: builder" in result

    def test_no_agent_info_absent(self):
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 10},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
        }
        result = self._run_main(data)
        assert "agent:" not in result

    def test_rate_limits_shown(self):
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 10},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
            "rate_limits": {
                "five_hour": {"used_percentage": 50, "resets_at": None},
                "seven_day": {"used_percentage": 90, "resets_at": None},
            },
        }
        result = self._run_main(data)
        assert "5h:50%" in result
        assert "7d:90%" in result

    def test_rate_limit_red_above_85(self):
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 10},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
            "rate_limits": {"five_hour": {"used_percentage": 90, "resets_at": None}},
        }
        result = self._run_main(data)
        assert "31m" in result

    def test_rate_limit_yellow_60_to_85(self):
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 10},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
            "rate_limits": {"five_hour": {"used_percentage": 70, "resets_at": None}},
        }
        result = self._run_main(data)
        assert "33m" in result

    def test_rate_limit_green_below_60(self):
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 5},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
            "rate_limits": {"five_hour": {"used_percentage": 40, "resets_at": None}},
        }
        result = self._run_main(data)
        assert "32m" in result

    def test_rate_limit_with_reset_hours(self):
        future_ts = int(time.time()) + 3900  # ~65 min
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 10},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
            "rate_limits": {"five_hour": {"used_percentage": 50, "resets_at": str(future_ts)}},
        }
        result = self._run_main(data)
        assert "1h" in result

    def test_rate_limit_with_reset_minutes(self):
        future_ts = int(time.time()) + 1800  # 30 min
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 10},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
            "rate_limits": {"five_hour": {"used_percentage": 50, "resets_at": str(future_ts)}},
        }
        result = self._run_main(data)
        # allow small time skew
        assert any(f"{m}m" in result for m in range(27, 33))

    def test_rate_limit_invalid_ts_silently_skipped(self):
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 10},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
            "rate_limits": {"five_hour": {"used_percentage": 50, "resets_at": "bad"}},
        }
        result = self._run_main(data)
        assert "5h:50%" in result  # shown, without countdown

    def test_rate_limit_missing_used_pct_skipped(self):
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 10},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
            "rate_limits": {"five_hour": {}},
        }
        result = self._run_main(data)
        assert "5h:" not in result

    def test_git_exception_silently_ignored(self):
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 10},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
        }
        with patch("subprocess.run", side_effect=Exception("git not found")):
            result = self._run_main(data)
        assert "test" in result

    def test_git_project_and_branch_shown(self):
        mock_top = MagicMock(returncode=0, stdout="/home/user/myproject\n")
        mock_branch = MagicMock(returncode=0, stdout="main\n")
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 10},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
        }
        with patch("subprocess.run", side_effect=[mock_top, mock_branch]):
            result = self._run_main(data)
        assert "myproject" in result
        assert "main" in result

    def test_duration_formatted(self):
        data = {
            "model": {"display_name": "test"},
            "context_window": {"used_percentage": 10},
            "cost": {"total_cost_usd": 0.12, "total_duration_ms": 125000},  # 2m5s
        }
        result = self._run_main(data)
        assert "2m5s" in result


# ─── session_end ──────────────────────────────────────────────────────────────


class TestSessionEnd:
    def setup_method(self):
        import session_end

        self.mod = session_end

    def test_trims_failure_log_over_100_lines(self, tmp_path):
        logs_dir = tmp_path / ".claude" / "logs"
        logs_dir.mkdir(parents=True)
        failure_log = logs_dir / "tool_failures.jsonl"
        lines = [json.dumps({"tool": "Bash", "error": f"err{i}"}) for i in range(150)]
        failure_log.write_text("\n".join(lines) + "\n", encoding="utf-8")
        data = {}
        with (
            patch("sys.stdin", io.StringIO(json.dumps(data))),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            try:
                self.mod.main()
            except SystemExit:
                pass
        trimmed = failure_log.read_text().strip().split("\n")
        assert len(trimmed) == 100

    def test_does_not_trim_log_under_100_lines(self, tmp_path):
        logs_dir = tmp_path / ".claude" / "logs"
        logs_dir.mkdir(parents=True)
        failure_log = logs_dir / "tool_failures.jsonl"
        lines = [json.dumps({"tool": "Bash", "error": f"err{i}"}) for i in range(50)]
        failure_log.write_text("\n".join(lines) + "\n", encoding="utf-8")
        data = {}
        with (
            patch("sys.stdin", io.StringIO(json.dumps(data))),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            try:
                self.mod.main()
            except SystemExit:
                pass
        trimmed = failure_log.read_text().strip().split("\n")
        assert len(trimmed) == 50

    def test_session_end_logs_event(self, tmp_path):
        logs_dir = tmp_path / ".claude" / "logs"
        logs_dir.mkdir(parents=True)
        data = {"matcher": "test_stop"}
        with (
            patch("sys.stdin", io.StringIO(json.dumps(data))),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            try:
                self.mod.main()
            except SystemExit:
                pass
        log = logs_dir / "sessions.jsonl"
        assert log.exists()
        entry = json.loads(log.read_text().strip())
        assert entry["event"] == "session_end"


# ─── wiki_reminder extra paths ────────────────────────────────────────────────


class TestWikiReminderExtra:
    def setup_method(self):
        import wiki_reminder

        self.mod = wiki_reminder

    def test_get_last_response_skips_empty_lines(self, tmp_path):
        f = tmp_path / "t.jsonl"
        f.write_text("\n\n\n", encoding="utf-8")
        assert self.mod._get_last_assistant_response(str(f)) == ""

    def test_get_last_response_skips_invalid_json(self, tmp_path):
        f = tmp_path / "t.jsonl"
        f.write_text("not-json\n{bad\n", encoding="utf-8")
        assert self.mod._get_last_assistant_response(str(f)) == ""

    def test_get_last_response_skips_non_assistant(self, tmp_path):
        f = tmp_path / "t.jsonl"
        entry = {"message": {"role": "user", "content": "hello"}}
        f.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        assert self.mod._get_last_assistant_response(str(f)) == ""

    def test_get_last_response_handles_list_content(self, tmp_path):
        f = tmp_path / "t.jsonl"
        entry = {
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "decided to use"},
                    {"type": "tool_use", "name": "Bash"},
                    {"type": "text", "text": " architecture"},
                ],
            }
        }
        f.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        result = self.mod._get_last_assistant_response(str(f))
        assert "decided" in result

    def test_get_last_response_skips_non_dict_msg(self, tmp_path):
        f = tmp_path / "t.jsonl"
        entry = {"message": "not-a-dict"}
        f.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        assert self.mod._get_last_assistant_response(str(f)) == ""

    def test_main_skips_stop_hook_active(self, tmp_path, capsys):
        data = {"stop_hook_active": True, "transcript_path": str(tmp_path / "t.jsonl")}
        with patch("sys.stdin", io.StringIO(json.dumps(data))):
            self.mod.main()
        assert capsys.readouterr().out == ""

    def test_main_skips_empty_transcript_path(self, tmp_path, capsys):
        self.mod.DEBOUNCE_FILE = tmp_path / "deb.txt"
        data = {"stop_hook_active": False, "transcript_path": ""}
        with patch("sys.stdin", io.StringIO(json.dumps(data))):
            self.mod.main()
        assert capsys.readouterr().out == ""

    def test_main_emits_reminder_with_evidence(self, tmp_path):
        self.mod.DEBOUNCE_FILE = tmp_path / "deb.txt"
        transcript = tmp_path / "t.jsonl"
        text = "decided to use [VERIFIED] architecture instead of Postgres — tradeoff"
        transcript.write_text(
            json.dumps({"message": {"role": "assistant", "content": text}}) + "\n"
        )
        data = {"stop_hook_active": False, "transcript_path": str(transcript)}
        with patch("sys.stdin", io.StringIO(json.dumps(data))):
            with patch("builtins.print") as mock_print:
                self.mod.main()
        out = json.loads(mock_print.call_args[0][0])
        assert "wiki-reminder" in out.get("systemMessage", "")

    def test_main_emits_no_evidence_warning(self, tmp_path):
        self.mod.DEBOUNCE_FILE = tmp_path / "deb.txt"
        transcript = tmp_path / "t.jsonl"
        # 3 keywords, NO evidence markers
        text = "decided to use architecture instead of Postgres — tradeoff"
        transcript.write_text(
            json.dumps({"message": {"role": "assistant", "content": text}}) + "\n"
        )
        data = {"stop_hook_active": False, "transcript_path": str(transcript)}
        with patch("sys.stdin", io.StringIO(json.dumps(data))):
            with patch("builtins.print") as mock_print:
                self.mod.main()
        out = json.loads(mock_print.call_args[0][0])
        assert "NO evidence" in out.get("systemMessage", "")

    def test_has_verified_evidence_true(self):
        assert self.mod._has_verified_evidence("This is [VERIFIED] correct") is True
        assert self.mod._has_verified_evidence("[DOCS] says so") is True
        assert self.mod._has_verified_evidence("[CODE] shows this") is True

    def test_has_verified_evidence_false(self):
        assert self.mod._has_verified_evidence("plain statement") is False


# ─── post_tool_failure extra paths ────────────────────────────────────────────


class TestPostToolFailureExtra:
    def setup_method(self):
        import post_tool_failure

        self.mod = post_tool_failure

    def test_oserror_on_write_silently_ignored(self, tmp_path):
        self.mod.FAILURE_LOG = tmp_path / "failures.jsonl"
        data = {"tool_name": "Bash", "error": "err"}
        with patch("builtins.open", side_effect=OSError("disk full")):
            with patch("sys.stdin", io.StringIO(json.dumps(data))):
                try:
                    self.mod.main()
                except SystemExit:
                    pass

    def test_invalid_json_in_log_line_skipped(self, tmp_path):
        self.mod.FAILURE_LOG = tmp_path / "failures.jsonl"
        content = (
            "not-json\n"
            + "\n".join(json.dumps({"tool": "Bash", "error": "e"}) for _ in range(2))
            + "\n"
        )
        self.mod.FAILURE_LOG.write_text(content)
        data = {"tool_name": "Bash", "error": "again"}
        with patch("sys.stdin", io.StringIO(json.dumps(data))):
            try:
                self.mod.main()
            except SystemExit:
                pass  # must not raise

    def test_oserror_on_read_silently_ignored(self, tmp_path):
        self.mod.FAILURE_LOG = tmp_path / "sub" / "failures.jsonl"
        data = {"tool_name": "Bash", "error": "err"}
        with patch("sys.stdin", io.StringIO(json.dumps(data))):
            try:
                self.mod.main()
            except SystemExit:
                pass  # must not raise
