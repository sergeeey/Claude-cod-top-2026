"""Tests for utils.secure_append_env_file() -- F-07, security audit 2026-07-12.

WHY: env_reload.py / direnv_loader.py append real .env secret values to
$CLAUDE_ENV_FILE for an external shell wrapper to source. This tests the
shared append+chmod helper directly (append behavior + best-effort chmod,
not the hooks' own routing logic).
"""

import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from utils import secure_append_env_file


def test_appends_text(tmp_path: Path):
    target = tmp_path / "claude_env"
    target.write_text("existing\n", encoding="utf-8")
    result = secure_append_env_file(target, "export FOO=bar\n")
    assert result is True
    assert target.read_text(encoding="utf-8") == "existing\nexport FOO=bar\n"


def test_creates_file_if_missing(tmp_path: Path):
    target = tmp_path / "new_claude_env"
    result = secure_append_env_file(target, "export FOO=bar\n")
    assert result is True
    assert target.exists()
    assert "export FOO=bar" in target.read_text(encoding="utf-8")


def test_returns_false_on_write_oserror(tmp_path: Path):
    target = tmp_path / "unwritable"
    with patch("builtins.open", side_effect=OSError("disk full")):
        result = secure_append_env_file(target, "export FOO=bar\n")
    assert result is False


def test_chmod_failure_does_not_crash(tmp_path: Path):
    """Windows / some filesystems reject chmod bits -- must not raise."""
    target = tmp_path / "claude_env"
    with patch("os.chmod", side_effect=OSError("not supported")):
        result = secure_append_env_file(target, "export FOO=bar\n")
    assert result is True  # write still succeeded
    assert "export FOO=bar" in target.read_text(encoding="utf-8")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
def test_chmod_restricts_to_owner_only(tmp_path: Path):
    target = tmp_path / "claude_env"
    secure_append_env_file(target, "export FOO=bar\n")
    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600
