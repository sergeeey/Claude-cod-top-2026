"""Tests for weakened_test_guard.py — detect tests weakened to force a pass."""

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import weakened_test_guard  # noqa: E402
from hook_state import HookState  # noqa: E402
from weakened_test_guard import _is_test_file, _weakening_signals  # noqa: E402


class TestIsTestFile:
    def test_test_prefix(self):
        assert _is_test_file("tests/test_foo.py")

    def test_test_suffix(self):
        assert _is_test_file("src/foo_test.py")

    def test_under_tests_dir(self):
        assert _is_test_file("a/tests/helpers.py")

    def test_not_python(self):
        assert not _is_test_file("tests/test_foo.txt")

    def test_regular_source(self):
        assert not _is_test_file("src/foo.py")


class TestWeakeningSignals:
    def test_removed_assertion(self):
        old = "def test_x():\n    assert a == 1\n    assert b == 2\n"
        new = "def test_x():\n    assert a == 1\n"
        sigs = _weakening_signals(old, new)
        assert any("dropped" in s for s in sigs)

    def test_skip_added(self):
        old = "def test_x():\n    assert a == 1\n"
        new = "@pytest.mark.skip\ndef test_x():\n    assert a == 1\n"
        sigs = _weakening_signals(old, new)
        assert any("skip" in s for s in sigs)

    def test_xfail_added(self):
        old = "def test_x():\n    assert a == 1\n"
        new = "@pytest.mark.xfail\ndef test_x():\n    assert a == 1\n"
        sigs = _weakening_signals(old, new)
        assert any("skip/xfail" in s for s in sigs)

    def test_tautology_added(self):
        old = "def test_x():\n    assert compute() == 42\n"
        new = "def test_x():\n    assert True\n"
        sigs = _weakening_signals(old, new)
        # both: assertion count same (1->1) but tautology + the real assert gone
        assert any("tautolog" in s for s in sigs)

    def test_commented_out_assertion(self):
        old = "def test_x():\n    assert a == 1\n    assert b == 2\n"
        new = "def test_x():\n    assert a == 1\n    # assert b == 2\n"
        sigs = _weakening_signals(old, new)
        assert any("commented out" in s for s in sigs)

    def test_no_weakening_on_strengthen(self):
        old = "def test_x():\n    assert a == 1\n"
        new = "def test_x():\n    assert a == 1\n    assert b == 2\n"
        assert _weakening_signals(old, new) == []

    def test_no_weakening_on_refactor(self):
        old = "def test_x():\n    assert foo() == 1\n"
        new = "def test_x():\n    result = foo()\n    assert result == 1\n"
        assert _weakening_signals(old, new) == []

    def test_unittest_assert_removed_now_detected(self):
        """Regression (MEDIUM, hooks-02 audit): removing `self.assertEqual(a, b)`
        while adding an unrelated bare `assert` kept the bare-assert count
        unchanged (0 -> 1 old, still net removal), so the old bare-assert-only
        counter missed it entirely in a unittest.TestCase-style suite."""
        old = "def test_x(self):\n    self.assertEqual(a, b)\n"
        new = "def test_x(self):\n    pass\n"
        sigs = _weakening_signals(old, new)
        assert any("dropped" in s for s in sigs)

    def test_unittest_assert_replaced_by_unrelated_bare_assert_still_detected(self):
        old = "def test_x(self):\n    self.assertEqual(a, b)\n"
        new = "def test_x(self):\n    assert True\n"
        sigs = _weakening_signals(old, new)
        # net assertion count 1 -> 1 (self.assertEqual replaced by assert True),
        # but it must still be caught -- via the tautology signal, since the
        # total-assert-count itself didn't drop here.
        assert any("tautolog" in s for s in sigs)

    def test_unittest_assert_true_removed_is_a_real_drop(self):
        old = "def test_x(self):\n    self.assertTrue(condition)\n    self.assertIn(x, y)\n"
        new = "def test_x(self):\n    self.assertTrue(condition)\n"
        sigs = _weakening_signals(old, new)
        assert any("dropped" in s for s in sigs)

    def test_skipif_added_now_detected(self):
        """Regression (MEDIUM, hooks-02 audit): `@pytest.mark.skipif(...)`
        disables a test just as effectively as `@pytest.mark.skip`, but the
        old regex only matched the bare `skip`/`xfail` decorator names."""
        old = "def test_x():\n    assert a == 1\n"
        new = "@pytest.mark.skipif(True, reason='flaky')\ndef test_x():\n    assert a == 1\n"
        sigs = _weakening_signals(old, new)
        assert any("skip/xfail" in s for s in sigs)


def _run_main(monkeypatch, tmp_path, data: dict) -> str:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        try:
            weakened_test_guard.main()
        except SystemExit:
            pass
    return buf.getvalue()


