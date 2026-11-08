"""End-to-end: experiment_insight -> raw note -> raw_to_wiki -> knowledge_librarian.

WHY (2026-11-08 project-interaction audit): the chain lost provenance at every hop. The raw note
had no project, raw_to_wiki buried its YAML in the body (and used it as the TL;DR), and the
librarian served an old note and the note that refuted it with equal weight and no date or
status. These tests run the REAL modules over a temp wiki: nothing is mocked except paths.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

REJECT = """\
# Decision

**Experiment ID:** `20261108-lamarckian-policy`
**Date:** 2026-11-08

## Verdict

- [x] REJECT — policy gain vanished on held-out split

## Reasoning

Gain of 0.12 on the training split fell to 0.00 on held-out data. Leakage via shared seed.
"""
REPEAT = REJECT.replace(
    "[x] REJECT — policy gain vanished on held-out split", "[x] REPEAT — rerun with disjoint seeds"
)


def _project(tmp_path: Path) -> Path:
    dec = tmp_path / "proj" / "experiments" / "20261108-lamarckian-policy" / "decision.md"
    dec.parent.mkdir(parents=True)
    (tmp_path / "proj" / ".git").mkdir()
    return dec


@pytest.fixture
def chain(monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
    monkeypatch.setenv("CLAUDE_DRY_RUN", "0")
    import experiment_insight
    import knowledge_librarian
    import raw_to_wiki

    importlib.reload(experiment_insight)
    importlib.reload(raw_to_wiki)
    raw, wiki = tmp_path / "raw", tmp_path / "wiki"
    experiment_insight.RAW_DIR = raw
    experiment_insight.DRY_RUN = False
    raw_to_wiki.DRY_RUN = False
    monkeypatch.setattr(raw_to_wiki.cogniml_client, "push_wiki_entry", lambda *a, **k: None)
    monkeypatch.setattr(knowledge_librarian, "WIKI_DIR", wiki)
    return experiment_insight, raw_to_wiki, knowledge_librarian, raw, wiki


def _capture(ei, text: str, dec: Path):
    return ei._create_raw_insight(ei._parse_decision(text), ei._project_of(str(dec)), "src")


def _wiki_entries(wiki: Path) -> dict[str, Path]:
    return {p.name: p for p in wiki.rglob("*.md") if "insight" in p.name}


class TestRawToWikiKeepsProvenance:
    def test_header_carries_project_outcome_evidence_status(self, chain, tmp_path):
        ei, r2w, _lib, raw, wiki = chain
        _capture(ei, REJECT, _project(tmp_path))
        assert r2w.process_raw_to_wiki(raw, wiki) == 1
        text = next(iter(_wiki_entries(wiki).values())).read_text(encoding="utf-8")
        for needle in (
            "**Project:** proj",
            "**Experiment:** 20261108-lamarckian-policy",
            "**Decision-Date:** 2026-11-08",
            "**Outcome:** NEGATIVE",
            "**Evidence:** UNKNOWN",
            "**Status:** auto-captured-not-verified",
        ):
            assert needle in text, needle
        assert "capture_key:" not in text and not text.startswith("---"), "YAML must not leak"
        tldr = text.split("## TL;DR", 1)[1].split("---", 1)[0]
        assert "title:" not in tldr and "project_path" not in tldr

    def test_plain_notes_without_frontmatter_are_unchanged(self, chain):
        _ei, r2w, _lib, raw, wiki = chain
        raw.mkdir()
        (raw / "plain.md").write_text("# Plain\n\n#raw #x\n\nBody text here.\n", encoding="utf-8")
        r2w.process_raw_to_wiki(raw, wiki)
        text = next(wiki.rglob("*plain.md")).read_text(encoding="utf-8")
        assert "**Project:**" not in text and "Body text here." in text


class TestLibrarianLabelsAndSupersession:
    def _two_captures(self, ei, r2w, raw, wiki, tmp_path):
        dec = _project(tmp_path)
        old = _capture(ei, REJECT, dec)
        new = _capture(ei, REPEAT, dec)
        assert old and new and old != new
        r2w.process_raw_to_wiki(raw, wiki)
        return _wiki_entries(wiki)

    def test_old_entry_is_labelled_superseded_new_one_is_not(self, chain, tmp_path):
        ei, r2w, lib, raw, wiki = chain
        entries = self._two_captures(ei, r2w, raw, wiki, tmp_path)
        by_verdict = {("REJECT" if "REJECT" in n else "REPEAT"): p for n, p in entries.items()}
        for verdict, expect in (("REJECT", True), ("REPEAT", False)):
            p = by_verdict[verdict]
            rel = p.relative_to(wiki).as_posix()
            badge, superseded = lib._entry_badge(rel, p.read_text(encoding="utf-8"))
            assert superseded is expect, (verdict, badge)
            assert "2026-11-08" in badge and "proj" in badge and "evidence UNKNOWN" in badge
            assert "не проверено" in badge
            assert ("ЗАМЕНЕНО" in badge) is expect
        # history is preserved: both entries still exist and the old one is unchanged
        assert len(entries) == 2
        assert "Supersedes" not in by_verdict["REJECT"].read_text(encoding="utf-8")

    def test_superseded_entry_is_never_inlined_as_hot(self, chain, tmp_path):
        from lib.wiki_types import SearchHit, WikiRef

        ei, r2w, lib, raw, wiki = chain
        entries = self._two_captures(ei, r2w, raw, wiki, tmp_path)
        hits = [
            SearchHit(WikiRef(p.relative_to(wiki).as_posix(), f"T-{i}"), 1.0, "keyword")
            for i, p in enumerate(entries.values())
        ]
        hot, warm = lib._classify_and_render_wiki(hits, ["lamarckian", "policy", "gain"])
        old_title = next(f"T-{i}" for i, p in enumerate(entries.values()) if "REJECT" in p.name)
        assert not any(old_title in line for line in hot), "outdated claim must not be inlined"
        assert any(old_title in line and "ЗАМЕНЕНО" in line for line in warm)

    def test_ordinary_entries_get_a_date_badge_only(self, chain):
        _ei, _r2w, lib, _raw, wiki = chain
        wiki.mkdir(parents=True)
        (wiki / "n.md").write_text(
            "# N\n\n**Date:** 2026-05-01  \n**Tags:** a\n\nbody", encoding="utf-8"
        )
        badge, superseded = lib._entry_badge("n.md", (wiki / "n.md").read_text(encoding="utf-8"))
        assert badge == "2026-05-01" and superseded is False


class TestIdentityFallback:
    def test_identity_focus_uses_project_name_and_claude_md(self, chain, monkeypatch, tmp_path):
        _ei, _r2w, lib, _raw, _wiki = chain
        proj = tmp_path / "geo-miro-2026"
        (proj / ".git").mkdir(parents=True)
        (proj / "sub").mkdir()
        (proj / "CLAUDE.md").write_text(
            "---\nx: y\n---\n# Geo\nScenario planning.", encoding="utf-8"
        )
        monkeypatch.chdir(proj / "sub")
        focus = lib._project_identity_focus()
        assert "geo miro 2026" in focus and "Scenario planning" in focus and "x: y" not in focus

    def test_identity_focus_survives_project_without_any_files(self, chain, monkeypatch, tmp_path):
        _ei, _r2w, lib, _raw, _wiki = chain
        bare = tmp_path / "bare-local-project"
        bare.mkdir()
        monkeypatch.chdir(bare)
        assert lib._project_identity_focus() == "bare local project"


class TestInheritedVaultContextAndNameOnly:
    def test_vault_activecontext_is_not_a_projects_focus(self, chain, monkeypatch, tmp_path):
        """A project under ~ without its own memory must not be queried by the Vault's focus."""
        _ei, _r2w, lib, _raw, _wiki = chain
        fake_home = tmp_path / "home"
        (fake_home / ".claude" / "memory").mkdir(parents=True)
        ctx = fake_home / ".claude" / "memory" / "activeContext.md"
        ctx.write_text("## Current Focus\nVault maintenance\n", encoding="utf-8")
        proj = fake_home / "work" / "delta"
        proj.mkdir(parents=True)
        for var in ("USERPROFILE", "HOME"):
            monkeypatch.setenv(var, str(fake_home))
        monkeypatch.chdir(proj)
        assert lib._is_inherited_vault_context(ctx) is True
        monkeypatch.chdir(fake_home / ".claude" / "memory")
        assert lib._is_inherited_vault_context(ctx) is False  # a session inside the Vault keeps it

    def test_name_only_identity_is_silent_and_does_not_query_the_wiki(
        self, chain, monkeypatch, tmp_path
    ):
        import io
        from unittest.mock import patch

        _ei, _r2w, lib, _raw, _wiki = chain
        bare = tmp_path / "Gamma-bare"
        bare.mkdir()
        monkeypatch.chdir(bare)
        monkeypatch.setattr(lib, "find_project_memory", lambda: None)
        monkeypatch.setattr(
            lib, "_query_wiki_raw_titles", lambda *a, **k: pytest.fail("wiki must not be queried")
        )
        monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            try:
                lib.main()
            except SystemExit:
                pass
        assert buf.getvalue() == "", "a bare folder name is not a query: silence, not noise"


