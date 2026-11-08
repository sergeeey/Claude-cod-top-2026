"""O37: raw -> processed move on Windows, repeat-Stop idempotency, failures, concurrency.

Measured on the real Vault (2026-11-08): 135 raw/session-*.md were stuck because processed/<name>
already existed; Path.rename() raises FileExistsError there ([WinError 183]), the old code swallowed
it AFTER rewriting the wiki entry, so every Stop re-converted them with a fresh Date. They are NOT
duplicates: each is a later batch of the same day (different events). All tests use synthetic data.
"""

from __future__ import annotations

import importlib
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

HOOKS = str(Path(__file__).parent.parent / "hooks")
sys.path.insert(0, HOOKS)


def _batch(day: str, n: int, events: int) -> str:
    body = "\n".join(
        f"- `{9 + n}:{i:02d}` Edit `C:\\proj\\f{n}_{i}.py` (+{i} chars)" for i in range(events)
    )
    return f"# Session Observations — {day}\n\n#raw #session-log #auto-capture\n\n**Date:** {day}  \n\n---\n\n{body}\n"


@pytest.fixture
def r2w(monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
    monkeypatch.setenv("CLAUDE_DRY_RUN", "0")
    import raw_to_wiki

    importlib.reload(raw_to_wiki)
    raw_to_wiki.DRY_RUN = False
    monkeypatch.setattr(raw_to_wiki.cogniml_client, "push_wiki_entry", lambda *a, **k: None)
    raw, wiki = tmp_path / "raw", tmp_path / "wiki"
    raw.mkdir()
    return raw_to_wiki, raw, wiki


def _snap(root: Path) -> dict:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not p.name.endswith(".lock")
    }


def _freeze(r2w, day: int):
    class FD(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, day, 12, 0, 0, tzinfo=tz)

    r2w.datetime = FD


def _wiki_date(wiki: Path, stem: str) -> str:
    f = next(wiki.rglob(f"*_{stem}.md"))
    return re.search(r"^\*\*Date:\*\*\s*(\S+)", f.read_text(encoding="utf-8"), re.M).group(1)


class TestCollisionSafeArchive:
    def test_same_name_different_content_gets_a_unique_name_and_nothing_is_overwritten(self, r2w):
        m, raw, wiki = r2w
        (raw / "s.md").write_text(_batch("2026-11-06", 1, 3), encoding="utf-8")
        assert m.process_raw_to_wiki(raw, wiki) == 1
        first = (raw / "processed" / "s.md").read_bytes()
        (raw / "s.md").write_text(_batch("2026-11-06", 2, 9), encoding="utf-8")
        second = (raw / "s.md").read_bytes()
        assert m.process_raw_to_wiki(raw, wiki) == 1
        assert not (raw / "s.md").exists(), "must not stay stuck in raw/"
        assert (raw / "processed" / "s.md").read_bytes() == first, "batch 1 must not be overwritten"
        archived = [p for p in (raw / "processed").glob("s.*.md")]
        assert len(archived) == 1 and archived[0].read_bytes() == second

    def test_byte_identical_copy_is_not_archived_twice_and_raw_copy_is_removed(self, r2w):
        m, raw, wiki = r2w
        text = _batch("2026-11-06", 1, 3)
        (raw / "s.md").write_text(text, encoding="utf-8")
        m.process_raw_to_wiki(raw, wiki)
        (raw / "s.md").write_bytes((raw / "processed" / "s.md").read_bytes())  # identical again
        before_wiki = _snap(wiki)
        assert m.process_raw_to_wiki(raw, wiki) == 1
        assert not (raw / "s.md").exists()
        assert len(list((raw / "processed").glob("s*.md"))) == 1
        assert _snap(wiki) == before_wiki, "the wiki entry is already current: untouched"

    def test_uniquely_named_archive_is_reused_not_duplicated(self, r2w):
        m, raw, wiki = r2w
        (raw / "s.md").write_text(_batch("d", 1, 3), encoding="utf-8")
        m.process_raw_to_wiki(raw, wiki)
        (raw / "s.md").write_text(_batch("d", 2, 9), encoding="utf-8")
        m.process_raw_to_wiki(raw, wiki)
        archived = next((raw / "processed").glob("s.*.md"))
        (raw / "s.md").write_bytes(archived.read_bytes())  # the same batch re-appears
        m.process_raw_to_wiki(raw, wiki)
        assert len(list((raw / "processed").glob("s*.md"))) == 2 and not (raw / "s.md").exists()


