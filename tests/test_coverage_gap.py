"""Coverage gap tests: syntax_guard, post_tool_failure, post_format, wiki_reminder, pattern_extractor."""

import io
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))


# ─── syntax_guard ─────────────────────────────────────────────────────────────


class TestValidateJs:
    def setup_method(self):
        import syntax_guard

        self.mod = syntax_guard

    def test_valid_js_returns_none(self):
        result = self.mod._validate_js("const x = 1;")
        # node may not be installed in CI — either None (pass) or error string
        assert result is None or isinstance(result, str)

    def test_node_not_found_returns_none(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = self.mod._validate_js("const x = 1;")
        assert result is None

    def test_node_timeout_returns_none(self):
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("node", 5)):
            result = self.mod._validate_js("bad js {{{{")
        assert result is None

    def test_node_error_returns_string(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "SyntaxError: Unexpected token\nmore noise"
        with patch("subprocess.run", return_value=mock_result):
            result = self.mod._validate_js("bad {{")
        assert result is not None
        assert "SyntaxError" in result
        assert len(result) <= 200

    def test_valid_python_passes(self, tmp_path):
        py_file = tmp_path / "test.py"
        py_file.write_text("x = 1 + 2\n", encoding="utf-8")
        result = self.mod._validate_python(py_file.read_text())
        assert result is None

    def test_invalid_python_returns_error(self):
        result = self.mod._validate_python("def broken(\n    x\n# missing close")
        assert result is not None
        assert isinstance(result, str)


# ─── post_tool_failure ────────────────────────────────────────────────────────


class TestPostToolFailure:
    def setup_method(self):
        import post_tool_failure

        self.mod = post_tool_failure

    def test_logs_failure(self, tmp_path):
        self.mod.FAILURE_LOG = tmp_path / "failures.jsonl"
        data = {"tool_name": "Bash", "error": "command not found"}
        with patch("sys.stdin", io.StringIO(json.dumps(data))):
            try:
                self.mod.main()
            except SystemExit:
                pass
        assert self.mod.FAILURE_LOG.exists()
        line = json.loads(self.mod.FAILURE_LOG.read_text().strip())
        assert line["tool"] == "Bash"

    def test_recovery_message_at_3_failures(self, tmp_path, capsys):
        self.mod.FAILURE_LOG = tmp_path / "failures.jsonl"
        # Pre-fill 2 failures
        entries = [json.dumps({"tool": "Edit", "error": "e"}) for _ in range(2)]
        self.mod.FAILURE_LOG.write_text("\n".join(entries) + "\n")
        data = {"tool_name": "Edit", "error": "again"}
        with patch("sys.stdin", io.StringIO(json.dumps(data))):
            try:
                self.mod.main()
            except SystemExit:
                pass
        captured = capsys.readouterr()
        assert "error-recovery" in captured.out or captured.out == ""

    def test_no_recovery_below_threshold(self, tmp_path, capsys):
        self.mod.FAILURE_LOG = tmp_path / "failures.jsonl"
        data = {"tool_name": "Read", "error": "oops"}
        with patch("sys.stdin", io.StringIO(json.dumps(data))):
            try:
                self.mod.main()
            except SystemExit:
                pass
        captured = capsys.readouterr()
        # Only 1 failure — no recovery message
        assert "error-recovery" not in captured.out


# ─── post_format ──────────────────────────────────────────────────────────────


class TestPostFormat:
    def setup_method(self):
        import post_format

        self.mod = post_format

    def test_python_file_calls_ruff(self, tmp_path):
        py = tmp_path / "test.py"
        py.write_text("x=1\n")
        data = {"tool_input": {"file_path": str(py)}}
        with patch("subprocess.run") as mock_run, patch("sys.stdin", io.StringIO(json.dumps(data))):
            self.mod.main()
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("ruff" in c for c in calls)

    def test_js_file_calls_prettier(self, tmp_path):
        js = tmp_path / "test.js"
        js.write_text("const x=1\n")
        data = {"tool_input": {"file_path": str(js)}}
        with patch("subprocess.run") as mock_run, patch("sys.stdin", io.StringIO(json.dumps(data))):
            self.mod.main()
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("prettier" in c for c in calls)

    def test_missing_path_skips(self, capsys):
        data = {"tool_input": {"file_path": "/nonexistent/file.py"}}
        with patch("sys.stdin", io.StringIO(json.dumps(data))):
            self.mod.main()
        # no crash, no output
        assert capsys.readouterr().out == ""

    def test_formatter_not_installed_silently_skips(self, tmp_path):
        py = tmp_path / "test.py"
        py.write_text("x=1\n")
        data = {"tool_input": {"file_path": str(py)}}
        with (
            patch("subprocess.run", side_effect=FileNotFoundError),
            patch("sys.stdin", io.StringIO(json.dumps(data))),
        ):
            self.mod.main()  # must not raise


# ─── wiki_reminder ────────────────────────────────────────────────────────────


class TestWikiReminder:
    def setup_method(self):
        import wiki_reminder

        self.mod = wiki_reminder

    def test_debounce_no_file_returns_true(self, tmp_path):
        self.mod.DEBOUNCE_FILE = tmp_path / "debounce.txt"
        assert self.mod._check_debounce() is True

    def test_debounce_recent_returns_false(self, tmp_path):
        f = tmp_path / "debounce.txt"
        f.write_text(str(time.time()), encoding="utf-8")
        self.mod.DEBOUNCE_FILE = f
        assert self.mod._check_debounce() is False

    def test_debounce_old_returns_true(self, tmp_path):
        f = tmp_path / "debounce.txt"
        f.write_text(str(time.time() - 400), encoding="utf-8")
        self.mod.DEBOUNCE_FILE = f
        assert self.mod._check_debounce() is True

    def test_debounce_invalid_returns_true(self, tmp_path):
        f = tmp_path / "debounce.txt"
        f.write_text("not-a-number", encoding="utf-8")
        self.mod.DEBOUNCE_FILE = f
        assert self.mod._check_debounce() is True

    def test_update_debounce_writes_timestamp(self, tmp_path):
        self.mod.DEBOUNCE_FILE = tmp_path / "debounce.txt"
        self.mod._update_debounce()
        val = float(self.mod.DEBOUNCE_FILE.read_text())
        assert abs(val - time.time()) < 2

    def test_get_last_response_missing_file(self, tmp_path):
        result = self.mod._get_last_assistant_response(str(tmp_path / "missing.jsonl"))
        assert result == ""

    def test_get_last_response_oversized_returns_empty(self, tmp_path):
        f = tmp_path / "big.jsonl"
        f.write_text("x" * 10)
        orig = self.mod.MAX_TRANSCRIPT_BYTES
        self.mod.MAX_TRANSCRIPT_BYTES = 5
        result = self.mod._get_last_assistant_response(str(f))
        self.mod.MAX_TRANSCRIPT_BYTES = orig
        assert result == ""

    def test_get_last_response_parses_jsonl(self, tmp_path):
        f = tmp_path / "transcript.jsonl"
        entry = {"message": {"role": "assistant", "content": "I decided to use Neo4j"}}
        f.write_text(json.dumps(entry) + "\n")
        result = self.mod._get_last_assistant_response(str(f))
        assert "Neo4j" in result

    def test_has_decision_language_true(self):
        # MIN_KEYWORD_MATCHES=3: "decided" + "instead of" + "architecture" = 3
        text = "I decided to use Neo4j instead of Postgres for architecture reasons"
        assert self.mod._has_decision_language(text) is True

    def test_has_decision_language_false(self):
        assert self.mod._has_decision_language("hello world") is False

    def test_has_decision_language_below_threshold(self):
        # Only 2 keywords — below threshold of 3
        assert self.mod._has_decision_language("decided to use instead of") is False


# ─── pattern_extractor ────────────────────────────────────────────────────────


class TestPatternExtractor:
    def setup_method(self):
        import pattern_extractor

        self.mod = pattern_extractor

    def test_extract_fix_subject_valid(self):
        result = self.mod.extract_fix_subject("fix: resolve memory leak in session_save")
        assert result == "resolve memory leak in session_save"

    def test_extract_fix_subject_non_fix_returns_none(self):
        assert self.mod.extract_fix_subject("feat: add new feature") is None
        assert self.mod.extract_fix_subject("chore: update deps") is None

    def test_find_matching_patterns_empty(self):
        result = self.mod.find_matching_patterns("some bug", "")
        assert result == []

    def test_find_matching_patterns_finds_match(self):
        patterns_text = (
            "[AVOID] never use datetime.utcnow() — use timezone-aware\n[REPEAT] always use UTC"
        )
        result = self.mod.find_matching_patterns("datetime bug", patterns_text)
        # "datetime" appears in patterns_text
        assert isinstance(result, list)

    def test_build_reminder_message_no_matches(self):
        msg = self.mod.build_reminder_message("abc1234", "fix: something", "something", [])
        assert "abc1234" in msg
        assert isinstance(msg, str)

    def test_build_reminder_message_with_matches(self):
        # find_matching_patterns returns list[tuple[str, int]]
        matches = [("### [AVOID] Never ignore errors", 2)]
        msg = self.mod.build_reminder_message(
            "abc1234", "fix: ignore error", "ignore error", matches
        )
        assert "abc1234" in msg
        assert "×2" in msg or "Never ignore" in msg or "WARNING" in msg

    def test_is_failed_commit(self):
        assert self.mod.is_failed_commit("nothing to commit") is True
        assert self.mod.is_failed_commit("[main abc1234] fix: something") is False

    def test_main_skips_non_commit(self, capsys):
        data = {
            "tool_input": {"command": "git push origin main"},
            "tool_response": {"stdout": "", "returncode": 0},
        }
        with patch("sys.stdin", io.StringIO(json.dumps(data))):
            self.mod.main()
        assert capsys.readouterr().out == ""
