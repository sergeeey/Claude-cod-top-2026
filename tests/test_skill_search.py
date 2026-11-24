"""Tests for scripts/skill_search.py: what is indexed, freshness, ranking, abstention, privacy."""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

import skill_search as ss  # noqa: E402

# Thresholds are passed explicitly so these tests do not depend on the calibrated defaults.
LOOSE = {"min_score": 0.0, "min_matched": 1, "min_cov": 0.0}


def make_skill(base: Path, folder: str, name: str, desc: str, body: str = "Body.", extra: str = ""):
    d = base / folder
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n{extra}---\n\n# {name}\n\n{body}\n",
        encoding="utf-8",
    )
    return d


def home_with(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    (home / "skills").mkdir(parents=True)
    return home, home / "skills"


def names(res: dict) -> list[str]:
    return [c["name"] for c in res["candidates"]]


def test_backups_disabled_hidden_and_overridden_skills_are_not_indexed(tmp_path):
    home, sk = home_with(tmp_path)
    make_skill(sk, "good", "good", "incident postmortem workflow")
    make_skill(sk, "good.bak-20261101", "good", "incident postmortem workflow old copy")
    make_skill(sk, "good-backup", "good-backup", "incident postmortem backup")
    make_skill(sk, "_private", "private-thing", "incident postmortem private")
    make_skill(sk, ".dot", "dot-thing", "incident postmortem dot")
    make_skill(
        sk,
        "nomodel",
        "nomodel",
        "incident postmortem manual",
        extra="disable-model-invocation: true\n",
    )
    make_skill(sk, "ovoff", "ovoff", "incident postmortem off")
    make_skill(sk, "ovuio", "ovuio", "incident postmortem user only")
    make_skill(sk, "ovname", "ovname", "incident postmortem name only")
    make_skill(home / "skills-disabled", "dis", "dis", "incident postmortem disabled copy")
    (home / "settings.json").write_text(
        json.dumps(
            {
                "skillOverrides": {
                    "ovoff": "off",
                    "ovuio": "user-invocable-only",
                    "ovname": "name-only",
                }
            }
        ),
        encoding="utf-8",
    )
    skills, stats = ss.collect(home, None)
    assert sorted(s.name for s in skills) == ["good", "ovname"]
    assert stats["hidden_by_override"] == 2
    assert stats["model_invocation_disabled"] == 1


def test_unreadable_and_invalid_files_are_skipped_and_counted_not_fatal(tmp_path):
    home, sk = home_with(tmp_path)
    make_skill(sk, "ok", "ok", "deploy rollback procedure")
    (sk / "nofm").mkdir()
    (sk / "nofm" / "SKILL.md").write_text("no frontmatter here", encoding="utf-8")
    (sk / "badyaml").mkdir()
    (sk / "badyaml" / "SKILL.md").write_text(
        "---\nname: bad\ndescription: a: b: [\n---\nx", encoding="utf-8"
    )
    skills, stats = ss.collect(home, None)
    assert [s.name for s in skills] == ["ok"]
    assert stats["skipped_unreadable"] == 2


def test_project_skills_are_indexed_and_user_scope_wins_a_name_clash(tmp_path):
    home, sk = home_with(tmp_path)
    make_skill(sk, "shared", "shared", "personal version about invoices")
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    make_skill(root / ".claude" / "skills", "shared", "shared", "project version about invoices")
    make_skill(
        root / ".claude" / "skills", "only-here", "only-here", "project only translation memory"
    )
    sub = root / "pkg" / "inner"
    sub.mkdir(parents=True)
    skills, stats = ss.collect(home, sub)  # started in a subdirectory: parents up to .git count
    by = {s.name: s for s in skills}
    assert set(by) == {"shared", "only-here"}
    assert by["shared"].scope == "user" and by["only-here"].scope == "project"
    assert stats["shadowed"] == 1


def test_index_is_fresh_after_add_edit_rename_and_remove_without_any_rebuild_step(tmp_path):
    home, sk = home_with(tmp_path)
    make_skill(sk, "a", "alpha-skill", "reconcile ledger entries")
    q = "reconcile ledger entries"
    assert names(ss.search(q, home, **LOOSE)) == ["alpha-skill"]
    make_skill(sk, "b", "beta-skill", "reconcile ledger entries monthly close")  # add
    assert "beta-skill" in names(ss.search(q, home, **LOOSE))
    make_skill(sk, "a", "alpha-skill", "something else entirely about gardening")  # edit
    assert "alpha-skill" not in names(ss.search(q, home, **LOOSE))
    (sk / "b").rename(sk / "b2")  # rename the folder; the frontmatter name stays
    assert "beta-skill" in names(ss.search(q, home, **LOOSE))
    import shutil

    shutil.rmtree(sk / "b2")  # remove
    assert ss.search(q, home, **LOOSE)["candidates"] == []


def test_finds_a_skill_by_description_by_body_and_in_russian_and_english(tmp_path):
    home, sk = home_with(tmp_path)
    make_skill(sk, "inc", "incident-response", "Разбор производственного инцидента и постмортем")
    make_skill(
        sk, "tax", "tax-helper", "Prepare quarterly tax filings", body="VAT reconciliation steps"
    )
    make_skill(sk, "misc", "misc", "Unrelated gardening notes")
    assert (
        names(ss.search("разобрать инцидент и написать постмортем", home, **LOOSE))[0]
        == "incident-response"
    )
    assert names(ss.search("quarterly tax filings", home, **LOOSE))[0] == "tax-helper"
    # body-only terms influence ranking but are never enough to recommend (see the head rule)
    skills, _ = ss.collect(home, None)
    assert ss.rank(skills, "VAT reconciliation")[0]["name"] == "tax-helper"
    assert ss.search("VAT reconciliation", home, **LOOSE)["candidates"] == []


def test_abstains_when_nothing_fits_and_on_empty_or_stopword_queries(tmp_path):
    home, sk = home_with(tmp_path)
    make_skill(sk, "tax", "tax-helper", "Prepare quarterly tax filings")
    assert ss.search("", home)["confident"] is False
    assert ss.search("the and for", home)["confident"] is False
    res = ss.search("translate this paragraph to French", home)
    assert res["confident"] is False and res["candidates"] == []


def test_a_coincidence_in_the_body_alone_does_not_count_as_evidence(tmp_path):
    home, sk = home_with(tmp_path)
    make_skill(
        sk,
        "x",
        "x-skill",
        "Prepare quarterly tax filings",
        body="mentions refactoring and cleanup once",
    )
    strict = {"min_score": 0.0, "min_matched": 2, "min_cov": 0.0}
    res = ss.search("refactoring cleanup", home, **strict)
    assert res["confident"] is False  # both terms match, but only in the body


def test_floors_decide_between_a_recommendation_and_silence():
    ranked = [
        {"name": "a", "score": 9.0, "cov": 0.9, "matched": ["x", "y"], "matched_head": ["x", "y"]}
    ]
    assert ss.decide(ranked, 5, 7.0, 2, 0.8)[0] is True
    assert ss.decide(ranked, 5, 10.0, 2, 0.8)[0] is False  # score floor
    assert ss.decide(ranked, 5, 7.0, 3, 0.8)[0] is False  # matched floor
    assert ss.decide(ranked, 5, 7.0, 2, 0.95)[0] is False  # coverage floor
    assert ss.decide([], 5)[0] is False


def test_trigger_phrases_are_indexed_only_when_asked(tmp_path):
    home, sk = home_with(tmp_path)
    make_skill(
        sk, "t", "t-skill", "generic helper", extra='triggers: ["balance the quarterly books"]\n'
    )
    assert names(ss.search("balance quarterly books", home, include_triggers=True, **LOOSE)) == [
        "t-skill"
    ]
    assert (
        ss.search("balance quarterly books", home, include_triggers=False, **LOOSE)["candidates"]
        == []
    )


def test_frontmatter_fallback_works_without_pyyaml(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "yaml", None)
    d = tmp_path / "s"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: folded\ndescription: >\n  Reconcile bank statements\n  against the ledger.\n"
        'triggers: ["match payments", other phrase]\ndisable-model-invocation: false\n---\n\n# H\n',
        encoding="utf-8",
    )
    fm, _ = ss.read_skill(d / "SKILL.md")
    assert fm["name"] == "folded"
    assert "Reconcile bank statements against the ledger." in fm["description"]
    assert fm["triggers"] == ["match payments", "other phrase"]