class TestRepeatStopIdempotency:
    def test_quiet_repeat_changes_nothing_and_keeps_the_date(self, r2w):
        m, raw, wiki = r2w
        _freeze(m, 6)
        (raw / "s.md").write_text(_batch("2026-11-06", 1, 3), encoding="utf-8")
        m.process_raw_to_wiki(raw, wiki)
        (raw / "s.md").write_text(_batch("2026-11-06", 2, 9), encoding="utf-8")
        _freeze(m, 7)
        m.process_raw_to_wiki(raw, wiki)
        assert _wiki_date(wiki, "s") == "2026-11-07"
        snap = _snap(raw.parent)
        for day in (8, 9):
            _freeze(m, day)
            assert m.process_raw_to_wiki(raw, wiki) == 0
            assert _snap(raw.parent) == snap, "a Stop without new events must change nothing"
        assert _wiki_date(wiki, "s") == "2026-11-07", "the date must not follow the Stop"

    def test_stuck_state_left_by_the_old_code_is_resolved_without_touching_the_wiki(self, r2w):
        """Exactly the production state: wiki entry == conversion of raw, processed/ has another batch."""
        m, raw, wiki = r2w
        _freeze(m, 7)
        (raw / "s.md").write_text(_batch("2026-11-06", 1, 3), encoding="utf-8")
        m.process_raw_to_wiki(raw, wiki)
        batch2 = _batch("2026-11-06", 2, 9)
        (raw / "s.md").write_text(batch2, encoding="utf-8")
        # reproduce the old code's end state: convert, then fail to move
        real_rename = Path.rename
        Path.rename = lambda self, tgt: (_ for _ in ()).throw(FileExistsError(183, "exists"))
        try:
            m.process_raw_to_wiki(raw, wiki)
        finally:
            Path.rename = real_rename
        assert (raw / "s.md").exists()
        wiki_before = _snap(wiki)
        _freeze(m, 20)  # a much later day
        assert m.process_raw_to_wiki(raw, wiki) == 1
        assert _snap(wiki) == wiki_before, "wiki bytes (incl. Date) unchanged"
        assert not (raw / "s.md").exists()

    def test_changed_content_does_update_the_entry_and_its_date(self, r2w):
        m, raw, wiki = r2w
        _freeze(m, 6)
        (raw / "a.md").write_text("# Note\n\n#raw\n\nfirst body\n", encoding="utf-8")
        m.process_raw_to_wiki(raw, wiki)
        _freeze(m, 9)
        (raw / "a.md").write_text("# Note\n\n#raw\n\nsecond body, different\n", encoding="utf-8")
        m.process_raw_to_wiki(raw, wiki)
        assert _wiki_date(wiki, "a") == "2026-11-09"
        assert "second body" in next(wiki.rglob("*_a.md")).read_text(encoding="utf-8")


