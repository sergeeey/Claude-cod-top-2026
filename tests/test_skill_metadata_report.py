"""Warning-mode skill metadata report (check_architecture.skill_metadata_report): counts, defects, no failure."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

check = pytest.importorskip("check_architecture")
snap = pytest.importorskip("snapshot_state")

ROOT = Path(__file__).resolve().parent.parent


def write(root: Path, section: str, name: str, text: str) -> None:
    d = root / "skills" / section / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(text, encoding="utf-8")


def entry(name: str, desc: str = "d", triggers=None, **extra):
    return {"name": name, "description": desc, "triggers": triggers or [], **extra}


def test_classification_names_the_nature_of_a_difference():
    cd = check.classify_description
    assert cd("Reconcile bank statements", "Reconcile bank statements") == "identical"
    assert (
        cd(
            "Reconcile bank statements against the ledger and flag",
            "Reconcile bank statements against the ledger and flag every gap in detail",
        )
        == "one is a cut of the other"
    )
    assert cd("x", "[STATUS: review] [CONFIDENCE: high] x") == "identical"  # banner is not wording
    assert (
        cd("Составляет отчёты о работе", "Reports generator tool")
        == "different wording or language"
    )
    assert cd("", "anything") == "missing"
    ct = check.classify_triggers
    assert ct(["a", "b"], ["a", "b"]) == "equal"
    assert ct(["a"], ["a", "c"]) == "partial overlap"
    assert ct(["a"], ["c"]) == "disjoint"
    assert ct(["a"], None) == "SKILL.md has none"


def test_definite_defects_are_listed_and_the_report_never_raises(tmp_path):
    write(
        tmp_path,
        "extensions",
        "good",
        "---\nname: good\ndescription: Reconcile ledger\ntriggers: [a]\n---\n# g\n",
    )
    write(tmp_path, "extensions", "late", "# title first\n---\nname: late\ndescription: x\n---\n")
    write(tmp_path, "extensions", "renamed", "---\nname: other-name\ndescription: y\n---\n# r\n")
    write(tmp_path, "extensions", "bad", "---\nname: [unclosed\n---\n")
    reg = {
        "extensions": [
            entry("good", "Reconcile ledger", ["a"]),
            entry("late"),
            entry("renamed"),
            entry("bad"),
            entry("good", "Reconcile ledger", ["a"]),  # duplicate name in the registry
            entry("ext", type="external"),  # non-local: skipped, no SKILL.md expected
        ]
    }
    rep = check.skill_metadata_report(reg, tmp_path)
    assert rep["unparseable_skill_md"] == ["bad", "late"]
    assert rep["name_mismatch"] == ["renamed"]
    assert rep["duplicate_registry_names"] == ["good"]
    assert rep["description"]["identical"] == 2  # the two registry entries named "good"
    warns = check.skill_metadata_warnings(rep)
    assert len(warns) == 3 and all("skill(s)" in w for w in warns)


def test_main_stays_green_and_exit_code_zero_even_with_warnings(capsys):
    assert check.main(["--check"]) == 0  # the real tree: warnings go to stderr, nothing fails
    assert "Architectural coherence: FAIL" not in capsys.readouterr().err


def test_banner_led_descriptions_are_counted(tmp_path):
    write(
        tmp_path,
        "core",
        "b",
        "---\nname: b\ndescription: '[STATUS: review] [CONFIDENCE: high] Does a thing'\n---\n",
    )
    write(tmp_path, "core", "p", "---\nname: p\ndescription: Does another thing\n---\n")
    rep = check.skill_metadata_report({"core": [entry("b"), entry("p")]}, tmp_path)
    assert rep["banner_leading"] == 1


def test_snapshot_records_the_counts_as_metrics(tmp_path):
    m = snap.build(ROOT, tmp_path / "missing", None)["metrics"]
    assert "repo.skill_md_unparseable" in m and "repo.skill_banner_leading" in m
    assert any(k.startswith("repo.skill_desc.") for k in m)
    assert any(k.startswith("repo.skill_triggers.") for k in m)
    json.dumps(m)  # serialisable for --compare
