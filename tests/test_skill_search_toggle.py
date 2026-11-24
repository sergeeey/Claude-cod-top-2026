"""skill_search_toggle: preview writes nothing, install is marked, removal restores the file."""

import os
import sys
from pathlib import Path

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

import skill_search_toggle as tg  # noqa: E402

ORIGINAL = "# My rules\n\nBe brief.\n"


def run(target: Path, *flags: str) -> int:
    return tg.main(["--target", str(target), *flags])


def test_preview_is_the_default_and_writes_nothing(tmp_path, capsys):
    f = tmp_path / "CLAUDE.md"
    f.write_bytes(ORIGINAL.encode("utf-8"))
    assert run(f) == 0
    assert f.read_text(encoding="utf-8") == ORIGINAL
    assert not list(tmp_path.glob("*.bak*"))
    assert "PREVIEW" in capsys.readouterr().out


def test_install_adds_one_marked_block_with_backup_and_is_idempotent(tmp_path):
    f = tmp_path / "CLAUDE.md"
    f.write_bytes(ORIGINAL.encode("utf-8"))
    run(f, "--apply")
    once = f.read_text(encoding="utf-8")
    assert once.startswith(ORIGINAL) and once.count(tg.BEGIN) == 1 and tg.END in once
    assert "skill_search.py" in once and "no listed skill fits" in once
    assert (tmp_path / "CLAUDE.md.bak-skill-search").read_text(encoding="utf-8") == ORIGINAL
    run(f, "--apply")
    assert f.read_text(encoding="utf-8") == once


def test_remove_restores_the_original_bytes(tmp_path):
    f = tmp_path / "CLAUDE.md"
    f.write_bytes(ORIGINAL.encode("utf-8"))
    run(f, "--apply")
    run(f, "--remove", "--apply")
    assert f.read_bytes() == ORIGINAL.encode("utf-8")


def test_missing_target_is_created_and_removal_on_clean_file_changes_nothing(tmp_path, capsys):
    f = tmp_path / "new.md"
    run(f, "--apply")
    assert tg.BEGIN in f.read_text(encoding="utf-8")
    g = tmp_path / "clean.md"
    g.write_bytes(ORIGINAL.encode("utf-8"))
    assert run(g, "--remove", "--apply") == 0
    assert g.read_text(encoding="utf-8") == ORIGINAL
    assert "nothing to change" in capsys.readouterr().out
