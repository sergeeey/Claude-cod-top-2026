"""Tests for scripts/skill_usage_report.py: counting, deduplication, exposure, status, privacy."""

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
EARLY = "2026-11-10T10:00:00.000Z"


def _assistant(mid, uuid, tool=None, usage=(1, 2, 3), ts=DAY):
    content = []
    if tool:
        content.append(
            {"type": "tool_use", "id": tool[0], "name": "Skill", "input": {"skill": tool[1]}}
        )
    return {
        "type": "assistant",
        "timestamp": ts,
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


def _listing(content, ts=DAY):
    return {
        "type": "attachment",
        "timestamp": ts,
        "attachment": {"type": "skill_listing", "isInitial": True, "content": content},
    }


def _slash(uuid, name, ts=DAY, extra=""):
    return {
        "type": "user",
        "timestamp": ts,
        "uuid": uuid,
        "message": {"role": "user", "content": f"<command-name>/{name}</command-name>{extra}"},
    }


def _result(tool_use_id, text, ts=DAY):
    return {
        "type": "user",
        "timestamp": ts,
        "uuid": "r-" + tool_use_id,
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": text}],
        },
    }


def _write(path: Path, records):
    # compact separators, like the real transcripts (the script prefilters on '"name":"Skill"')
    path.write_text(
        "\n".join(json.dumps(r, separators=(",", ":")) for r in records) + "\n", encoding="utf-8"
    )


def _fixture(root: Path):
    proj = root / "proj"
    proj.mkdir(parents=True)
    # older session: its listing still has a name that is gone from the latest listing
    _write(
        proj / "sess-0.jsonl",
        [
            _listing("- alpha: does alpha things\n- oldname", ts=EARLY),
            _slash("u-old", "oldname", ts=EARLY),
        ],
    )
    records = [
        _listing("- alpha: does alpha things\n- beta\n- gamma: gamma description"),
        _slash("u1", "beta", extra=f" {SENTINEL}"),
        _slash("u0", "model"),  # a built-in command, not a skill
        _assistant("m1", "a1", tool=("toolu_1", "alpha"), usage=(50, 50, 50)),
        _assistant("m1", "a1b", tool=("toolu_1", "alpha"), usage=(50, 50, 50)),  # repeated record
    ]
    for i in range(2, 8):
        records.append(_assistant(f"m{i}", f"a{i}"))  # 6 tokens each (1 + 2 + 3)
    records += [
        _assistant("mg", "ag", tool=("toolu_g", "ghost")),
        _result("toolu_g", "Unknown skill: ghost"),  # answers a Skill call: counted as failed
        _result("toolu_bash", "grep output: Unknown skill: quoted"),  # merely quotes the text
        _assistant("old", "aold", tool=("toolu_old", "alpha"), ts="2026-01-01T00:00:00Z"),
    ]
    _write(proj / "sess-1.jsonl", records)
    # a session with no listing record: exposure of its activation is unknown
    _write(proj / "sess-2.jsonl", [_assistant("mz", "az", tool=("toolu_z", "alpha"))])


def _skills(rep):
    return {r["skill"]: r for r in rep["skills"]}


def test_counts_dedup_and_exposure(tmp_path):
    _fixture(tmp_path)
    rep = sur.build(tmp_path, "2026-11-01")
    s = _skills(rep)
    assert s["alpha"]["model_activations"] == 2  # repeated record and the January one excluded
    assert s["alpha"]["activations_description_visible"] == 1
    assert s["alpha"]["activations_exposure_unknown"] == 1
    assert s["beta"]["user_slash"] == 1
    assert s["beta"]["activations_name_only"] == 1
    assert "model" not in s  # a built-in command is not a skill


def test_exposure_columns_add_up_to_activations(tmp_path):
    _fixture(tmp_path)
    for r in sur.build(tmp_path, "2026-11-01")["skills"]:
        expo = (
            r["activations_description_visible"]
            + r["activations_name_only"]
            + r["activations_exposure_unknown"]
        )
        assert expo == r["user_slash"] + r["model_activations"], r["skill"]


def test_unknown_skill_counts_only_failed_skill_calls(tmp_path):
    _fixture(tmp_path)
    rep = sur.build(tmp_path, "2026-11-01")
    s = _skills(rep)
    assert s["ghost"]["failed_unknown"] == 1
    assert s["ghost"]["model_activations"] == 0  # a failed call is not an activation
    assert "quoted" not in s  # text that only quotes the error is not a failed Skill call
    assert rep["model_calls_failed_unknown"] == 1


def test_current_and_historical_names_are_separated(tmp_path):
    _fixture(tmp_path)
    rep = sur.build(tmp_path, "2026-11-01")
    s = _skills(rep)
    assert s["alpha"]["status"] == "current"
    assert s["oldname"]["status"] == "historical"
    assert rep["current_listed_skills"] == 3  # alpha, beta, gamma: from the latest listing only
    assert rep["current_never_activated_names"] == ["gamma"]  # oldname cannot inflate it
    assert rep["historical_names_activated"] == 1
    assert rep["sessions_with_listing"] == 2


def test_next5_tokens_exclude_the_calling_request_and_report_samples(tmp_path):
    _fixture(tmp_path)
    s = _skills(sur.build(tmp_path, "2026-11-01"))
    # five later distinct requests of 6 tokens each; the call's own 150-token request is skipped
    assert s["alpha"]["next5_tokens_mean"] == 30
    assert s["alpha"]["next5_samples"] == 1


def test_no_prompt_text_leaks_into_outputs(tmp_path):
    _fixture(tmp_path)
    rep = sur.build(tmp_path, "2026-11-01")
    assert SENTINEL not in json.dumps(rep)
    assert SENTINEL not in sur.render(rep)


def test_window_excludes_old_activations(tmp_path):
    _fixture(tmp_path)
    rep = sur.build(tmp_path, "2026-12-01")
    assert rep["activations_model"] == 0
    assert rep["activations_user_slash"] == 0
    assert rep["current_listed_skills"] == 0


def test_parse_listing_separates_described_from_name_only():
    names, described = sur.parse_listing("- a\n- b: text\n- plugin:c: more\n- plugin:d")
    assert names == {"a", "b", "plugin:c", "plugin:d"}
    assert described == {"b", "plugin:c"}


def test_main_writes_markdown_and_json(tmp_path):
    _fixture(tmp_path / "root")
    out = tmp_path / "out"
    rc = sur.main(["--root", str(tmp_path / "root"), "--since", "2026-11-01", "--out", str(out)])
    assert rc == 0
    assert len(list(out.glob("skill-usage-*.json"))) == 1
    text = next(out.glob("skill-usage-*.md")).read_text(encoding="utf-8")
    assert "| alpha |" in text and "Exposure unknown" in text
