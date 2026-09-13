"""Tests for scripts/redeploy_drift.py -- direction-aware redeploy of live drift.

Each test builds a real throwaway git repository with real history, because the
property under test IS git history: a live file is STALE only if it equals an
older version of the same path on origin/main, in the right order. Mocking git
would test the mock.

The failures pinned here, in order of cost -- several were found by independent
review of the first draft (skeptic + sec-auditor, 2026-09-13) and each has its
own regression test below:
  * a live file edited live (matching nothing main shipped) gets overwritten;
  * a feature branch that reverts a hardened hook makes the correctly-deployed
    live copy look "older", and the weaker version is written live;
  * a feature branch with unreviewed commits gets deployed;
  * main reverted to an earlier version while live kept the later one, and the
    later one is destroyed;
  * a symlinked live file is followed and something outside ~/.claude overwritten;
  * the live file changes between classification and write, and the change is lost;
  * a glob-shaped path name borrows another file's history.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hooks"))

import redeploy_drift as rd  # noqa: E402

if shutil.which("git") is None:  # pragma: no cover
    pytest.skip("git not available", allow_module_level=True)


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "-c",
            "core.autocrlf=false",
            *args,
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def commit(repo: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        write(repo / rel, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


def set_main_here(repo: Path) -> None:
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")


@pytest.fixture()
def world(tmp_path):
    """repo with two commits per artifact, origin/main == HEAD, empty live install."""
    repo = tmp_path / "repo"
    live = tmp_path / "live"
    repo.mkdir()
    live.mkdir()
    git(repo, "init", "-q")
    commit(
        repo,
        {
            "hooks/registry.yaml": "x\n",
            "skills/registry.yaml": "x\n",
            "hooks/a.py": "v1\n",
            "rules/sub/r.md": "rule v1\n",
            "agents/ag.md": "agent v1\n",
            "commands/cm.md": "cmd v1\n",
            "skills/core/sk/SKILL.md": "skill v1\n",
        },
        "v1",
    )
    commit(
        repo,
        {
            "hooks/a.py": "v2\n",
            "rules/sub/r.md": "rule v2\n",
            "agents/ag.md": "agent v2\n",
            "commands/cm.md": "cmd v2\n",
            "skills/core/sk/SKILL.md": "skill v2\n",
        },
        "v2",
    )
    set_main_here(repo)
    return repo, live


def classify(repo: Path, live: Path, rel: str) -> rd.Item:
    main_sha = rd.resolve_main(repo)
    assert main_sha
    return rd.classify(repo, rel, live / rel, main_sha, live)


def statuses(repo: Path, live: Path) -> dict[str, str]:
    pairs, _ = rd.candidates(repo, live)
    main_sha = rd.resolve_main(repo)
    assert main_sha
    return {rel: rd.classify(repo, rel, p, main_sha, live).status for rel, p in pairs}


def backups(live: Path) -> list[Path]:
    return [p for p in live.rglob("*") if ".bak-redeploy-" in p.name]


# ── classification ────────────────────────────────────────────────────────────


class TestClassify:
    def test_older_version_is_stale(self, world):
        repo, live = world
        write(live / "hooks/a.py", "v1\n")
        assert statuses(repo, live) == {"hooks/a.py": rd.STALE}

    def test_live_edit_matching_no_shipped_version_is_unproven(self, world):
        repo, live = world
        write(live / "hooks/a.py", "v2 plus a live-only fix\n")
        assert statuses(repo, live) == {"hooks/a.py": rd.UNPROVEN}

    def test_crlf_copy_of_older_version_is_still_stale(self, world):
        """Without LF-normalisation every CRLF live copy matches no blob and the
        tool refuses to fix the very files it exists for."""
        repo, live = world
        write(live / "hooks/a.py", "v1\r\n")
        assert statuses(repo, live) == {"hooks/a.py": rd.STALE}

    def test_crlf_only_difference_from_main_is_current(self, world):
        repo, live = world
        write(live / "hooks/a.py", "v2\r\n")
        assert statuses(repo, live) == {"hooks/a.py": rd.CURRENT}

    def test_all_single_file_layers_are_candidates(self, world):
        repo, live = world
        write(live / "rules/sub/r.md", "rule v1\n")
        write(live / "agents/ag.md", "agent v1\n")
        write(live / "commands/cm.md", "cmd v1\n")
        assert statuses(repo, live) == {
            "rules/sub/r.md": rd.STALE,
            "agents/ag.md": rd.STALE,
            "commands/cm.md": rd.STALE,
        }

    def test_skills_are_counted_but_never_candidates(self, world):
        repo, live = world
        write(live / "skills/sk/SKILL.md", "skill v1\n")
        pairs, skipped = rd.candidates(repo, live)
        assert pairs == []
        assert skipped == 1

    def test_any_older_version_in_a_forward_history_is_stale(self, world):
        """Control for the ordering rule: v1 -> v2 -> v3 with live at v2 IS stale."""
        repo, live = world
        commit(repo, {"hooks/a.py": "v3\n"}, "v3")
        set_main_here(repo)
        write(live / "hooks/a.py", "v2\n")
        assert classify(repo, live, "hooks/a.py").status == rd.STALE

    def test_revert_on_main_does_not_make_the_later_live_version_stale(self, world):
        """skeptic F2. main went v1 -> v2 -> v1 (a revert); live kept v2. v2 IS an
        older blob, but main moved BACK past it -- overwriting would destroy a
        deliberate choice."""
        repo, live = world
        commit(repo, {"hooks/a.py": "v1\n"}, "revert to v1")
        set_main_here(repo)
        write(live / "hooks/a.py", "v2\n")
        item = classify(repo, live, "hooks/a.py")
        assert item.status == rd.UNPROVEN
        assert "revert" in item.detail

    def test_content_only_on_a_feature_branch_is_unproven(self, world):
        """The reference is origin/main: a blob that exists only on some branch was
        never shipped, so matching it proves nothing."""
        repo, live = world
        git(repo, "switch", "-q", "-c", "feature")
        commit(repo, {"hooks/a.py": "branch only\n"}, "wip")
        commit(repo, {"hooks/a.py": "branch later\n"}, "wip2")
        write(live / "hooks/a.py", "branch only\n")
        assert classify(repo, live, "hooks/a.py").status == rd.UNPROVEN

    def test_branch_reverting_a_hook_does_not_mark_the_main_copy_stale(self, world):
        """sec-auditor H1 / skeptic F1, the downgrade: live holds main's hardened v2;
        a feature branch puts the weak v1 back. Against HEAD, v2 looks 'older'.
        Against origin/main, live is simply current."""
        repo, live = world
        git(repo, "switch", "-q", "-c", "feature")
        commit(repo, {"hooks/a.py": "v1\n"}, "put the weak version back")
        write(live / "hooks/a.py", "v2\n")
        item = classify(repo, live, "hooks/a.py")
        assert item.status == rd.CURRENT
        assert rd.run(repo, live, apply=True) == 0
        assert (live / "hooks/a.py").read_bytes() == b"v2\n"

    def test_merge_commit_delivery_is_tracked_but_pr_intermediates_are_not(self, world):
        """Found measuring the real machine: 4 agents flipped STALE -> UNPROVEN after
        the switch to main's first-parent history. Exhaustive walk confirmed their
        live content existed only inside a merged PR branch, never on main -- so
        UNPROVEN is right. This pins both halves: what a merge DELIVERED to main is
        history; what a PR branch passed through on the way is not."""
        repo, live = world
        git(repo, "switch", "-q", "-c", "pr")
        commit(repo, {"hooks/a.py": "b1\n"}, "b1")
        commit(repo, {"hooks/a.py": "b2\n"}, "b2")
        git(repo, "switch", "-q", "-")
        git(repo, "merge", "-q", "--no-ff", "pr", "-m", "merge pr")
        set_main_here(repo)
        write(live / "hooks/a.py", "v2\n")
        assert classify(repo, live, "hooks/a.py").status == rd.STALE
        write(live / "hooks/a.py", "b1\n")
        assert classify(repo, live, "hooks/a.py").status == rd.UNPROVEN
        write(live / "hooks/a.py", "b2\n")
        assert classify(repo, live, "hooks/a.py").status == rd.CURRENT

    def test_revert_is_detected_even_when_main_once_stored_the_text_with_crlf(self, world):
        """sec-auditor round 2, M-1 (reproduced): the current text first appeared as a
        CRLF blob, so a blob-id comparison missed it, the revert looked like a first
        appearance, and a live HARDENED version came out STALE."""
        repo, live = world
        commit(repo, {"hooks/g.py": "weak=1\r\n"}, "weak, stored with CRLF")
        commit(repo, {"hooks/g.py": "hardened=1\n"}, "hardened")
        commit(repo, {"hooks/g.py": "weak=1\n"}, "revert to weak, LF")
        set_main_here(repo)
        write(live / "hooks/g.py", "hardened=1\n")
        assert classify(repo, live, "hooks/g.py").status == rd.UNPROVEN

    def test_linked_live_install_root_is_refused(self, world, monkeypatch):
        """sec-auditor round 2, M-2 (reproduced with a real `mklink /J`): resolve()
        follows a linked ~/.claude, so every containment check passed while writes
        landed in the link's target. Simulated here so it runs on every platform."""
        repo, live = world
        write(live / "hooks/a.py", "v1\n")
        real_is_link = rd._is_link
        monkeypatch.setattr(rd, "_is_link", lambda p: p == live or real_is_link(p))
        item = classify(repo, live, "hooks/a.py")
        assert item.status == rd.UNPROVEN
        assert "root itself is a link" in item.detail

    def test_glob_shaped_path_does_not_borrow_another_files_history(self, world):
        """sec-auditor L1: without literal pathspecs `hooks/[ab].py` matches
        hooks/a.py's history, so live content equal to a.py's v1 looked STALE."""
        repo, live = world
        commit(repo, {"hooks/[ab].py": "glob file\n"}, "add glob-named file")
        set_main_here(repo)
        write(live / "hooks/[ab].py", "v1\n")
        assert classify(repo, live, "hooks/[ab].py").status == rd.UNPROVEN

    def test_symlinked_live_file_is_refused_and_nothing_written(self, world, monkeypatch):
        """sec-auditor H2: install.sh --link makes exactly these links, and a naive
        write follows them out of ~/.claude (reproduced against the first draft).

        Simulated with a patched is_symlink rather than a real link: creating
        symlinks needs privileges on Windows, and a test that cannot run there
        proves nothing there -- this one runs everywhere."""
        repo, live = world
        write(live / "hooks/a.py", "v1\n")
        linked = (live / "hooks" / "a.py").resolve()
        real_is_symlink = Path.is_symlink

        def fake_is_symlink(self):
            return True if self.resolve() == linked else real_is_symlink(self)

        monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)
        item = classify(repo, live, "hooks/a.py")
        assert item.status == rd.UNPROVEN
        assert "symlink" in item.detail
        assert rd.run(repo, live, apply=True) == 0
        assert (live / "hooks/a.py").read_bytes() == b"v1\n"
        assert backups(live) == []


