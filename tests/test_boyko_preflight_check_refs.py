"""Tests for skills/extensions/boyko-preflight/scripts/check_refs.py (borrowed idea, 2026-11-01).

Source of the idea: claude-md-doctor dead-reference check (agent-clinic, verified).
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "extensions"
    / "boyko-preflight"
    / "scripts"
    / "check_refs.py"
)


@pytest.fixture(scope="module")
def cr():
    spec = importlib.util.spec_from_file_location("check_refs", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidate_refs_picks_only_path_like_backticks(cr):
    text = "See `rules/a.md`, `run.py`, `config.json`, plain word, `has space.md`, `*.md`."
    assert cr.candidate_refs(text) == ["rules/a.md", "run.py", "config.json"]


def test_urls_and_non_paths_are_skipped(cr):
    text = "Link `https://x.io/a.md` and `version 1.0`."
    assert cr.candidate_refs(text) == []


def test_existing_relative_ref_resolves(cr, tmp_path):
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "a.md").write_text("x", encoding="utf-8")
    md = tmp_path / "CLAUDE.md"
    md.write_text("Read `rules/a.md` first.", encoding="utf-8")
    assert cr.missing_refs(md, None) == []


def test_missing_ref_is_reported(cr, tmp_path):
    md = tmp_path / "CLAUDE.md"
    md.write_text("Run `scripts/gone.py` before commit.", encoding="utf-8")
    assert cr.missing_refs(md, None) == ["scripts/gone.py"]


def test_base_directory_is_searched(cr, tmp_path):
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "tool.py").write_text("x", encoding="utf-8")
    skill_dir = tmp_path / "skills"
    skill_dir.mkdir()
    md = skill_dir / "SKILL.md"
    md.write_text("Use `scripts/tool.py`.", encoding="utf-8")
    assert cr.missing_refs(md, None) == ["scripts/tool.py"]
    assert cr.missing_refs(md, repo) == []


def test_duplicate_missing_ref_listed_once(cr, tmp_path):
    md = tmp_path / "CLAUDE.md"
    md.write_text("`gone.md` and again `gone.md`.", encoding="utf-8")
    assert cr.missing_refs(md, None) == ["gone.md"]


def test_main_exit_codes(cr, tmp_path, monkeypatch, capsys):
    ok = tmp_path / "ok.md"
    (tmp_path / "a.md").write_text("x", encoding="utf-8")
    ok.write_text("See `a.md`.", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["check_refs.py", str(ok)])
    assert cr.main() == 0

    bad = tmp_path / "bad.md"
    bad.write_text("See `missing.md`.", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["check_refs.py", str(bad)])
    assert cr.main() == 1
    assert "missing.md" in capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["check_refs.py"])
    assert cr.main() == 2


def test_bare_name_found_in_subdirectory_resolves(cr, tmp_path):
    base = tmp_path / "repo"
    (base / "scripts").mkdir(parents=True)
    (base / "scripts" / "check_architecture.py").write_text("x", encoding="utf-8")
    md = tmp_path / "CLAUDE.md"
    md.write_text("Run `check_architecture.py` before merge.", encoding="utf-8")
    assert cr.missing_refs(md, base) == []


def test_bare_name_missing_everywhere_is_reported(cr, tmp_path):
    base = tmp_path / "repo"
    base.mkdir()
    md = tmp_path / "CLAUDE.md"
    md.write_text("Run `nowhere.py`.", encoding="utf-8")
    assert cr.missing_refs(md, base) == ["nowhere.py"]


def test_path_with_slash_must_exist_exactly(cr, tmp_path):
    base = tmp_path / "repo"
    (base / "other").mkdir(parents=True)
    (base / "other" / "tool.py").write_text("x", encoding="utf-8")
    md = tmp_path / "CLAUDE.md"
    md.write_text("Run `scripts/tool.py`.", encoding="utf-8")
    assert cr.missing_refs(md, base) == ["scripts/tool.py"]