def test_search_writes_nothing_and_prints_no_private_text_to_disk(tmp_path):
    home, sk = home_with(tmp_path)
    make_skill(sk, "a", "private-name-skill", "reconcile ledger entries")
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    ss.search("reconcile ledger entries", home, **LOOSE)
    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    assert before == after


def test_cli_prints_candidates_or_the_no_match_message_and_always_exits_zero(tmp_path, capsys):
    home, sk = home_with(tmp_path)
    make_skill(sk, "a", "ledger-skill", "reconcile ledger entries")
    rc = ss.main(["reconcile ledger entries", "--home", str(home), "--project", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0 and out.startswith("[skill-search]")
    rc = ss.main(["make me a sandwich", "--home", str(home), "--project", str(tmp_path)])
    assert rc == 0 and "no confident match" in capsys.readouterr().out
    rc = ss.main(
        ["reconcile ledger entries", "--home", str(home), "--project", str(tmp_path), "--json"]
    )
    data = json.loads(capsys.readouterr().out)
    assert rc == 0 and {"confident", "candidates", "stats"} <= set(data)


def test_building_and_searching_three_hundred_skills_stays_cheap(tmp_path):
    home, sk = home_with(tmp_path)
    for i in range(300):
        make_skill(
            sk, f"s{i}", f"skill-{i}", f"does thing number {i} about topic{i % 40}", body="x " * 300
        )
    t0 = time.perf_counter()
    res = ss.search("topic7 thing", home, **LOOSE)
    assert time.perf_counter() - t0 < 5.0
    assert res["stats"]["indexed"] == 300


def test_yo_and_ye_are_the_same_letter_for_search(tmp_path):
    home, sk = home_with(tmp_path)
    make_skill(sk, "r", "report-skill", "Составляет отчёты о проделанной работе")
    assert names(ss.search("написать отчет о работе", home, **LOOSE)) == ["report-skill"]
    assert names(ss.search("отчёт", home, **LOOSE)) == ["report-skill"]


def test_nested_layout_is_indexed_only_for_explicit_extra_roots(tmp_path):
    home, skills = home_with(tmp_path)
    make_skill(skills / "extensions", "ledger", "ledger", "Reconcile bank statements")
    make_skill(skills, "flat", "flat", "Flat native skill")
    extra = tmp_path / "repo" / "skills"
    make_skill(extra / "extensions", "ledger2", "ledger2", "Reconcile invoices")
    native, _ = ss.collect(home, None)
    assert {s.name for s in native} == {"flat"}
    withextra, _ = ss.collect(home, None, extra_roots=[extra])
    assert {s.name for s in withextra} == {"flat", "ledger2"}


def test_project_overrides_are_read_from_every_root_up_to_the_git_root(tmp_path):
    home, _ = home_with(tmp_path)
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    make_skill(repo / ".claude" / "skills", "ledger", "ledger", "Reconcile bank statements")
    (repo / ".claude" / "settings.json").write_text(
        json.dumps({"skillOverrides": {"ledger": "off"}}), encoding="utf-8"
    )
    sub = repo / "src" / "pkg"
    sub.mkdir(parents=True)
    from_root, _ = ss.collect(home, repo)
    from_sub, _ = ss.collect(home, sub)
    assert [s.name for s in from_root] == [] and [s.name for s in from_sub] == []


def test_fallback_parser_understands_inline_comments_on_the_invocation_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "yaml", None)
    home, skills = home_with(tmp_path)
    make_skill(
        skills,
        "manual",
        "manual",
        "Reconcile bank statements",
        extra="disable-model-invocation: true # manual only\n",
    )
    make_skill(skills, "auto", "auto", "Reconcile bank invoices", extra="note: a # b\n")
    found, st = ss.collect(home, None)
    assert [s.name for s in found] == ["auto"]
    assert st["model_invocation_disabled"] == 1
