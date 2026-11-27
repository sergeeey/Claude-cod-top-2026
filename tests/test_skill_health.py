"""Tests for scripts/skill_health.py, the read-only skill health report (2026-11-24).

Each check is exercised on a throwaway skills tree under tmp_path. The real repo is only run as a
smoke test, and its exit code is not asserted: until the frontmatter-first fix is merged, the
real skills tree can legitimately report BLOCK findings.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import skill_health  # noqa: E402

GOOD = "---\nname: {name}\ndescription: Does a thing. Use when asked.\n---\n\nBody.\n"


def make_tree(tmp_path: Path, skills: dict[str, str], registry: list[dict] | None = None) -> Path:
    base = tmp_path / "skills"
    for name, text in skills.items():
        d = base / "extensions" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_bytes(text.encode("utf-8"))
    if registry is not None:
        import yaml

        (base / "registry.yaml").write_text(
            yaml.safe_dump({"core": [], "extensions": registry}), encoding="utf-8"
        )
    return base


def checks(result: dict) -> set[tuple[str, str]]:
    return {(f.severity, f.check) for f in result["findings"]}


def run(base: Path, **kw) -> dict:
    return skill_health.analyse(base, base / "registry.yaml", **kw)


def test_clean_tree_has_no_findings(tmp_path):
    base = make_tree(tmp_path, {"alpha": GOOD.format(name="alpha")})
    assert run(base)["findings"] == []


def test_comment_before_frontmatter_blocks(tmp_path):
    text = "<!-- BSV card -->\n\n" + GOOD.format(name="alpha")
    base = make_tree(tmp_path, {"alpha": text})
    assert ("BLOCK", "frontmatter_not_first") in checks(run(base))


def test_bom_before_frontmatter_is_accepted(tmp_path):
    base = make_tree(tmp_path, {"alpha": "﻿" + GOOD.format(name="alpha")})
    assert run(base)["findings"] == []


def test_missing_frontmatter_blocks(tmp_path):
    base = make_tree(tmp_path, {"alpha": "# Just a heading\n"})
    assert ("BLOCK", "frontmatter_not_first") in checks(run(base))


def test_unclosed_and_invalid_yaml_warn(tmp_path):
    base = make_tree(
        tmp_path,
        {
            "unclosed": "---\nname: unclosed\ndescription: x\n",
            "badyaml": "---\nname: [badyaml\ndescription: x\n---\nbody\n",
        },
    )
    found = checks(run(base))
    assert ("WARN", "frontmatter_yaml_error") in found
    assert not any(sev == "BLOCK" for sev, _ in found)


def test_name_mismatch_and_missing_description_warn(tmp_path):
    base = make_tree(
        tmp_path,
        {
            "alpha": "---\nname: Alpha Skill\ndescription: Does a thing.\n---\nbody\n",
            "beta": "---\nname: beta\n---\nbody\n",
        },
    )
    found = checks(run(base))
    assert ("WARN", "name_mismatch") in found
    assert ("WARN", "no_description") in found


def test_listing_text_cap_counts_when_to_use(tmp_path):
    text = "---\nname: alpha\ndescription: " + "a" * 100 + "\nwhen_to_use: " + "b" * 100 + "\n---\n"
    base = make_tree(tmp_path, {"alpha": text})
    assert ("WARN", "listing_text_over_cap") not in checks(run(base))
    assert ("WARN", "listing_text_over_cap") in checks(run(base, desc_cap=150))


def test_body_too_long_is_advisory(tmp_path):
    text = GOOD.format(name="alpha") + "line\n" * 30
    base = make_tree(tmp_path, {"alpha": text})
    result = run(base, max_lines=20)
    assert ("WARN", "body_too_long") in checks(result)
    assert skill_health.main(["--skills-dir", str(base), "--registry", str(base / "r.yaml")]) == 0


def test_trigger_collision_and_registry_folder_mismatch(tmp_path):
    base = make_tree(
        tmp_path,
        {"alpha": GOOD.format(name="alpha"), "beta": GOOD.format(name="beta")},
        registry=[
            {"name": "alpha", "triggers": ["Audit", "alpha"], "maturity": "dogfooded"},
            {"name": "beta", "triggers": ["audit"], "maturity": "wired"},
            {"name": "ghost", "triggers": ["boo"], "maturity": "described"},
        ],
    )
    result = run(base)
    found = checks(result)
    assert ("WARN", "trigger_collision") in found
    assert ("WARN", "registry_no_folder") in found
    totals = result["totals"]
    assert (totals["skill_folders"], totals["registry_entries"], totals["dogfooded"]) == (2, 3, 1)


def test_folder_without_registry_entry_warns(tmp_path):
    base = make_tree(
        tmp_path,
        {"alpha": GOOD.format(name="alpha"), "orphan": GOOD.format(name="orphan")},
        registry=[{"name": "alpha", "triggers": ["a"], "maturity": "wired"}],
    )
    assert ("WARN", "folder_no_registry") in checks(run(base))


def test_token_ratio_uses_file_size(tmp_path):
    text = GOOD.format(name="alpha") + "x" * 4000
    base = make_tree(
        tmp_path,
        {"alpha": text},
        registry=[{"name": "alpha", "tokens": "~100", "maturity": "wired"}],
    )
    ratio = run(base)["totals"]["median_actual_over_declared_tokens"]
    assert ratio is not None and ratio > 9


def test_only_block_changes_exit_code_and_json_is_valid(tmp_path, capsys):
    good = make_tree(tmp_path / "good", {"alpha": GOOD.format(name="alpha")})
    bad = make_tree(tmp_path / "bad", {"alpha": "<!-- c -->\n" + GOOD.format(name="alpha")})
    assert skill_health.main(["--skills-dir", str(good), "--registry", str(good / "r.yaml")]) == 0
    capsys.readouterr()
    code = skill_health.main(
        ["--skills-dir", str(bad), "--registry", str(bad / "r.yaml"), "--json"]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["blocking"] is True
    assert payload["repo"]["findings"][0]["check"] == "frontmatter_not_first"


def test_live_scan_reports_installed_copy(tmp_path, capsys):
    repo = make_tree(tmp_path / "repo", {"alpha": "<!-- c -->\n" + GOOD.format(name="alpha")})
    live = make_tree(tmp_path / "live", {"alpha": GOOD.format(name="alpha")})
    code = skill_health.main(
        [
            "--skills-dir",
            str(repo),
            "--registry",
            str(repo / "r.yaml"),
            "--live",
            str(live),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1  # the repo copy is what blocks
    assert payload["live"]["only_in_repo_broken"] == ["alpha"]


def test_duplicate_folder_names_keep_findings_from_every_copy(tmp_path):
    """A broken flat copy next to a valid nested copy must not be hidden by the name lookup."""
    base = make_tree(tmp_path, {"alpha": GOOD.format(name="alpha")})  # extensions/alpha, valid
    flat = base / "alpha"
    flat.mkdir()
    (flat / "SKILL.md").write_text("<!-- c -->\n" + GOOD.format(name="alpha"), encoding="utf-8")
    result = run(base)
    found = checks(result)
    assert ("BLOCK", "frontmatter_not_first") in found
    assert ("WARN", "duplicate_skill_name") in found
    blocked = [f for f in result["findings"] if f.check == "frontmatter_not_first"]
    assert [f.path for f in blocked] == ["alpha/SKILL.md"]
    assert result["totals"]["skill_files"] == 2
    assert result["totals"]["skill_folders"] == 1


def test_real_repo_smoke():
    result = skill_health.analyse(REPO_ROOT / "skills", REPO_ROOT / "skills" / "registry.yaml")
    assert result["totals"]["skill_folders"] > 100
    assert result["totals"]["registry_entries"] >= result["totals"]["skill_folders"]