# ── run(): preview vs apply ───────────────────────────────────────────────────


class TestRun:
    def test_preview_writes_nothing(self, world):
        repo, live = world
        write(live / "hooks/a.py", "v1\n")
        assert rd.run(repo, live, apply=False) == 0
        assert (live / "hooks/a.py").read_bytes() == b"v1\n"
        assert backups(live) == []

    def test_apply_overwrites_stale_from_main_with_backup(self, world):
        repo, live = world
        write(live / "hooks/a.py", "v1\n")
        assert rd.run(repo, live, apply=True) == 0
        assert (live / "hooks/a.py").read_bytes() == b"v2\n"
        [bak] = backups(live)
        assert bak.read_bytes() == b"v1\n", "the backup must hold what was overwritten"

    def test_apply_never_writes_unproven(self, world):
        """THE reason this script exists: a live-only edit must survive --apply."""
        repo, live = world
        write(live / "hooks/a.py", "v2 plus a live-only fix\n")
        write(live / "agents/ag.md", "agent v1\n")  # a STALE sibling, so apply does run
        assert rd.run(repo, live, apply=True) == 0
        assert (live / "hooks/a.py").read_bytes() == b"v2 plus a live-only fix\n"
        assert (live / "agents/ag.md").read_bytes() == b"agent v2\n"
        assert [b.name.split(".bak-redeploy-")[0] for b in backups(live)] == ["ag.md"], (
            "no backup may be created for a file that was not written"
        )

    def test_apply_deploys_main_blob_not_uncommitted_working_tree(self, world):
        repo, live = world
        write(live / "hooks/a.py", "v1\n")
        write(repo / "hooks/a.py", "v3 uncommitted\n")
        assert rd.run(repo, live, apply=True) == 0
        assert (live / "hooks/a.py").read_bytes() == b"v2\n"

    def test_apply_refused_when_head_is_behind_origin_main(self, world):
        repo, live = world
        git(repo, "switch", "-q", "-c", "ahead")
        commit(repo, {"hooks/a.py": "v3\n"}, "v3")
        set_main_here(repo)
        git(repo, "switch", "-q", "-")  # back to the older branch
        write(live / "hooks/a.py", "v1\n")
        assert rd.run(repo, live, apply=True) == 1
        assert (live / "hooks/a.py").read_bytes() == b"v1\n"
        assert backups(live) == []

    def test_apply_refused_when_head_is_ahead_of_origin_main(self, world):
        """skeptic F1: the first draft's guard ("HEAD contains origin/main") passed on
        every feature branch. Here a WIP commit sits on top of main."""
        repo, live = world
        git(repo, "switch", "-q", "-c", "feature")
        commit(repo, {"hooks/a.py": "unreviewed WIP\n"}, "wip")
        write(live / "hooks/a.py", "v1\n")
        assert rd.run(repo, live, apply=True) == 1
        assert (live / "hooks/a.py").read_bytes() == b"v1\n"
        assert backups(live) == []

    def test_apply_refused_without_origin_main_ref(self, world):
        repo, live = world
        git(repo, "update-ref", "-d", "refs/remotes/origin/main")
        write(live / "hooks/a.py", "v1\n")
        assert rd.run(repo, live, apply=True) == 1
        assert (live / "hooks/a.py").read_bytes() == b"v1\n"

    def test_current_is_not_rewritten(self, world):
        repo, live = world
        write(live / "hooks/a.py", "v2\r\n")
        assert rd.run(repo, live, apply=True) == 0
        assert (live / "hooks/a.py").read_bytes() == b"v2\r\n"
        assert backups(live) == []

    def test_skills_are_never_written(self, world):
        repo, live = world
        write(live / "skills/sk/SKILL.md", "skill v1\n")
        write(live / "hooks/a.py", "v1\n")
        assert rd.run(repo, live, apply=True) == 0
        assert (live / "skills/sk/SKILL.md").read_bytes() == b"skill v1\n"

    def test_live_change_between_classify_and_write_is_not_lost(self, world):
        """sec-auditor M2: whatever is in the live file at write time must be what
        was classified; otherwise an edit made in between is silently replaced."""
        repo, live = world
        write(live / "hooks/a.py", "v1\n")
        item = classify(repo, live, "hooks/a.py")
        assert item.status == rd.STALE
        write(live / "hooks/a.py", "edited meanwhile\n")
        main_sha = rd.resolve_main(repo)
        assert main_sha
        err = rd.apply_item(repo, item, live / "hooks/a.py", main_sha, live, "t")
        assert err is not None and "changed since" in err
        assert (live / "hooks/a.py").read_bytes() == b"edited meanwhile\n"


