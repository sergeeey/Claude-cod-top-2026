"""session_start warns when activeContext's recorded main SHA lags the repo (advisory)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

import session_start  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-qm", name)
    return _git(repo, "rev-parse", "--short", "HEAD")


def _repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    return tmp_path


def _ctx(sha: str) -> str:
    return f"| **branch** | `main` = `{sha}` [VERIFIED: x] |\n"


def test_current_sha_gives_no_warning(tmp_path):
    repo = _repo(tmp_path)
    head = _commit(repo, "a")
    assert session_start.snapshot_staleness(_ctx(head), repo) is None


def test_lagging_sha_is_recheck_required_not_false(tmp_path):
    repo = _repo(tmp_path)
    old = _commit(repo, "a")
    _commit(repo, "b")
    _commit(repo, "c")
    note = session_start.snapshot_staleness(_ctx(old), repo)
    assert note is not None
    assert "RECHECK_REQUIRED" in note
    assert "2 commit(s) ahead" in note
    assert "false" not in note.lower().replace("not necessarily wrong", "")


def test_unknown_sha_is_not_checkable_not_pass(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, "a")
    note = session_start.snapshot_staleness(_ctx("deadbee"), repo)
    assert note is not None and "NOT_CHECKABLE" in note


def test_no_recorded_sha_is_silent(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, "a")
    assert session_start.snapshot_staleness("# no branch row here\n", repo) is None


def test_not_a_git_repo_is_silent_or_not_checkable(tmp_path):
    # WHY: must never raise inside a SessionStart hook
    note = session_start.snapshot_staleness(_ctx("abc1234"), tmp_path)
    assert note is None or "NOT_CHECKABLE" in note
