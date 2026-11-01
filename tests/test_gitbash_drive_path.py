"""Git-Bash drive paths (`/d/cc-wt/f2`) must become native Windows paths on win32 only."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "hooks" / "lib"))

import discovery  # noqa: E402


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("/d/cc-wt/f2", "D:\\cc-wt\\f2"),
        ("/D/x", "D:\\x"),
        ("/c/Users/a b", "C:\\Users\\a b"),
    ],
)
def test_gitbash_drive_path_is_converted_on_windows(monkeypatch, given, expected):
    monkeypatch.setattr(discovery.sys, "platform", "win32")
    assert discovery._normalize_gitbash_drive_path(given) == expected


@pytest.mark.parametrize("given", ["/d", "/d/", "d/x", "./d/x", "/tmp/x", "/proc/x"])
def test_non_drive_paths_are_left_alone_on_windows(monkeypatch, given):
    monkeypatch.setattr(discovery.sys, "platform", "win32")
    assert discovery._normalize_gitbash_drive_path(given) == given


def test_nothing_is_converted_off_windows(monkeypatch):
    monkeypatch.setattr(discovery.sys, "platform", "linux")
    assert discovery._normalize_gitbash_drive_path("/d/cc-wt/f2") == "/d/cc-wt/f2"
