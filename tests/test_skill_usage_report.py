"""Tests for scripts/skill_usage_report.py: counting, deduplication, exposure, privacy."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

import skill_usage_report as sur  # noqa: E402

SENTINEL = "PRIVATE-PROMPT-TEXT-SENTINEL"
DAY = "2026-11-20T10:00:00.000Z"


def _assistant(mid, uuid, tool=None, usage=(1, 2, 3)):
    content = []
    if tool:
        content.append(
            {"type": "tool_use", "id": tool[0], "name": "Skill", "input": {"skill": tool[1]}}
        )
    return {
        "type": "assistant",
        "timestamp": DAY,
        "uuid": uuid,
        "message": {
            "id": mid,
            "model": "m",
            "content": content,
            "usage": {
                "input_tokens": usage[0],
                "output_tokens": usage[1],
                "cache_creation_input_tokens": usage[2],
                "cache_read_input_tokens": 999999,
            },
        },
    }


def _write(path: Path, records):
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def _fixture(root: Path):
    proj = root / "proj"
    proj.mkdir(parents=True)
    listing = {
        "type": "attachment",
        "timestamp": DAY,
        "attachment": {
            "type": "skill_listing",
            "isInitial": True,
            "content": "- alpha: does alpha things\n- beta\n- gamma: gamma description",
        },
    }
    records = [
        listing,
        {
            "type": "user",
            "timestamp": DAY,
            "uuid": "u1",
            "message": {
                "role": "user",
                "content": f"<command-name>/beta</command-name> {SENTINEL}",
            },
        },
        {
            "type": "user",
            "timestamp": DAY,
            "uuid": "u0",
            "message": {"role": "user", "content": "<command-name>/model</command-name>"},
        },
        _assistant("m1", "a1", tool=("toolu_1", "alpha"), usage=(50, 50, 50)),
        _assistant("m1", "a1b", tool=("toolu_1", "alpha"), usage=(50, 50, 50)),  # repeated record
    ]
    for i in range(2, 8):
        records.append(_assistant(f"m{i}", f"a{i}"))  # 6 tokens each (1 + 2 + 3)
    records.append(
        {
            "type": "user",
            "timestamp": DAY,
            "uuid": "u2",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_9",
                        "content": "Unknown skill: ghost",
                    }
                ],
            },
        }
    )
    records.append(  # outside the window, must be ignored
        _assistant("old", "aold", tool=("toolu_old", "alpha"))
        | {"timestamp": "2026-01-01T00:00:00Z"}
    )
    _write(proj / "sess-1.jsonl", records)


def _skills(rep):
    return {r["skill"]: r for r in rep["skills"]}


def test_counts_dedup_exposure_and_unknown(tmp_path):
    _fixture(tmp_path)
    rep = sur.build(tmp_path, "2026-11-01")
    s = _skills(rep)
    assert s["alpha"]["model_calls"] == 1  # repeated record and the old one are not counted
    assert s["alpha"]["sessions_active_with_description_visible"] == 1
    assert s["beta"]["user_slash"] == 1
    assert s["beta"]["sessions_active_with_description_visible"] == 0  # beta is listed name-only
    assert s["beta"]["sessions_listed"] == 1
    assert "model" not in s  # a built-in command is not a skill
    assert "gamma" in rep["never_activated_names"]
    assert rep["unknown_skill_errors"] == {"ghost": 1}
    assert rep["listed_skills"] == 3


def test_post_activation_tokens_exclude_the_calling_request(tmp_path):
    _fixture(tmp_path)
    s = _skills(sur.build(tmp_path, "2026-11-01"))
    # five later distinct requests of 6 tokens each; the call's own 150-token request is skipped
    assert s["alpha"]["post_activation_tokens_mean"] == 30


def test_no_prompt_text_leaks_into_outputs(tmp_path):
    _fixture(tmp_path)
    rep = sur.build(tmp_path, "2026-11-01")
    assert SENTINEL not in json.dumps(rep)
    assert SENTINEL not in sur.render(rep)


def test_window_excludes_old_activations(tmp_path):
    _fixture(tmp_path)
    rep = sur.build(tmp_path, "2026-12-01")
    assert rep["skills_activated"] == 0
    assert rep["total_model_calls"] == 0


def test_parse_listing_separates_described_from_name_only():
    names, described = sur.parse_listing("- a\n- b: text\n- plugin:c: more")
    assert names == {"a", "b", "plugin:c"}
    assert described == {"b", "plugin:c"}


def test_main_writes_markdown_and_json(tmp_path):
    _fixture(tmp_path / "root")
    out = tmp_path / "out"
    rc = sur.main(["--root", str(tmp_path / "root"), "--since", "2026-11-01", "--out", str(out)])
    assert rc == 0
    assert len(list(out.glob("skill-usage-*.json"))) == 1
    assert "| alpha |" in next(out.glob("skill-usage-*.md")).read_text(encoding="utf-8")


def _listing(content, ts=DAY):
    return {
        "type": "attachment",
        "timestamp": ts,
        "attachment": {"type": "skill_listing", "isInitial": True, "content": content},
    }


def _slash(uuid, name, ts=DAY):
    return {
        "type": "user",
        "timestamp": ts,
        "uuid": uuid,
        "message": {"role": "user", "content": f"<command-name>/{name}</command-name>"},
    }


def test_skill_call_is_found_with_default_json_spacing_and_no_prior_slash(tmp_path):
    """Review finding: the prefilter looked for the compact form only, so a listing followed
    directly by a Skill call (json.dumps default spacing) reported zero model activations."""
    proj = tmp_path / "proj"
    proj.mkdir()
    records = [
        _listing("- alpha: does alpha things\n- beta"),
        _assistant("m1", "a1", tool=("toolu_1", "alpha")),
    ]
    (proj / "s.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )  # default separators: '"name": "Skill"'
    s = {r["skill"]: r for r in sur.build(tmp_path, "2026-11-01")["skills"]}
    assert s["alpha"]["model_calls"] == 1
    assert s["alpha"]["sessions_active_with_description_visible"] == 1


def test_bare_slash_and_skill_call_resolve_to_the_listed_plugin_name(tmp_path):
    """Review finding: /alpha was stored under 'alpha' although the listing says
    'plugin:alpha', so the listed skill looked never activated and its exposure was lost."""
    proj = tmp_path / "proj"
    proj.mkdir()
    records = [
        _listing("- plugin:alpha: does alpha things\n- beta"),
        _slash("u1", "alpha"),
        _assistant("m1", "a1", tool=("toolu_1", "alpha")),
    ]
    _write(proj / "s.jsonl", records)
    rep = sur.build(tmp_path, "2026-11-01")
    s = {r["skill"]: r for r in rep["skills"]}
    assert "alpha" not in s
    assert s["plugin:alpha"]["user_slash"] == 1
    assert s["plugin:alpha"]["model_calls"] == 1
    assert s["plugin:alpha"]["sessions_active_with_description_visible"] == 1
    assert "plugin:alpha" not in rep["never_activated_names"]
    assert "beta" in rep["never_activated_names"]


def test_ambiguous_bare_name_is_not_guessed():
    assert sur.resolve_name("alpha", {"p1:alpha", "p2:alpha"}) == "alpha"
    assert sur.resolve_name("alpha", {"plugin:alpha"}) == "plugin:alpha"
    assert sur.resolve_name("plugin:alpha", {"plugin:alpha", "other:alpha"}) == "plugin:alpha"
    assert sur.resolve_name("gamma", set()) == "gamma"


def test_bare_slash_alone_keeps_the_exposure_of_the_listed_plugin_name(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    _write(proj / "s.jsonl", [_listing("- plugin:alpha: does alpha things"), _slash("u1", "alpha")])
    s = {r["skill"]: r for r in sur.build(tmp_path, "2026-11-01")["skills"]}
    assert s["plugin:alpha"]["user_slash"] == 1
    assert s["plugin:alpha"]["sessions_active_with_description_visible"] == 1
