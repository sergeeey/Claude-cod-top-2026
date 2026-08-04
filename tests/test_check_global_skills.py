"""Tests for scripts/check_global_skills.py — repo<->global skill deployment gate.

WHY: 0% coverage before this file. main() reads ROOT/skills/registry.yaml and
compares against GLOBAL_SKILLS (~/.claude/skills/), both module-level Path
constants -- tests monkeypatch both to point at a hermetic tmp_path registry
instead of this machine's real ~/.claude/skills/.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import check_global_skills
from check_global_skills import main


def _write_registry(root: Path, entries: dict) -> None:
    (root / "skills").mkdir(parents=True, exist_ok=True)
    (root / "skills" / "registry.yaml").write_text(
        yaml.safe_dump(entries, allow_unicode=True), encoding="utf-8"
    )


class TestMain:
    def test_directory_skill_deployed_both_sides(self, tmp_path, monkeypatch, capsys):
        root = tmp_path / "repo"
        global_skills = tmp_path / "global"
        (root / "skills" / "core" / "orient").mkdir(parents=True)
        (global_skills / "orient").mkdir(parents=True)
        _write_registry(root, {"core": [{"name": "orient"}], "extensions": []})
        monkeypatch.setattr(check_global_skills, "ROOT", root)
        monkeypatch.setattr(check_global_skills, "GLOBAL_SKILLS", global_skills)

        main()

        out = capsys.readouterr().out
        assert "All repo skills are deployed globally." in out

    def test_directory_skill_missing_globally_exits_1(self, tmp_path, monkeypatch, capsys):
        root = tmp_path / "repo"
        global_skills = tmp_path / "global"
        (root / "skills" / "core" / "orient").mkdir(parents=True)
        global_skills.mkdir(parents=True)
        _write_registry(root, {"core": [{"name": "orient"}], "extensions": []})
        monkeypatch.setattr(check_global_skills, "ROOT", root)
        monkeypatch.setattr(check_global_skills, "GLOBAL_SKILLS", global_skills)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        out = capsys.readouterr().out
        assert "NOT deployed globally" in out
        assert "orient" in out
        assert "cp -r" in out

    def test_file_type_skill_uses_md_suffix_path(self, tmp_path, monkeypatch, capsys):
        root = tmp_path / "repo"
        global_skills = tmp_path / "global"
        (root / "skills" / "extensions").mkdir(parents=True)
        (root / "skills" / "extensions" / "python-geodata.md").write_text("x", encoding="utf-8")
        global_skills.mkdir(parents=True)
        _write_registry(
            root, {"core": [], "extensions": [{"name": "python-geodata", "type": "file"}]}
        )
        monkeypatch.setattr(check_global_skills, "ROOT", root)
        monkeypatch.setattr(check_global_skills, "GLOBAL_SKILLS", global_skills)

        with pytest.raises(SystemExit):
            main()

        out = capsys.readouterr().out
        assert 'cp "' in out
        assert "python-geodata.md" in out

    def test_external_type_skill_is_skipped_not_flagged_missing(
        self, tmp_path, monkeypatch, capsys
    ):
        root = tmp_path / "repo"
        global_skills = tmp_path / "global"
        root.mkdir(parents=True)
        global_skills.mkdir(parents=True)
        _write_registry(
            root, {"core": [], "extensions": [{"name": "last30days", "type": "external"}]}
        )
        monkeypatch.setattr(check_global_skills, "ROOT", root)
        monkeypatch.setattr(check_global_skills, "GLOBAL_SKILLS", global_skills)

        main()

        out = capsys.readouterr().out
        assert "Skipped (external/community, no local deploy expected): 1" in out
        assert "All repo skills are deployed globally." in out

    def test_ghost_registry_entry_without_repo_path_is_ignored(self, tmp_path, monkeypatch, capsys):
        root = tmp_path / "repo"
        global_skills = tmp_path / "global"
        root.mkdir(parents=True)
        global_skills.mkdir(parents=True)
        _write_registry(root, {"core": [{"name": "does-not-exist-on-disk"}], "extensions": []})
        monkeypatch.setattr(check_global_skills, "ROOT", root)
        monkeypatch.setattr(check_global_skills, "GLOBAL_SKILLS", global_skills)

        main()

        out = capsys.readouterr().out
        assert "Registry: 0 deployable entries checked" in out
        assert "All repo skills are deployed globally." in out