class TestWriteBypassFix:
    """Regression (HIGH, hooks-02 audit): replacing a whole EXISTING test
    file via `Write` (not `Edit`) previously skipped weakening detection
    entirely, since the guard only ever handled Edit's old_string/new_string
    pair. A PreToolUse(Write) leg stashes the file's prior content; the
    PostToolUse(Write) leg compares it against what was just written."""

    def test_write_replacing_existing_test_with_weakened_content_warns(self, monkeypatch, tmp_path):
        test_file = tmp_path / "test_foo.py"
        test_file.write_text("def test_x():\n    assert a == 1\n    assert b == 2\n")

        pre_data = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(test_file), "content": "IGNORED"},
        }
        _run_main(monkeypatch, tmp_path, pre_data)

        post_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(test_file),
                "content": "def test_x():\n    assert a == 1\n",
            },
            "tool_response": {"success": True},
        }
        out = _run_main(monkeypatch, tmp_path, post_data)
        assert "dropped" in out

    def test_write_to_brand_new_test_file_does_not_warn(self, monkeypatch, tmp_path):
        """Authoring a new test file (no prior content exists) must not be
        treated as weakening -- there is nothing to compare against."""
        test_file = tmp_path / "test_new.py"

        pre_data = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(test_file), "content": "IGNORED"},
        }
        _run_main(monkeypatch, tmp_path, pre_data)

        post_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(test_file),
                "content": "def test_x():\n    assert True\n",
            },
            "tool_response": {"success": True},
        }
        out = _run_main(monkeypatch, tmp_path, post_data)
        assert out == ""

    def test_write_pending_stash_is_consumed_not_leaked(self, monkeypatch, tmp_path):
        """The stashed content must be popped after use, not accumulate
        forever in state across unrelated Write calls to other files."""
        test_file = tmp_path / "test_foo.py"
        test_file.write_text("def test_x():\n    assert a == 1\n")

        pre_data = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(test_file), "content": "IGNORED"},
        }
        _run_main(monkeypatch, tmp_path, pre_data)

        post_data = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(test_file), "content": "def test_x():\n    pass\n"},
            "tool_response": {"success": True},
        }
        _run_main(monkeypatch, tmp_path, post_data)

        state = HookState("weakened_test_guard")
        assert state.get("pending", {}) == {}

    def test_write_to_non_test_file_is_ignored(self, monkeypatch, tmp_path):
        src_file = tmp_path / "foo.py"
        src_file.write_text("def compute():\n    return 1\n")

        pre_data = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(src_file), "content": "IGNORED"},
        }
        out = _run_main(monkeypatch, tmp_path, pre_data)
        assert out == ""


class TestEditDoesNotDoubleFire:
    """Regression: this hook is registered under BOTH PreToolUse(Edit|Write)
    and PostToolUse(Edit|Write) -- PreToolUse is needed for the Write-stash
    leg, but without gating on is_post, a single Edit call would run the
    SAME weakening check twice (once per phase) and could warn twice."""

    def test_edit_at_pretooluse_does_not_warn(self, monkeypatch, tmp_path):
        data = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "test_foo.py",
                "old_string": "assert a == 1\n    assert b == 2\n",
                "new_string": "assert a == 1\n",
            },
        }
        out = _run_main(monkeypatch, tmp_path, data)
        assert out == ""

    def test_edit_at_posttooluse_warns_exactly_once(self, monkeypatch, tmp_path):
        data = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "test_foo.py",
                "old_string": "assert a == 1\n    assert b == 2\n",
                "new_string": "assert a == 1\n",
            },
            "tool_response": {"success": True},
        }
        out = _run_main(monkeypatch, tmp_path, data)
        assert out.count("WEAKEN") == 1


class TestMultiEditHandling:
    """Regression (cross-model audit): the "Edit|Write" matcher is an
    unanchored regex -- "Edit" matches as a substring of "MultiEdit" -- so
    this hook was ALREADY being invoked for MultiEdit calls, just silently
    falling through with zero detection since MultiEdit carries a batch
    `edits` list, not a single old_string/new_string pair."""

    def test_multiedit_weakening_detected(self, monkeypatch, tmp_path):
        data = {
            "tool_name": "MultiEdit",
            "tool_input": {
                "file_path": "test_foo.py",
                "edits": [
                    {"old_string": "assert a == 1\n", "new_string": "assert True\n"},
                    {"old_string": "assert b == 2\n", "new_string": "pass\n"},
                ],
            },
            "tool_response": {"success": True},
        }
        out = _run_main(monkeypatch, tmp_path, data)
        assert "WEAKEN" in out

    def test_multiedit_at_pretooluse_does_not_warn(self, monkeypatch, tmp_path):
        data = {
            "tool_name": "MultiEdit",
            "tool_input": {
                "file_path": "test_foo.py",
                "edits": [{"old_string": "assert a == 1\n", "new_string": "assert True\n"}],
            },
        }
        out = _run_main(monkeypatch, tmp_path, data)
        assert out == ""

    def test_multiedit_no_weakening_is_silent(self, monkeypatch, tmp_path):
        data = {
            "tool_name": "MultiEdit",
            "tool_input": {
                "file_path": "test_foo.py",
                "edits": [{"old_string": "assert a == 1\n", "new_string": "assert a == 2\n"}],
            },
            "tool_response": {"success": True},
        }
        out = _run_main(monkeypatch, tmp_path, data)
        assert out == ""

    def test_multiedit_on_non_test_file_ignored(self, monkeypatch, tmp_path):
        data = {
            "tool_name": "MultiEdit",
            "tool_input": {
                "file_path": "foo.py",
                "edits": [{"old_string": "assert a == 1\n", "new_string": "assert True\n"}],
            },
            "tool_response": {"success": True},
        }
        out = _run_main(monkeypatch, tmp_path, data)
        assert out == ""
