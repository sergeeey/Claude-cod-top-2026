"""research_health_loop reports experiments whose decision.md was never committed to any branch.

WHY (reproducer): a finished experiment (decision.md, verdict REPEAT) lived only as untracked
files in a git worktree. A fresh agent asked to plan the same study did not find it and proposed
redoing ~10 000 labelled prompts from scratch; `git worktree remove` or a cleanup would delete it.
Nothing in the existing weekly audit looked at whether experiments are captured in git at all.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

import research_health_loop as rhl  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def _experiment(base: Path, name: str, verdict: str = "REPEAT") -> Path:
    exp = base / "experiments" / name
    exp.mkdir(parents=True)
    (exp / "decision.md").write_text(f"# decision\n- [x] {verdict}\n", encoding="utf-8")
    return exp


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "CLAUDE.md").write_text("x", encoding="utf-8")
    _git(repo, "add", "CLAUDE.md")
    _git(repo, "commit", "-qm", "init")
    return repo


def test_committed_experiment_is_not_reported(tmp_path):
    repo = _repo(tmp_path)
    _experiment(repo, "20260101-done", "PROMOTE")
    _git(repo, "add", "experiments")
    _git(repo, "commit", "-qm", "exp")
    assert rhl._find_uncaptured(repo) == []


def test_untracked_experiment_in_main_checkout_is_reported(tmp_path):
    repo = _repo(tmp_path)
    _experiment(repo, "20260102-local")
    found = rhl._find_uncaptured(repo)
    assert [f.split(" ")[0] for f in found] == ["20260102-local"]


def test_untracked_experiment_in_a_worktree_is_reported(tmp_path):
    repo = _repo(tmp_path)
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "side", str(wt))
    _experiment(wt, "20260103-only-in-worktree")
    found = rhl._find_uncaptured(repo)
    assert len(found) == 1
    assert found[0].startswith("20260103-only-in-worktree")
    assert "wt" in found[0]  # says WHERE it lives, so the owner can find it


def test_experiment_committed_on_another_branch_is_not_reported(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-qb", "side")
    _experiment(repo, "20260104-on-side", "REJECT")
    _git(repo, "add", "experiments")
    _git(repo, "commit", "-qm", "exp")
    _git(repo, "checkout", "-q", "main")
    # an untracked copy of the same folder in main must not count: it is captured on `side`
    _experiment(repo, "20260104-on-side", "REJECT")
    assert rhl._find_uncaptured(repo) == []


def test_folder_without_decision_is_not_reported(tmp_path):
    repo = _repo(tmp_path)
    (repo / "experiments" / "20260105-draft").mkdir(parents=True)
    assert rhl._find_uncaptured(repo) == []


def test_not_a_git_repo_is_silent(tmp_path):
    _experiment(tmp_path, "20260106-nogit")
    assert rhl._find_uncaptured(tmp_path) == []


def test_message_lists_uncaptured_experiments():
    msg = rhl._format_message([], [], [], "p", uncaptured=["20260103-x (worktree: wt)"])
    assert msg is not None
    assert "20260103-x" in msg
    assert "not committed" in msg


def test_committed_protocol_does_not_hide_an_uncommitted_decision(tmp_path):
    # Codex P2 reproducer: a protocol committed earlier in the same folder made the
    # whole directory look captured while decision.md had no git history at all.
    repo = _repo(tmp_path)
    exp = repo / "experiments" / "20260201-plan-first"
    exp.mkdir(parents=True)
    (exp / "protocol.md").write_text("plan", encoding="utf-8")
    _git(repo, "add", "experiments")
    _git(repo, "commit", "-qm", "protocol only")
    (exp / "decision.md").write_text("# decision\n- [x] REJECT\n", encoding="utf-8")
    found = rhl._find_uncaptured(repo)
    assert [f.split(" ")[0] for f in found] == ["20260201-plan-first"]
