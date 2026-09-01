"""Tests for live_drift_guard.py -- SessionStart hook warning when the
installed ~/.claude/hooks copy has diverged from this repo's own hooks/.

WHY: this hook exists because a real merged fix (PR #296, the circuit-
breaker lock race) sat undeployed on the live install with nothing to
catch it. It must fire only inside this repo's own checkout, only warn
(never block), and never crash session start on any I/O error.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
)

import live_drift_guard as ldg  # noqa: E402

# ── is_this_repo ─────────────────────────────────────────────────────────────


class TestIsThisRepo:
    def test_true_when_both_registries_present(self, tmp_path):
        (tmp_path / "hooks").mkdir()
        (tmp_path / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        (tmp_path / "skills").mkdir()
        (tmp_path / "skills" / "registry.yaml").write_text("x", encoding="utf-8")
        assert ldg.is_this_repo(tmp_path) is True

    def test_false_when_only_one_registry_present(self, tmp_path):
        (tmp_path / "hooks").mkdir()
        (tmp_path / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        assert ldg.is_this_repo(tmp_path) is False

    def test_false_for_unrelated_directory(self, tmp_path):
        assert ldg.is_this_repo(tmp_path) is False


# ── find_drift ───────────────────────────────────────────────────────────────


class TestFindDrift:
    def test_no_drift_when_content_matches(self, tmp_path):
        repo = tmp_path / "repo_hooks"
        live = tmp_path / "live_hooks"
        repo.mkdir()
        live.mkdir()
        (repo / "a.py").write_text("same", encoding="utf-8")
        (live / "a.py").write_text("same", encoding="utf-8")
        assert ldg.find_drift(repo, live) == []

    def test_reports_drift_when_content_differs(self, tmp_path):
        repo = tmp_path / "repo_hooks"
        live = tmp_path / "live_hooks"
        repo.mkdir()
        live.mkdir()
        (repo / "a.py").write_text("new version", encoding="utf-8")
        (live / "a.py").write_text("old version", encoding="utf-8")
        assert ldg.find_drift(repo, live) == ["a.py"]

    def test_ignores_file_missing_from_live(self, tmp_path):
        """Not yet deployed is a different fact than drifted -- must not conflate."""
        repo = tmp_path / "repo_hooks"
        live = tmp_path / "live_hooks"
        repo.mkdir()
        live.mkdir()
        (repo / "brand_new_hook.py").write_text("content", encoding="utf-8")
        assert ldg.find_drift(repo, live) == []

    def test_ignores_file_only_in_live(self, tmp_path):
        """A personal-only hook that isn't in the repo at all is not drift."""
        repo = tmp_path / "repo_hooks"
        live = tmp_path / "live_hooks"
        repo.mkdir()
        live.mkdir()
        (live / "personal_hook.py").write_text("content", encoding="utf-8")
        assert ldg.find_drift(repo, live) == []

    def test_ignores_pycache(self, tmp_path):
        repo = tmp_path / "repo_hooks"
        live = tmp_path / "live_hooks"
        (repo / "__pycache__").mkdir(parents=True)
        (live / "__pycache__").mkdir(parents=True)
        (repo / "__pycache__" / "a.cpython-311.pyc.py").write_text("x", encoding="utf-8")
        (live / "__pycache__" / "a.cpython-311.pyc.py").write_text("y", encoding="utf-8")
        assert ldg.find_drift(repo, live) == []

    def test_finds_drift_in_nested_lib_directory(self, tmp_path):
        repo = tmp_path / "repo_hooks"
        live = tmp_path / "live_hooks"
        (repo / "lib").mkdir(parents=True)
        (live / "lib").mkdir(parents=True)
        (repo / "lib" / "state.py").write_text("new", encoding="utf-8")
        (live / "lib" / "state.py").write_text("old", encoding="utf-8")
        assert ldg.find_drift(repo, live) == [os.path.join("lib", "state.py")]


# ── main (end-to-end, via monkeypatch) ───────────────────────────────────────


class TestMain:
    def test_silent_outside_this_repo(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        ldg.main()
        assert capsys.readouterr().out == ""

    def test_silent_when_claude_home_missing(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "hooks").mkdir()
        (tmp_path / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        (tmp_path / "skills").mkdir()
        (tmp_path / "skills" / "registry.yaml").write_text("x", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "does_not_exist"))
        ldg.main()
        assert capsys.readouterr().out == ""

    def test_warns_on_real_drift(self, tmp_path, monkeypatch, capsys):
        repo_root = tmp_path / "repo"
        (repo_root / "hooks").mkdir(parents=True)
        (repo_root / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "skills").mkdir()
        (repo_root / "skills" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "hooks" / "some_hook.py").write_text("new", encoding="utf-8")

        claude_home = tmp_path / "claude_home"
        (claude_home / "hooks").mkdir(parents=True)
        (claude_home / "hooks" / "some_hook.py").write_text("old", encoding="utf-8")

        monkeypatch.chdir(repo_root)
        monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
        ldg.main()
        out = capsys.readouterr().out
        assert "live-drift-guard" in out
        assert "some_hook.py" in out

    def test_silent_when_live_hooks_is_same_path_as_repo_hooks(self, tmp_path, monkeypatch, capsys):
        """A --link install (or --target pointing at the repo itself) can't drift."""
        repo_root = tmp_path / "repo"
        (repo_root / "hooks").mkdir(parents=True)
        (repo_root / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "skills").mkdir()
        (repo_root / "skills" / "registry.yaml").write_text("x", encoding="utf-8")

        monkeypatch.chdir(repo_root)
        monkeypatch.setenv("CLAUDE_HOME", str(repo_root))
        ldg.main()
        assert capsys.readouterr().out == ""

    def test_never_raises_on_unreadable_file(self, tmp_path, monkeypatch, capsys):
        repo_root = tmp_path / "repo"
        (repo_root / "hooks").mkdir(parents=True)
        (repo_root / "hooks" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "skills").mkdir()
        (repo_root / "skills" / "registry.yaml").write_text("x", encoding="utf-8")
        (repo_root / "hooks" / "some_hook.py").write_text("content", encoding="utf-8")

        claude_home = tmp_path / "claude_home"
        (claude_home / "hooks").mkdir(parents=True)
        (claude_home / "hooks" / "some_hook.py").write_text("content", encoding="utf-8")

        monkeypatch.chdir(repo_root)
        monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
        # Must not raise even if main()'s internals hit an unexpected error.
        ldg.main()
        assert "Traceback" not in capsys.readouterr().err