class TestFailuresAndRetry:
    def test_failed_move_keeps_raw_and_the_retry_rewrites_nothing(self, r2w, monkeypatch):
        m, raw, wiki = r2w
        _freeze(m, 6)
        (raw / "s.md").write_text(_batch("d", 1, 3), encoding="utf-8")
        real = Path.rename
        monkeypatch.setattr(
            Path, "rename", lambda s, t: (_ for _ in ()).throw(PermissionError(13, "locked"))
        )
        assert m.process_raw_to_wiki(raw, wiki) == 0, (
            "the file was not archived: not counted as processed"
        )
        monkeypatch.setattr(Path, "rename", real)
        assert (raw / "s.md").exists()
        wiki_before = _snap(wiki)
        _freeze(m, 12)
        assert m.process_raw_to_wiki(raw, wiki) == 1
        assert _snap(wiki) == wiki_before and not (raw / "s.md").exists()

    def test_interrupted_wiki_write_is_repaired_on_the_next_run(self, r2w):
        m, raw, wiki = r2w
        (raw / "s.md").write_text(_batch("d", 1, 3), encoding="utf-8")
        m.process_raw_to_wiki(raw, wiki)
        archived = (raw / "processed" / "s.md").read_bytes()
        (raw / "s.md").write_bytes(archived)  # the file is back, wiki entry truncated by a crash
        w = next(wiki.rglob("*_s.md"))
        good = w.read_text(encoding="utf-8")
        w.write_text(good[: len(good) // 3], encoding="utf-8")
        m.process_raw_to_wiki(raw, wiki)
        assert w.read_text(encoding="utf-8") == good, (
            "a damaged entry is rewritten from the archive-identical raw"
        )
        assert not (raw / "s.md").exists()

    def test_empty_raw_file_is_ignored(self, r2w):
        m, raw, wiki = r2w
        (raw / "e.md").write_text("", encoding="utf-8")
        assert m.process_raw_to_wiki(raw, wiki) == 0 and (raw / "e.md").exists()

    def test_dry_run_neither_writes_nor_locks(self, r2w):
        m, raw, wiki = r2w
        m.DRY_RUN = True
        (raw / "s.md").write_text(_batch("d", 1, 3), encoding="utf-8")
        before = _snap(raw.parent)
        m.process_raw_to_wiki(raw, wiki)
        assert _snap(raw.parent) == before and not list(raw.glob("*.lock"))


class TestConcurrentConverters:
    def test_a_second_converter_skips_while_the_first_holds_the_lock(self, r2w):
        from lib.state import file_lock

        m, raw, wiki = r2w
        (raw / "s.md").write_text(_batch("d", 1, 3), encoding="utf-8")
        with file_lock(raw / ".raw_to_wiki.lock", timeout=1.0) as held:
            assert held
            assert m.process_raw_to_wiki(raw, wiki) == 0
        assert (raw / "s.md").exists() and not list(wiki.rglob("*.md"))
        assert m.process_raw_to_wiki(raw, wiki) == 1, "the next Stop picks the work up"

    def test_parallel_processes_convert_every_file_exactly_once(self, tmp_path):
        raw, wiki = tmp_path / "raw", tmp_path / "wiki"
        (raw / "processed").mkdir(parents=True)
        n = 25
        for i in range(n):
            (raw / f"s{i}.md").write_text(_batch(f"d{i}", i, 4), encoding="utf-8")
            if i % 2:  # half of them already have a same-named, DIFFERENT archived batch
                (raw / "processed" / f"s{i}.md").write_text(_batch(f"d{i}", 0, 2), encoding="utf-8")
        originals = {i: (raw / f"s{i}.md").read_bytes() for i in range(n)}
        worker = (
            "import os, sys, time\n"
            "sys.path.insert(0, sys.argv[1]); t0 = float(sys.argv[2])\n"
            "os.environ.pop('CLAUDE_INVOKED_BY', None); os.environ['CLAUDE_DRY_RUN'] = '0'\n"
            "import raw_to_wiki as m\nfrom pathlib import Path\n"
            "m.cogniml_client.push_wiki_entry = lambda *a, **k: None\n"
            "while time.time() < t0: pass\n"
            "print(m.process_raw_to_wiki(Path(sys.argv[3]), Path(sys.argv[4])))\n"
        )
        t0 = time.time() + 2.5
        procs = [
            subprocess.Popen(
                [sys.executable, "-S", "-c", worker, HOOKS, str(t0), str(raw), str(wiki)],
                stdout=subprocess.PIPE,
                text=True,
            )
            for _ in range(4)
        ]
        counts = [int(p.communicate()[0].strip() or 0) for p in procs]
        assert not list(raw.glob("s*.md")), "all files archived"
        assert sum(counts) == n, f"each file converted exactly once across the runs: {counts}"
        archived = [p.read_bytes() for p in (raw / "processed").glob("s*.md")]
        for i in range(n):
            assert originals[i] in archived, f"batch of s{i}.md lost"
        assert len(list(wiki.rglob("*_s*.md"))) == n
        assert not list(raw.glob("*.lock")) and not list(raw.glob("*.tmp*"))
