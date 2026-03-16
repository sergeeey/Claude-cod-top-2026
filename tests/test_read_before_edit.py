"""Unit tests for hooks/read_before_edit.py — Edit/Write reminder."""

import io

import pytest

# WHY: We test the logic directly since main() reads from stdin.
# Import the module and test tool_name filtering logic.


class TestReadBeforeEdit:
    def test_edit_triggers_warning(self, make_hook_input, capsys, monkeypatch):
        """Edit tool should print a warning to stderr."""
        stdin_data = make_hook_input("Edit", {"file_path": "/tmp/test.py"})
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin_data))

        from read_before_edit import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "Read this file first" in captured.err

    def test_write_no_warning(self, make_hook_input, capsys, monkeypatch):
        """Write tool should NOT print a warning (new files are OK)."""
        stdin_data = make_hook_input("Write", {"file_path": "/tmp/new.py"})
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin_data))

        from read_before_edit import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert captured.err == ""

    def test_other_tool_exits_silently(self, make_hook_input, capsys, monkeypatch):
        """Non Edit/Write tools should exit without any output."""
        stdin_data = make_hook_input("Read", {"file_path": "/tmp/test.py"})
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin_data))

        from read_before_edit import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_no_file_path_exits_silently(self, make_hook_input, capsys, monkeypatch):
        """Edit without file_path should exit silently."""
        stdin_data = make_hook_input("Edit", {})
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin_data))

        from read_before_edit import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
