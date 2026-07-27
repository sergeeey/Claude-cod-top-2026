"""Tests for auto_capture.py — _capture_git_commit, _capture_test_failure, _write_raw.

WHY: auto_capture.py runs on every Bash PostToolUse event and writes raw notes to
~/.claude/memory/_auto/raw/. Tests use tmp_path and env-var patching to stay
fully isolated — no real files written to $HOME.
"""

import importlib
import sys
from pathlib import Path

import pytest

# Add hooks/ to path before importing auto_capture
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def reload_module(monkeypatch: pytest.MonkeyPatch, raw_dir: Path, dry_run: bool = False):
    """Reload auto_capture with patched RAW_DIR and DRY_RUN."""
    monkeypatch.setenv("CLAUDE_DRY_RUN", "1" if dry_run else "0")
    # Ensure CLAUDE_INVOKED_BY is absent so the module doesn't sys.exit(0)
    monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)

    import auto_capture

    importlib.reload(auto_capture)
    # Override the module-level RAW_DIR to point at tmp_path
    auto_capture.RAW_DIR = raw_dir
    auto_capture.DRY_RUN = dry_run
    return auto_capture


# ===========================================================================
# _write_raw
# ===========================================================================


class TestWriteRaw:
    def test_writes_new_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        written = ac._write_raw("test-slug", "# Hello\n")
        assert written is True
        result = (tmp_path / "raw" / "test-slug.md").read_text(encoding="utf-8")
        assert "# Hello" in result

    def test_idempotent_when_file_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        raw = tmp_path / "raw"
        raw.mkdir(parents=True)
        (raw / "test-slug.md").write_text("existing", encoding="utf-8")

        ac = reload_module(monkeypatch, raw)
        written = ac._write_raw("test-slug", "# New content\n")
        # File already exists — should NOT overwrite and return False
        assert written is False
        assert (raw / "test-slug.md").read_text(encoding="utf-8") == "existing"

    def test_slug_sanitized(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        ac._write_raw("slug with spaces / slashes!", "body")
        files = list((tmp_path / "raw").glob("*.md"))
        assert len(files) == 1
        # Spaces and special chars replaced with underscores, no slash in filename
        assert "/" not in files[0].name
        assert " " not in files[0].name

    def test_slug_truncated_to_60_chars(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        long_slug = "a" * 100
        ac._write_raw(long_slug, "body")
        files = list((tmp_path / "raw").glob("*.md"))
        # stem is the slug (without .md extension), must be <= 60 chars
        assert len(files[0].stem) <= 60

    def test_dry_run_returns_true_no_file_written(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ):
        ac = reload_module(monkeypatch, tmp_path / "raw", dry_run=True)
        written = ac._write_raw("dry-slug", "# Dry content\n")
        assert written is True
        # No actual file written
        assert not (tmp_path / "raw" / "dry-slug.md").exists()
        # Dry-run message goes to stderr
        captured = capsys.readouterr()
        assert "dry-run" in captured.err

    def test_creates_parent_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        nested = tmp_path / "deep" / "nested" / "raw"
        ac = reload_module(monkeypatch, nested)
        ac._write_raw("nested-slug", "content")
        assert (nested / "nested-slug.md").exists()


# ===========================================================================
# _capture_git_commit
# ===========================================================================


class TestCaptureGitCommit:
    def _make_tool_output(self, exit_code: int, stdout: str) -> dict:
        return {"exit_code": exit_code, "stdout": stdout, "stderr": ""}

    def test_feat_commit_captured(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        tool_input = {"command": "git commit -m 'feat: add new widget'"}
        tool_output = self._make_tool_output(
            0, "[main abc1234] feat: add new widget\n 1 file changed"
        )
        result = ac._capture_git_commit(tool_input, tool_output)
        assert result is True
        files = list((tmp_path / "raw").glob("auto-git-feat-*.md"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "feat: add new widget" in content
        assert "abc1234" in content

    def test_fix_commit_captured(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        tool_input = {"command": "git commit -m 'fix: null pointer error'"}
        tool_output = self._make_tool_output(0, "[main def5678] fix: null pointer error\n")
        result = ac._capture_git_commit(tool_input, tool_output)
        assert result is True
        files = list((tmp_path / "raw").glob("auto-git-fix-*.md"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "fix" in content
        assert "#negative-example" in content

    def test_refactor_commit_captured(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        tool_input = {"command": "git commit -m 'refactor: extract helper'"}
        tool_output = self._make_tool_output(0, "[main aaa0001] refactor: extract helper\n")
        result = ac._capture_git_commit(tool_input, tool_output)
        assert result is True
        files = list((tmp_path / "raw").glob("auto-git-refactor-*.md"))
        assert len(files) == 1

    def test_chore_commit_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        tool_input = {"command": "git commit -m 'chore: bump version'"}
        tool_output = self._make_tool_output(0, "[main bbb0002] chore: bump version\n")
        result = ac._capture_git_commit(tool_input, tool_output)
        assert result is False

    def test_docs_commit_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        tool_input = {"command": "git commit -m 'docs: update README'"}
        tool_output = self._make_tool_output(0, "[main ccc0003] docs: update README\n")
        result = ac._capture_git_commit(tool_input, tool_output)
        assert result is False

    def test_failed_exit_code_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        tool_input = {"command": "git commit -m 'feat: something'"}
        tool_output = self._make_tool_output(1, "error: nothing to commit")
        result = ac._capture_git_commit(tool_input, tool_output)
        assert result is False

    def test_non_git_command_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        tool_input = {"command": "pytest tests/"}
        tool_output = self._make_tool_output(0, "1 passed")
        result = ac._capture_git_commit(tool_input, tool_output)
        assert result is False

    def test_no_match_in_stdout_returns_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        tool_input = {"command": "git commit -m 'feat: something'"}
        # stdout missing the expected pattern "[branch hash] subject"
        tool_output = self._make_tool_output(0, "On branch main, nothing happened")
        result = ac._capture_git_commit(tool_input, tool_output)
        assert result is False

    def test_branch_with_slash_parsed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Branch names like feat/my-feature should still parse correctly."""
        ac = reload_module(monkeypatch, tmp_path / "raw")
        tool_input = {"command": "git commit -m 'feat: slash branch test'"}
        tool_output = self._make_tool_output(
            0, "[feat/my-feature 9ab1234] feat: slash branch test\n"
        )
        result = ac._capture_git_commit(tool_input, tool_output)
        assert result is True

    def test_stderr_log_on_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        tool_input = {"command": "git commit -m 'feat: log test'"}
        tool_output = self._make_tool_output(0, "[main feed001] feat: log test\n")
        ac._capture_git_commit(tool_input, tool_output)
        captured = capsys.readouterr()
        assert "[auto-capture]" in captured.err


# ===========================================================================
# _capture_test_failure
# ===========================================================================


class TestCaptureTestFailure:
    def _make_tool_input(self, command: str) -> dict:
        return {"command": command}

    def _make_tool_output(self, exit_code: int, stdout: str = "", stderr: str = "") -> dict:
        return {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}

    def test_pytest_failure_captured(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        stdout = (
            "FAILED tests/test_foo.py::test_bar - AssertionError: expected 1 got 2\n"
            "1 failed in 0.5s\n"
        )
        result = ac._capture_test_failure(
            self._make_tool_input("pytest tests/"),
            self._make_tool_output(1, stdout=stdout),
        )
        assert result is True
        files = list((tmp_path / "raw").glob("auto-test-failure-*.md"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "test_bar" in content
        assert "AssertionError" in content

    def test_python_m_pytest_captured(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        stdout = "FAILED tests/test_baz.py::test_x - ValueError: bad value\n"
        result = ac._capture_test_failure(
            self._make_tool_input("python -m pytest tests/"),
            self._make_tool_output(1, stdout=stdout),
        )
        assert result is True

    def test_passing_tests_not_captured(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        result = ac._capture_test_failure(
            self._make_tool_input("pytest tests/"),
            self._make_tool_output(0, stdout="5 passed in 1.0s"),
        )
        assert result is False

    def test_non_pytest_command_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        result = ac._capture_test_failure(
            self._make_tool_input("git commit -m 'fix: x'"),
            self._make_tool_output(1, stdout="error"),
        )
        assert result is False

    def test_no_failed_lines_returns_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        # Non-zero exit but no FAILED lines
        result = ac._capture_test_failure(
            self._make_tool_input("pytest tests/"),
            self._make_tool_output(1, stdout="ERROR collecting tests/\n"),
        )
        assert result is False

    def test_short_failed_format_captured(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Short format: FAILED tests/test_x.py::test_y (no dash-reason)."""
        ac = reload_module(monkeypatch, tmp_path / "raw")
        stdout = "FAILED tests/test_x.py::test_y\n1 failed\n"
        result = ac._capture_test_failure(
            self._make_tool_input("pytest tests/"),
            self._make_tool_output(1, stdout=stdout),
        )
        assert result is True

    def test_failures_from_stderr_captured(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """FAILED lines in stderr (some pytest configs write there) should be picked up."""
        ac = reload_module(monkeypatch, tmp_path / "raw")
        stderr = "FAILED tests/test_z.py::test_w - RuntimeError: bang\n"
        result = ac._capture_test_failure(
            self._make_tool_input("pytest tests/"),
            self._make_tool_output(1, stdout="", stderr=stderr),
        )
        assert result is True

    def test_multiple_failures_capped_at_5(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        lines = "\n".join(f"FAILED tests/test_f.py::test_{i} - Error {i}" for i in range(10))
        ac._capture_test_failure(
            self._make_tool_input("pytest tests/"),
            self._make_tool_output(1, stdout=lines),
        )
        files = list((tmp_path / "raw").glob("auto-test-failure-*.md"))
        content = files[0].read_text(encoding="utf-8")
        # Content should contain at most 5 failure lines (- `...`)
        captured_failures = [ln for ln in content.splitlines() if ln.startswith("- `")]
        assert len(captured_failures) <= 5

    def test_idempotent_same_hash(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Same failure output → same slug → second call returns False (no overwrite)."""
        ac = reload_module(monkeypatch, tmp_path / "raw")
        stdout = "FAILED tests/test_idem.py::test_once - SomeError\n"
        tool_input = self._make_tool_input("pytest tests/")
        tool_output = self._make_tool_output(1, stdout=stdout)
        first = ac._capture_test_failure(tool_input, tool_output)
        second = ac._capture_test_failure(tool_input, tool_output)
        assert first is True
        assert second is False

    def test_content_includes_command(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        cmd = "pytest tests/ -k slow"
        stdout = "FAILED tests/test_slow.py::test_db - TimeoutError\n"
        ac._capture_test_failure(
            self._make_tool_input(cmd),
            self._make_tool_output(1, stdout=stdout),
        )
        files = list((tmp_path / "raw").glob("auto-test-failure-*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "pytest tests/ -k slow" in content


# ===========================================================================
# Secret redaction (F-13, security audit 2026-07-12)
# ===========================================================================


class TestSecretRedactionOnWrite:
    """Raw notes are a global, cross-session artifact (~/.claude/memory/_auto/raw/)
    read back by knowledge_librarian.py -- secrets that leak into pytest output
    or a commit subject must be scrubbed before they're persisted here, not just
    when re-injected into a prompt later."""

    def test_aws_key_redacted_from_test_failure_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        secret = "AKIAIOSFODNN7EXAMPLE"
        stdout = f"FAILED tests/test_conn.py::test_db - ConnectionError: key={secret} rejected\n"
        ac._capture_test_failure(
            self._capture_test_failure_input("pytest tests/"),
            {"exit_code": 1, "stdout": stdout, "stderr": ""},
        )
        files = list((tmp_path / "raw").glob("auto-test-failure-*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert secret not in content
        assert "[REDACTED-AWS-KEY]" in content

    def test_secret_env_assignment_redacted_from_command(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        cmd = "MY_API_TOKEN=abcdef123456 pytest tests/"
        stdout = "FAILED tests/test_x.py::test_y - Error\n"
        ac._capture_test_failure(
            self._capture_test_failure_input(cmd),
            {"exit_code": 1, "stdout": stdout, "stderr": ""},
        )
        files = list((tmp_path / "raw").glob("auto-test-failure-*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert "abcdef123456" not in content
        assert "[REDACTED]" in content

    def test_secret_in_commit_subject_redacted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ac = reload_module(monkeypatch, tmp_path / "raw")
        secret = "sk-ant-XXXXXXXXXXXXXXXXXXXXXXXX"
        tool_input = {"command": f"git commit -m 'fix: rotate {secret}'"}
        tool_output = {
            "exit_code": 0,
            "stdout": f"[main abc1234] fix: rotate {secret}\n",
            "stderr": "",
        }
        result = ac._capture_git_commit(tool_input, tool_output)
        assert result is True
        files = list((tmp_path / "raw").glob("auto-git-fix-*.md"))
        content = files[0].read_text(encoding="utf-8")
        assert secret not in content
        assert "[REDACTED" in content

    @staticmethod
    def _capture_test_failure_input(command: str) -> dict:
        return {"command": command}
