"""Tests for hooks/goal_stub_detector.py — PostToolUse stub-pattern blocker.

WHY: 0% coverage before this file. main() reads a PostToolUse event from
stdin and calls sys.exit(0|2) -- tested via monkeypatching sys.stdin and
capturing SystemExit, with tmp_path standing in for the edited file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from goal_stub_detector import is_excluded, main


def _stdin_event(monkeypatch, tool_name, file_path):
    payload = json.dumps({"tool_name": tool_name, "tool_input": {"file_path": str(file_path)}})
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(payload))


class TestIsExcluded:
    def test_excludes_tests_directory(self):
        assert is_excluded(Path("repo/tests/foo.py")) is True

    def test_excludes_nested_tests_directory(self):
        assert is_excluded(Path("repo/sub/tests/foo.py")) is True

    def test_excludes_test_prefixed_file(self):
        assert is_excluded(Path("repo/hooks/test_foo.py")) is True

    def test_does_not_exclude_normal_hook_file(self):
        assert is_excluded(Path("repo/hooks/foo.py")) is False


class TestMain:
    def test_exits_zero_on_unparseable_stdin(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", __import__("io").StringIO("not json"))
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_exits_zero_for_non_edit_write_tool(self, monkeypatch, tmp_path):
        _stdin_event(monkeypatch, "Read", tmp_path / "foo.py")
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_exits_zero_when_file_path_missing(self, monkeypatch):
        monkeypatch.setattr(
            sys, "stdin", __import__("io").StringIO(json.dumps({"tool_name": "Write"}))
        )
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_exits_zero_for_non_python_file(self, monkeypatch, tmp_path):
        target = tmp_path / "notes.md"
        target.write_text("TODO: fix this", encoding="utf-8")
        _stdin_event(monkeypatch, "Write", target)
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_exits_zero_for_excluded_test_file(self, monkeypatch, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        target = tests_dir / "test_something.py"
        target.write_text("# TODO: fix this test", encoding="utf-8")
        _stdin_event(monkeypatch, "Write", target)
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_exits_zero_when_file_unreadable(self, monkeypatch, tmp_path):
        missing = tmp_path / "does_not_exist.py"
        _stdin_event(monkeypatch, "Write", missing)
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_exits_zero_when_no_stub_patterns_found(self, monkeypatch, tmp_path):
        target = tmp_path / "clean.py"
        target.write_text("def f():\n    return 1\n", encoding="utf-8")
        _stdin_event(monkeypatch, "Write", target)
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_blocks_on_todo(self, monkeypatch, tmp_path, capsys):
        target = tmp_path / "stubby.py"
        target.write_text("def f():\n    pass  # TODO: implement\n", encoding="utf-8")
        _stdin_event(monkeypatch, "Write", target)
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "STUB_DETECTED" in err
        assert "TODO" in err

    def test_blocks_on_not_implemented_error(self, monkeypatch, tmp_path):
        target = tmp_path / "stubby2.py"
        target.write_text("def f():\n    raise NotImplementedError\n", encoding="utf-8")
        _stdin_event(monkeypatch, "Write", target)
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2

    def test_edit_tool_is_also_checked(self, monkeypatch, tmp_path):
        target = tmp_path / "stubby3.py"
        target.write_text("pass  # stub\n", encoding="utf-8")
        _stdin_event(monkeypatch, "Edit", target)
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2


class TestRealProcessExitCode:
    """Subprocess-level regression for the hook_main exit-code-swallow bug
    (bottleneck #2 fix, 2026-08-29; caught by independent reviewer, not by
    any pre-existing test in this file). Every test above calls main()
    directly, bypassing the `if __name__ == "__main__": hook_main(main, ...)`
    wrapper entirely -- that wrapper is exactly what silently discarded
    main()'s sys.exit(2) and turned it into a real process exit(0), and no
    amount of direct-main() unit testing can see through it. This class
    launches the actual script as a subprocess, exercising the real entry
    point end to end."""

    _SCRIPT = Path(__file__).parent.parent / "hooks" / "goal_stub_detector.py"

    def _run(self, tool_input: dict) -> int:
        import subprocess

        payload = json.dumps({"tool_name": "Write", "tool_input": tool_input})
        result = subprocess.run(
            [sys.executable, str(self._SCRIPT)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode

    def test_real_process_exits_2_on_stub(self, tmp_path):
        target = tmp_path / "real_stub.py"
        target.write_text("def f():\n    pass  # TODO: implement\n", encoding="utf-8")
        assert self._run({"file_path": str(target)}) == 2

    def test_real_process_exits_0_on_clean_file(self, tmp_path):
        target = tmp_path / "real_clean.py"
        target.write_text("def f():\n    return 1\n", encoding="utf-8")
        assert self._run({"file_path": str(target)}) == 0
