"""Tests for artifact_schema_validator.py — JSON validation in watched dirs.

Imports the hook directly from repo/hooks/ (via conftest sys.path injection)
so coverage counts on CI, not only when ~/.claude/hooks/ exists locally.
"""

from __future__ import annotations

import io
from unittest.mock import patch

from artifact_schema_validator import _in_watched_dir, _validate


def _capture_stderr(fn, *args, **kwargs) -> str:
    buf = io.StringIO()
    with patch("sys.stderr", buf):
        fn(*args, **kwargs)
    return buf.getvalue()


class TestInWatchedDir:
    def test_experiments_path_is_watched(self) -> None:
        assert _in_watched_dir("experiments/20260601-foo/metrics/run.json") is True

    def test_metrics_path_is_watched(self) -> None:
        assert _in_watched_dir("metrics/run.json") is True

    def test_results_path_is_watched(self) -> None:
        assert _in_watched_dir("results/something.json") is True

    def test_src_path_is_not_watched(self) -> None:
        assert _in_watched_dir("src/config/app.json") is False

    def test_random_path_is_not_watched(self) -> None:
        assert _in_watched_dir("README.md") is False


class TestValidate:
    def test_valid_json_in_watched_dir_no_warning(self) -> None:
        """Valid JSON in experiments/ → silence."""
        stderr = _capture_stderr(
            _validate,
            "experiments/20260601-foo/metrics/run.json",
            '{"auc": 0.92, "n": 100}',
        )
        assert stderr == "", f"Expected no warning, got: {stderr}"

    def test_invalid_json_in_watched_dir_emits_warning(self) -> None:
        """Malformed JSON in metrics/ → stderr warning."""
        stderr = _capture_stderr(
            _validate,
            "metrics/run.json",
            '{"auc": 0.92, broken}',
        )
        assert "WARN" in stderr, "Expected WARN on invalid JSON"
        assert "artifact_schema_validator" in stderr

    def test_valid_json_outside_watched_dirs_ignored(self) -> None:
        """Valid JSON in unrelated directory → no warning."""
        stderr = _capture_stderr(
            _validate,
            "src/config/app.json",
            '{"debug": true}',
        )
        assert stderr == "", f"Expected no warning for unwatched dir, got: {stderr}"

    def test_invalid_json_outside_watched_dirs_ignored(self) -> None:
        """Even invalid JSON outside watched dirs → no warning (not our concern)."""
        stderr = _capture_stderr(
            _validate,
            "src/config/broken.json",
            '{"oops": ',
        )
        assert stderr == "", f"Expected silence outside watched dirs, got: {stderr}"

    def test_non_json_file_in_watched_dir_ignored(self) -> None:
        """Non-.json file → no validation attempt."""
        stderr = _capture_stderr(
            _validate,
            "experiments/foo/notes.md",
            "# Notes",
        )
        assert stderr == ""
