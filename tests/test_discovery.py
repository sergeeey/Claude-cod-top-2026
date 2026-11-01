"""Tests for hooks/lib/discovery.py's Git-Bash drive-path normalization.

WHY this file exists: `extract_command_cwd()` returned a Git-Bash-style
POSIX drive path (e.g. `/d/cc-wt/f2`) verbatim, and both `pre_commit_guard.py`
and `gitnexus_reindex.py` fed that straight into `subprocess.run(cwd=...)`.
On Windows this crashes with `NotADirectoryError [WinError 267]` ("invalid
folder name") -- confirmed live via a direct `subprocess.run` reproduction,
not guessed -- because Windows has no notion of Git-Bash's drive-letter
convention: a leading slash means "root of the current drive, then literal
segments," not "drive letter follows." Found committing from a worktree via
`cd <git-bash-spelling-of-D:\\...> && git commit ...` (2026-09-12).
"""

import os
import subprocess
import sys

import pytest
from lib import discovery


class TestNormalizeGitbashDrivePath:
    """Cross-platform-safe unit tests of the pure string transform -- these
    force the Windows branch via `monkeypatch` so they run on Linux CI too,
    independent of the real-subprocess tests below (which can only run ON
    Windows, since that's the only platform the underlying bug exists on)."""

    def test_normalizes_gitbash_drive_path_to_native_form_on_windows(self, monkeypatch) -> None:
        monkeypatch.setattr(discovery.sys, "platform", "win32")
        assert discovery._normalize_gitbash_drive_path("/d/cc-wt/f2") == "D:\\cc-wt\\f2"
        assert discovery._normalize_gitbash_drive_path("/D/cc-wt/f2") == "D:\\cc-wt\\f2"

    def test_leaves_path_untouched_on_non_windows(self, monkeypatch) -> None:
        monkeypatch.setattr(discovery.sys, "platform", "linux")
        assert discovery._normalize_gitbash_drive_path("/d/cc-wt/f2") == "/d/cc-wt/f2"

    def test_does_not_touch_bare_single_letter_paths_even_on_windows(self, monkeypatch) -> None:
        """Guard against a collision with test_pre_commit_guard.py's own
        fixtures: `/a` and `/b` there (test_multi_cd_chain_resolves_to_the_
        LAST_cd et al) are generic cd-chain stand-ins, not Git-Bash drive
        paths -- a naive `^/[A-Za-z]$` pattern would have silently mangled
        them into `A:\\`/`B:\\` on a Windows test run. Only a drive letter
        FOLLOWED BY a real sub-path is normalized -- nobody `cd`s to the bare
        root of a drive before running `git commit`."""
        monkeypatch.setattr(discovery.sys, "platform", "win32")
        assert discovery._normalize_gitbash_drive_path("/a") == "/a"
        assert discovery._normalize_gitbash_drive_path("/b") == "/b"
        assert discovery._normalize_gitbash_drive_path("/repo/other") == "/repo/other"

    def test_already_native_windows_path_is_left_untouched(self, monkeypatch) -> None:
        monkeypatch.setattr(discovery.sys, "platform", "win32")
        path = "E:\\path with spaces"
        assert discovery._normalize_gitbash_drive_path(path) == path

    def test_extract_command_cwd_applies_normalization_on_windows(self, monkeypatch) -> None:
        """End-to-end at the public function level (not just the private
        helper): `extract_command_cwd` is what pre_commit_guard.py and
        gitnexus_reindex.py actually call."""
        monkeypatch.setattr(discovery.sys, "platform", "win32")
        cwd = discovery.extract_command_cwd('cd /d/cc-wt/f2 && git commit -m "x"')
        assert cwd == "D:\\cc-wt\\f2"


def _gitbash_spelling_of(native_path: str) -> str:
    """The Git-Bash spelling Windows subprocess.run(cwd=...) cannot resolve:
    lowercase drive letter, no colon, forward slashes -- `D:\\foo\\bar` ->
    `/d/foo/bar`."""
    drive_letter, rest = native_path[0], native_path[2:].replace("\\", "/")
    return f"/{drive_letter.lower()}{rest}"


@pytest.mark.skipif(sys.platform != "win32", reason="Git-Bash drive-path bug is Windows-only")
class TestRealSubprocessReproduction:
    """The two guarantees the reported bug requires: (1) the RAW, unnormalized
    Git-Bash spelling actually crashes a real subprocess.run(cwd=...) call
    (proves the bug is real, not hypothetical), and (2) the NORMALIZED path
    resolves to the exact same existing directory as the native spelling
    (proves the fix, not just "doesn't crash"). A mock or an in-process
    monkeypatch of the platform check alone would not catch this -- the bug
    lives in what path STRING actually reaches the Windows OS call."""

    def test_unnormalized_gitbash_spelling_crashes_real_subprocess_run(self, tmp_path) -> None:
        gitbash_spelling = _gitbash_spelling_of(str(tmp_path))
        with pytest.raises(OSError):
            subprocess.run(
                [sys.executable, "-c", "pass"],
                cwd=gitbash_spelling,
                capture_output=True,
                text=True,
                timeout=10,
            )

    def test_gitbash_and_native_spellings_resolve_the_same_existing_directory(
        self, tmp_path
    ) -> None:
        native = str(tmp_path)
        gitbash_spelling = _gitbash_spelling_of(native)

        cwd = discovery.extract_command_cwd(f'cd {gitbash_spelling} && git commit -m "x"')

        def _report_cwd(cwd_arg: str) -> str:
            result = subprocess.run(
                [sys.executable, "-c", "import os; print(os.getcwd())"],
                cwd=cwd_arg,
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.returncode == 0, result.stderr
            return result.stdout.strip()

        from_gitbash_spelling = _report_cwd(cwd)
        from_native_spelling = _report_cwd(native)
        assert from_gitbash_spelling == from_native_spelling
        assert os.path.normcase(from_gitbash_spelling) == os.path.normcase(native)