class TestPostCommitLocking:
    """post_commit_memory serialises its read-modify-write with the repo's lib.state.file_lock."""

    def test_locked_raises_instead_of_proceeding_unlocked(self, tmp_path, monkeypatch):
        import post_commit_memory as pcm

        monkeypatch.setattr(pcm, "file_lock", _never_acquired)
        with pytest.raises(TimeoutError):
            with pcm._locked(tmp_path / "decisions.md"):
                pytest.fail("body must not run without the lock")

    def test_locked_releases_the_lock_file(self, tmp_path):
        import post_commit_memory as pcm

        target = tmp_path / "decisions.md"
        with pcm._locked(target):
            assert Path(f"{target}.lock").exists()
        assert not Path(f"{target}.lock").exists()


import contextlib  # noqa: E402


@contextlib.contextmanager
def _never_acquired(*_a, **_k):
    yield False


def test_parallel_decision_appends_are_not_lost(tmp_path):
    """Regression for the 2026-11-08 finding: 8 parallel log_decision() calls kept 1 entry.

    Real function, real processes, wall-clock barrier, serial control checked first.
    """
    import os
    import subprocess
    import time

    n = 8
    hooks = str(Path(__file__).parent.parent / "hooks")
    proj = tmp_path / "proj"
    (proj / ".claude" / "memory").mkdir(parents=True)
    df = proj / ".claude" / "memory" / "decisions.md"
    worker = (
        "import os,sys,time\n"
        "sys.path.insert(0, sys.argv[1]); t0=float(sys.argv[2]); h=sys.argv[3]\n"
        "os.environ.pop('CLAUDE_INVOKED_BY', None)\n"
        "import post_commit_memory as m\n"
        "while time.time() < t0: pass\n"
        "m.log_decision(h, 'arch: decision ' + h)\n"
    )
    env = {**os.environ, "USERPROFILE": str(tmp_path / "h"), "HOME": str(tmp_path / "h")}
    env.pop("CLAUDE_INVOKED_BY", None)

    def run(tag: str, parallel: bool) -> int:
        df.write_text("# Decisions\n", encoding="utf-8")
        t0 = time.time() + 2.0
        cmds = [
            [sys.executable, "-S", "-c", worker, hooks, str(t0 if parallel else 0), f"{tag}{i}"]
            for i in range(n)
        ]
        if parallel:
            for p in [subprocess.Popen(c, cwd=proj, env=env) for c in cmds]:
                p.wait()
        else:
            for c in cmds:
                subprocess.run(c, cwd=proj, env=env, check=False)
        text = df.read_text(encoding="utf-8")
        return sum(1 for i in range(n) if f"`{tag}{i}`" in text)

    assert run("s", parallel=False) == n, "serial control failed: the test itself is invalid"
    assert run("p", parallel=True) == n, "lost update under concurrency"


class TestIdempotencyAcrossConversion:
    def test_repeated_edit_after_conversion_creates_no_second_note(self, chain, tmp_path):
        ei, r2w, _lib, raw, wiki = chain
        dec = _project(tmp_path)
        assert _capture(ei, REJECT, dec) is not None
        assert r2w.process_raw_to_wiki(raw, wiki) == 1
        assert _capture(ei, REJECT, dec) is None, "already captured (now in raw/processed/)"
        assert not list(raw.glob("*.md")), "nothing may be left behind in raw/"
        assert r2w.process_raw_to_wiki(raw, wiki) == 0
        assert len(_wiki_entries(wiki)) == 1

    def test_changed_verdict_after_conversion_supersedes_the_converted_note(self, chain, tmp_path):
        ei, r2w, _lib, raw, wiki = chain
        dec = _project(tmp_path)
        first = _capture(ei, REJECT, dec)
        r2w.process_raw_to_wiki(raw, wiki)
        second = _capture(ei, REPEAT, dec)
        assert second is not None
        assert f"supersedes: [{first.name}]" in second.read_text(encoding="utf-8")
