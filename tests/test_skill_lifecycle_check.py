"""Tests for scripts/skill_lifecycle_check.py.

Control/mutation/adversarial pattern, mirroring this repo's existing
architecture-gate tests: a real fixture (a temp skill file with known
content) must PASS; removing a required phrase must FAIL; a missing
skill_file must SKIP, never FAIL (absence of a personal-only file is not
evidence of regression).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.skill_lifecycle_check import (
    check_fixture,
    load_fixture,
    run_all,
)


def _write_fixture(tmp_path: Path, skill_file: Path, required_strings: list[dict]) -> Path:
    fixture_path = tmp_path / "fixture.yaml"
    fixture_path.write_text(
        yaml.safe_dump(
            {
                "skill": "test-skill",
                "skill_file": str(skill_file),
                "required_strings": required_strings,
            }
        ),
        encoding="utf-8",
    )
    return fixture_path


def test_pass_when_all_required_strings_present(tmp_path: Path) -> None:
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("Some content.\nAlways do X — потому что Y.\n", encoding="utf-8")
    fixture_path = _write_fixture(
        tmp_path, skill_file, [{"text": "Always do X — потому что Y", "why": "core rule"}]
    )
    fixture = load_fixture(fixture_path)
    result = check_fixture(fixture)
    assert result.status == "PASS"
    assert result.missing == []


def test_fail_when_required_string_removed(tmp_path: Path) -> None:
    skill_file = tmp_path / "SKILL.md"
    # WHY: simulates the exact real failure mode this tool exists for --
    # someone edits a skill and the mandatory rule silently disappears.
    skill_file.write_text("Some content without the rule.\n", encoding="utf-8")
    fixture_path = _write_fixture(
        tmp_path, skill_file, [{"text": "Always do X — потому что Y", "why": "core rule"}]
    )
    fixture = load_fixture(fixture_path)
    result = check_fixture(fixture)
    assert result.status == "FAIL"
    assert len(result.missing) == 1
    assert result.missing[0].text == "Always do X — потому что Y"


def test_skip_when_skill_file_does_not_exist(tmp_path: Path) -> None:
    missing_path = tmp_path / "does_not_exist" / "SKILL.md"
    fixture_path = _write_fixture(tmp_path, missing_path, [{"text": "anything"}])
    fixture = load_fixture(fixture_path)
    result = check_fixture(fixture)
    assert result.status == "SKIPPED"
    assert result.missing == []


def test_partial_removal_reports_only_the_missing_ones(tmp_path: Path) -> None:
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("Rule A is here.\n", encoding="utf-8")
    fixture_path = _write_fixture(
        tmp_path,
        skill_file,
        [{"text": "Rule A is here", "why": "a"}, {"text": "Rule B is here", "why": "b"}],
    )
    fixture = load_fixture(fixture_path)
    result = check_fixture(fixture)
    assert result.status == "FAIL"
    assert [m.text for m in result.missing] == ["Rule B is here"]


def test_run_all_returns_empty_list_when_fixtures_dir_missing(tmp_path: Path) -> None:
    assert run_all(fixtures_dir=tmp_path / "nonexistent") == []


def test_run_all_reads_real_fixtures_dir_without_crashing() -> None:
    # WHY: exercises the actual skills/lifecycle_tests/ fixtures committed to
    # this repo (currently boyko-scientific-consortium.yaml, a personal
    # skill's fixture). On CI (Linux) the referenced skill_file legitimately
    # does not exist -- must SKIP, never FAIL, and must never raise.
    results = run_all()
    for r in results:
        assert r.status in {"PASS", "FAIL", "SKIPPED"}
        if r.status == "FAIL":
            pytest.fail(
                f"skill lifecycle regression detected in {r.skill}: {[m.text for m in r.missing]}"
            )
