"""Tests for observation_capture.py — session observation logger."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))


@pytest.fixture()
def tmp_raw(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    import observation_capture as oc

    monkeypatch.setattr(oc, "RAW_DIR", raw)
    return raw


class TestEditObservation:
    def test_creates_session_log(self, tmp_raw: Path) -> None:
        import observation_capture as oc

        oc._append_observation(
            "Edit",
            {"file_path": "foo.py", "old_string": "a", "new_string": "abc"},
            {"exit_code": 0},
        )
        logs = list(tmp_raw.glob("session-*.md"))
        assert len(logs) == 1

    def test_log_contains_file_path(self, tmp_raw: Path) -> None:
        import observation_capture as oc

        oc._append_observation(
            "Edit",
            {"file_path": "hooks/foo.py", "old_string": "x", "new_string": "xy"},
            {},
        )
        content = next(tmp_raw.glob("session-*.md")).read_text()
        assert "hooks/foo.py" in content

    def test_delta_positive(self, tmp_raw: Path) -> None:
        import observation_capture as oc

        oc._append_observation(
            "Edit",
            {"file_path": "a.py", "old_string": "x", "new_string": "xyz"},
            {},
        )
        content = next(tmp_raw.glob("session-*.md")).read_text()
        assert "+2" in content

    def test_delta_negative(self, tmp_raw: Path) -> None:
        import observation_capture as oc

        oc._append_observation(
            "Edit",
            {"file_path": "a.py", "old_string": "abcde", "new_string": "x"},
            {},
        )
        content = next(tmp_raw.glob("session-*.md")).read_text()
        assert "-4" in content

    def test_failed_edit_not_logged(self, tmp_raw: Path) -> None:
        import observation_capture as oc

        result = oc._append_observation(
            "Edit",
            {"file_path": "a.py", "old_string": "x", "new_string": "y"},
            {"exit_code": 1},
        )
        assert result is False
        assert not list(tmp_raw.glob("session-*.md"))

    def test_returns_true_on_success(self, tmp_raw: Path) -> None:
        import observation_capture as oc

        result = oc._append_observation(
            "Edit",
            {"file_path": "a.py", "old_string": "x", "new_string": "xy"},
            {},
        )
        assert result is True


class TestWriteObservation:
    def test_write_logged(self, tmp_raw: Path) -> None:
        import observation_capture as oc

        oc._append_observation(
            "Write",
            {"file_path": "new.py", "content": "hello world"},
            {},
        )
        content = next(tmp_raw.glob("session-*.md")).read_text()
        assert "new.py" in content
        assert "11 chars" in content

    def test_write_returns_true(self, tmp_raw: Path) -> None:
        import observation_capture as oc

        result = oc._append_observation(
            "Write",
            {"file_path": "new.py", "content": "x"},
            {},
        )
        assert result is True


class TestSizeGuard:
    def test_stops_at_size_limit(self, tmp_raw: Path) -> None:
        import observation_capture as oc

        log = oc._get_session_log()
        log.write_text("x" * (oc.MAX_SESSION_LOG_BYTES + 1), encoding="utf-8")
        result = oc._append_observation(
            "Edit",
            {"file_path": "a.py", "old_string": "x", "new_string": "y"},
            {},
        )
        assert result is False


class TestIgnoredTools:
    def test_read_not_logged(self, tmp_raw: Path) -> None:
        import observation_capture as oc

        result = oc._append_observation("Read", {"file_path": "a.py"}, {})
        assert result is False

    def test_bash_not_logged(self, tmp_raw: Path) -> None:
        import observation_capture as oc

        result = oc._append_observation("Bash", {"command": "ls"}, {})
        assert result is False

    def test_unknown_tool_not_logged(self, tmp_raw: Path) -> None:
        import observation_capture as oc

        result = oc._append_observation("Glob", {"pattern": "*.py"}, {})
        assert result is False


class TestSessionHeader:
    def test_header_contains_marker(self, tmp_raw: Path) -> None:
        import observation_capture as oc

        oc._append_observation(
            "Edit",
            {"file_path": "a.py", "old_string": "x", "new_string": "y"},
            {},
        )
        content = next(tmp_raw.glob("session-*.md")).read_text()
        assert "Session Observations" in content
        assert "#session-log" in content

    def test_idempotent_header(self, tmp_raw: Path) -> None:
        import observation_capture as oc

        oc._append_observation(
            "Edit",
            {"file_path": "a.py", "old_string": "x", "new_string": "y"},
            {},
        )
        oc._append_observation(
            "Edit",
            {"file_path": "b.py", "old_string": "x", "new_string": "y"},
            {},
        )
        logs = list(tmp_raw.glob("session-*.md"))
        assert len(logs) == 1
        content = logs[0].read_text()
        assert content.count("# Session Observations") == 1


class TestConcurrentFirstObservation:
    """Regression (MEDIUM, cross-model audit): on the FIRST observation of
    a day, two concurrent hook invocations could both see log_path.exists()
    == False in _ensure_header(), so both call write_text() to create the
    header -- the second write truncates whatever the first process had
    already appended."""

    def test_six_concurrent_first_observations_none_lost(self, tmp_raw: Path) -> None:
        import threading

        import observation_capture as oc

        def append_one(i: int) -> None:
            oc._append_observation(
                "Edit",
                {"file_path": f"file_{i}.py", "old_string": "x", "new_string": "xy"},
                {},
            )

        # WHY 6 threads, not a larger number: see doc_registry's sibling
        # test for the full explanation.
        threads = [threading.Thread(target=append_one, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        logs = list(tmp_raw.glob("session-*.md"))
        assert len(logs) == 1
        content = logs[0].read_text()
        # WHY exactly one header, and all lines present: without the
        # lock, a header-write race could truncate earlier appends, or
        # concurrent appends racing the header write could corrupt the file.
        assert content.count("# Session Observations") == 1
        for i in range(6):
            assert f"file_{i}.py" in content, f"file_{i}.py observation lost to a race"