class TestWriteFailures:
    """What is left behind when a write cannot complete. Live must be intact, and
    nothing may be left beside it -- a stray backup is an older copy of a guard
    sitting in the hooks directory (sec-auditor round 2, L-3, reproduced by holding
    the live file open on Windows)."""

    def _stale(self, world):
        repo, live = world
        write(live / "hooks/a.py", "v1\n")
        item = classify(repo, live, "hooks/a.py")
        assert item.status == rd.STALE
        main_sha = rd.resolve_main(repo)
        assert main_sha
        return repo, live, item, main_sha

    def test_failed_replace_leaves_live_intact_and_nothing_behind(self, world, monkeypatch):
        repo, live, item, main_sha = self._stale(world)

        def boom(src, dst):
            raise PermissionError("file in use")

        monkeypatch.setattr(rd.os, "replace", boom)
        err = rd.apply_item(repo, item, live / "hooks/a.py", main_sha, live, "S")
        assert err is not None and "left as it was" in err
        assert (live / "hooks/a.py").read_bytes() == b"v1\n"
        assert sorted(p.name for p in (live / "hooks").iterdir()) == ["a.py"]

    def test_existing_file_at_temp_name_is_not_followed(self, world):
        """sec-auditor round 2, L-2: the temp file is created exclusively, so whatever
        already sits at that name is never opened and truncated."""
        repo, live, item, main_sha = self._stale(world)
        squatter = live / "hooks" / ".a.py.redeploy-tmp-S"
        write(squatter, "do not touch\n")
        err = rd.apply_item(repo, item, live / "hooks/a.py", main_sha, live, "S")
        assert err is not None
        assert squatter.read_bytes() == b"do not touch\n"
        assert (live / "hooks/a.py").read_bytes() == b"v1\n"

    def test_unreadable_file_after_replace_is_reported_not_raised(self, world, monkeypatch):
        """sec-auditor round 2, L-1: an OSError on the verification read used to escape
        and abort the whole run, skipping every remaining file without a FAILED line."""
        repo, live, item, main_sha = self._stale(world)
        target = live / "hooks" / "a.py"
        real_read = Path.read_bytes
        calls = {"n": 0}

        def flaky_read(self):
            if self == target:
                calls["n"] += 1
                if calls["n"] == 2:  # 1st = pre-write re-check, 2nd = post-write verify
                    raise PermissionError("locked by antivirus")
            return real_read(self)

        monkeypatch.setattr(Path, "read_bytes", flaky_read)
        err = rd.apply_item(repo, item, target, main_sha, live, "S")
        assert err is not None and "post-write verification" in err


class TestMain:
    def test_no_live_install_exits_2(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "does-not-exist"))
        assert rd.main([]) == 2

    def test_preview_names_unproven_and_how_to_resolve_it(self, world, capsys):
        """An UNPROVEN file is only safe if the human SEES it -- silently skipping it
        would leave the live-only change unported forever, which is how
        iteration_guard's fix stayed out of the repo in the first place."""
        repo, live = world
        write(live / "hooks/a.py", "v2 plus a live-only fix\n")
        rd.run(repo, live, apply=False)
        out = capsys.readouterr().out
        assert "UNPROVEN (1):" in out and "hooks/a.py" in out
        assert "never written" in out and "port the live change" in out
