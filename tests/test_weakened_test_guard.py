"""Tests for weakened_test_guard.py — detect tests weakened to force a pass."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from weakened_test_guard import _is_test_file, _weakening_signals


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
