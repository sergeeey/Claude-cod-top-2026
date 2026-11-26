"""Tests for scripts/session_outcome_ledger.py. No network: `gh` is replaced by fakes."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

import session_outcome_ledger as sol  # noqa: E402

REPO = "owner/repo"


def _write_session(
    path: Path, pr_number: int | None, prompts: str = "do the task", req="r1", sid="s1", tokens=100
) -> None:
    lines = [
        {
            "type": "user",
            "sessionId": sid,
            "cwd": "D:/work",
            "gitBranch": "feat/x",
            "timestamp": "2026-11-01T10:00:00Z",
            "message": {"content": prompts},
        },
        {
            "type": "attachment",
            "sessionId": sid,
            "timestamp": "2026-11-01T10:00:01Z",
            "attachment": {"text": "[routing-floor] RESEARCH tier"},
        },
        {
            "type": "assistant",
            "sessionId": sid,
            "timestamp": "2026-11-01T10:00:02Z",
            "requestId": req,
            "message": {
                "usage": {
                    "input_tokens": tokens,
                    "output_tokens": 50,
                    "cache_creation_input_tokens": 10,
                    "cache_read_input_tokens": 999,
                },
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "Skill",
                        "input": {"skill": "ru-writing-standard"},
                    },
                    {
                        "type": "tool_use",
                        "id": "t2",
                        "name": "Agent",
                        "input": {"subagent_type": "reviewer"},
                    },
                    {
                        "type": "tool_use",
                        "id": "t3",
                        "name": "Bash",
                        "input": {"command": "gh pr create --title x"},
                    },
                ],
            },
        },
    ]
    if pr_number is not None:
        lines.append(
            {
                "type": "user",
                "sessionId": sid,
                "timestamp": "2026-11-01T10:00:03Z",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "t3",
                            "content": f"https://github.com/{REPO}/pull/{pr_number}",
                        }
                    ]
                },
            }
        )
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")


def _states(number, state="MERGED"):
    return {
        number: {
            "state": state,
            "createdAt": "2026-11-01T00:00:00Z",
            "mergedAt": "2026-11-02T00:00:00Z" if state == "MERGED" else None,
        }
    }


def _const_detail(repo, number):
    return {"commits": 3, "reviews": 1, "changed_lines": 120}


def test_parse_counts_names_and_tokens_without_prompt_text(tmp_path):
    f = tmp_path / "proj" / "s1.jsonl"
    f.parent.mkdir()
    _write_session(f, pr_number=7)
    row = sol.row_from_feats(sol.parse_transcript(str(f), REPO))
    assert row["skill_calls"] == {"ru-writing-standard": 1}
    assert row["agent_types"] == {"reviewer": 1}
    assert row["routing_verdicts"] == {"RESEARCH": 1}
    assert row["user_prompts"] == 1
    assert row["tokens_input"] == 100 and row["tokens_output"] == 50
    assert row["tokens_cache_read"] == 999
    assert row["pr_created"] == [7]


def test_nothing_private_is_stored(tmp_path):
    f = tmp_path / "proj" / "s1.jsonl"
    f.parent.mkdir()
    _write_session(f, pr_number=7, prompts="secret-looking prompt text")
    row = sol.row_from_feats(sol.parse_transcript(str(f), REPO))
    text = json.dumps(row)
    assert "secret-looking prompt text" not in text  # prompt text
    assert "gh pr create" not in text  # tool arguments
    assert "cwd" not in row and "branch" not in row  # working directory and git branch


def test_pr_is_credited_only_when_session_created_it(tmp_path):
    f = tmp_path / "proj" / "s1.jsonl"
    f.parent.mkdir()
    # the URL appears in a tool result of a different tool call: not a creation
    lines = [
        {
            "type": "assistant",
            "sessionId": "s2",
            "requestId": "r1",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tx",
                        "name": "Bash",
                        "input": {"command": "gh pr list"},
                    }
                ]
            },
        },
        {
            "type": "user",
            "sessionId": "s2",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tx",
                        "content": f"https://github.com/{REPO}/pull/99",
                    }
                ]
            },
        },
    ]
    f.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    row = sol.row_from_feats(sol.parse_transcript(str(f), REPO))
    assert row["pr_created"] == []


def test_update_is_incremental_and_report_lists_outcome(tmp_path):
    projects = tmp_path / "projects"
    (projects / "proj").mkdir(parents=True)
    _write_session(projects / "proj" / "s1.jsonl", pr_number=7)
    ledger = tmp_path / "ledger.json"
    c1 = sol.update(projects, ledger, REPO, 30, pr_states=_states(7), pr_detail=_const_detail)
    assert c1["parsed"] == 1
    c2 = sol.update(projects, ledger, REPO, 30, pr_states=_states(7), pr_detail=_const_detail)
    assert c2["parsed"] == 0  # unchanged file is not re-parsed
    stored = json.loads(ledger.read_text(encoding="utf-8"))
    assert stored["prs"]["7"]["state"] == "MERGED"
    assert stored["prs"]["7"]["commits"] == 3
    text = sol.report(ledger, REPO, min_n=30)
    assert "| 1 | 1 | 0 | 0 | 3 | 120 |" in text  # one PR, merged, 3 commits, 120 lines
    assert "| RESEARCH |" in text
    assert "yes: no conclusion" in text  # n=1 is below min_n=30
    assert "Descriptive only" in text
    assert "integration status, not a measured result" in text


def test_pr_state_change_refetches_detail(tmp_path):
    projects = tmp_path / "projects"
    (projects / "proj").mkdir(parents=True)
    _write_session(projects / "proj" / "s1.jsonl", pr_number=7)
    ledger = tmp_path / "ledger.json"
    calls = []

    def detail(repo, number):
        calls.append(number)
        return {"commits": 2 if len(calls) == 1 else 5, "reviews": 0, "changed_lines": 10}

    sol.update(projects, ledger, REPO, 30, pr_states=_states(7, "OPEN"), pr_detail=detail)
    sol.update(projects, ledger, REPO, 30, pr_states=_states(7, "MERGED"), pr_detail=detail)
    stored = json.loads(ledger.read_text(encoding="utf-8"))["prs"]["7"]
    assert stored["state"] == "MERGED"
    assert stored["commits"] == 5  # re-read after the PR changed state
    assert stored["detail_state"] == "MERGED"
    assert len(calls) == 2


def test_second_run_on_settled_pr_makes_no_detail_calls(tmp_path):
    projects = tmp_path / "projects"
    (projects / "proj").mkdir(parents=True)
    _write_session(projects / "proj" / "s1.jsonl", pr_number=7)
    ledger = tmp_path / "ledger.json"
    calls = []

    def detail(repo, number):
        calls.append(number)
        return {"commits": 3, "reviews": 0, "changed_lines": 10}

    sol.update(projects, ledger, REPO, 30, pr_states=_states(7), pr_detail=detail)
    before = len(calls)
    sol.update(projects, ledger, REPO, 30, pr_states=_states(7), pr_detail=detail)
    assert len(calls) == before  # merged and already read: nothing refetched


def test_subagent_file_of_same_session_is_aggregated_not_double_counted(tmp_path):
    projects = tmp_path / "projects"
    (projects / "proj" / "sub").mkdir(parents=True)
    _write_session(projects / "proj" / "s1.jsonl", pr_number=7, req="r1", tokens=100)
    _write_session(
        projects / "proj" / "sub" / "agent.jsonl",
        pr_number=None,
        req="r2",
        tokens=200,
        prompts="subagent task",
    )
    ledger = tmp_path / "ledger.json"
    counts = sol.update(projects, ledger, REPO, 30, pr_states=_states(7), pr_detail=_const_detail)
    assert counts["files"] == 2 and counts["sessions"] == 1
    text = sol.report(ledger, REPO, min_n=30)
    assert "| s1 | 2026-11-01 | 2 |" in text  # two files, one session id
    assert "PRs" in text and "| 1 | 1 | 0 | 0 | 3 | 120 |" in text  # PR counted once


def test_old_schema_ledger_is_rebuilt(tmp_path):
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({"schema": 2, "repo": REPO, "sessions": {"x": {"cwd": "D:/secret"}}, "prs": {}}),
        encoding="utf-8",
    )
    data = sol.load_ledger(ledger, REPO)
    assert data["sessions"] == {} and data["schema"] == sol.SCHEMA


def test_auth_auto_retries_without_token_on_401(monkeypatch):
    seen = []

    def fake_run(argv, capture_output, text, timeout, env):
        seen.append("GH_TOKEN" in env)
        if "GH_TOKEN" in env:
            return subprocess.CompletedProcess(argv, 1, "", "HTTP 401: Bad credentials")
        return subprocess.CompletedProcess(argv, 0, "[]", "")

    monkeypatch.setenv("GH_TOKEN", "stale")
    monkeypatch.setattr(sol.subprocess, "run", fake_run)
    sol._STATS.clear()
    assert sol.fetch_pr_states(REPO, auth="auto") == {}
    assert seen == [True, False]  # first with the env token, then the CLI login
    assert sol._STATS["auth_fallback"] == 1


def test_auth_env_does_not_fall_back(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, env):
        return subprocess.CompletedProcess(argv, 1, "", "HTTP 401: Bad credentials")

    monkeypatch.setenv("GH_TOKEN", "stale")
    monkeypatch.setattr(sol.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        sol.fetch_pr_states(REPO, auth="env")


def test_auth_cli_always_drops_token(monkeypatch):
    seen = []

    def fake_run(argv, capture_output, text, timeout, env):
        seen.append("GH_TOKEN" in env)
        return subprocess.CompletedProcess(argv, 0, "[]", "")

    monkeypatch.setenv("GH_TOKEN", "present")
    monkeypatch.setattr(sol.subprocess, "run", fake_run)
    sol.fetch_pr_states(REPO, auth="cli")
    assert seen == [False]


def test_spearman_is_robust_to_one_large_point():
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [1.0, 2.0, 3.0, 4.0, 500.0]
    assert sol._spearman(x, y) == pytest.approx(1.0)
    assert sol._pearson(x, y) < 1.0


def test_report_empty_ledger_has_no_rows(tmp_path):
    ledger = tmp_path / "none.json"
    text = sol.report(ledger, REPO, min_n=30)
    assert "Session ids that created PRs: 0" in text


def test_project_folder_name_is_not_stored(tmp_path):
    folder = tmp_path / "C--Users-private-person-work"
    folder.mkdir()
    _write_session(folder / "s1.jsonl", pr_number=7)
    projects = tmp_path
    ledger = tmp_path / "ledger.json"
    sol.update(projects, ledger, REPO, 30, pr_states=_states(7), pr_detail=_const_detail)
    text = ledger.read_text(encoding="utf-8")
    assert "private-person" not in text  # neither the folder name nor the path is stored
    assert "C--Users" not in text


def test_malformed_lines_do_not_stop_the_update(tmp_path):
    projects = tmp_path / "projects"
    (projects / "proj").mkdir(parents=True)
    bad = [
        "[1, 2, 3]",
        '"just a string"',
        '{"type": "assistant", "message": "not an object"}',
        '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Skill", '
        '"input": "not an object"}]}}',
        "[" * 5000,  # deep nesting
    ]
    good = _session_lines_for_test()
    (projects / "proj" / "s1.jsonl").write_text(
        "\n".join(bad + [json.dumps(x) for x in good]) + "\n", encoding="utf-8"
    )
    ledger = tmp_path / "ledger.json"
    counts = sol.update(projects, ledger, REPO, 30, pr_states={}, pr_detail=_const_detail)
    assert counts["file_error"] == 0
    stored = json.loads(ledger.read_text(encoding="utf-8"))
    (row,) = stored["sessions"].values()
    assert row["skill_calls"] == {
        "other": 1,
        "ru-writing-standard": 1,
    }  # bad input counted as "other"


def test_skill_names_are_sanitised(tmp_path):
    f = tmp_path / "proj" / "s1.jsonl"
    f.parent.mkdir()
    lines = [
        {
            "type": "assistant",
            "sessionId": "s1",
            "requestId": "r1",
            "message": {
                "usage": {"input_tokens": 1},
                "content": [
                    {"type": "tool_use", "id": "a", "name": "Skill", "input": {"skill": "x" * 100}},
                    {
                        "type": "tool_use",
                        "id": "b",
                        "name": "Skill",
                        "input": {"skill": "has spaces and !"},
                    },
                    {
                        "type": "tool_use",
                        "id": "c",
                        "name": "Skill",
                        "input": {"skill": "ok-name:v1"},
                    },
                ],
            },
        },
    ]
    f.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    row = sol.row_from_feats(sol.parse_transcript(str(f), REPO))
    assert row["skill_calls"] == {"other": 2, "ok-name:v1": 1}


def test_repo_name_with_prefix_is_not_counted(tmp_path):
    f = tmp_path / "proj" / "s1.jsonl"
    f.parent.mkdir()
    lines = [
        {
            "type": "assistant",
            "sessionId": "s1",
            "requestId": "r1",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t9",
                        "name": "Bash",
                        "input": {"command": "gh pr create"},
                    }
                ]
            },
        },
        {
            "type": "user",
            "sessionId": "s1",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t9",
                        "content": f"https://github.com/x{REPO}/pull/5",
                    }
                ]
            },
        },
    ]
    f.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    row = sol.row_from_feats(sol.parse_transcript(str(f), REPO))
    assert row["pr_created"] == []


def _session_lines_for_test():
    return [
        {
            "type": "assistant",
            "sessionId": "s1",
            "requestId": "r1",
            "message": {
                "usage": {"input_tokens": 5},
                "content": [
                    {
                        "type": "tool_use",
                        "id": "k1",
                        "name": "Skill",
                        "input": {"skill": "ru-writing-standard"},
                    }
                ],
            },
        },
    ]


def test_ledger_refuses_another_repository(tmp_path):
    projects = tmp_path / "projects"
    (projects / "proj").mkdir(parents=True)
    _write_session(projects / "proj" / "s1.jsonl", pr_number=7)
    ledger = tmp_path / "ledger.json"
    sol.update(projects, ledger, REPO, 30, pr_states=_states(7), pr_detail=_const_detail)
    with pytest.raises(ValueError):
        sol.update(projects, ledger, "other/repo", 30, pr_states={}, pr_detail=_const_detail)


def test_default_ledger_path_is_per_repository():
    assert sol.default_ledger_path("a/b") != sol.default_ledger_path("c/d")
    assert "a__b" in sol.default_ledger_path("a/b").name


def test_pr_missing_from_bounded_list_keeps_its_known_state(tmp_path):
    projects = tmp_path / "projects"
    (projects / "proj").mkdir(parents=True)
    _write_session(projects / "proj" / "s1.jsonl", pr_number=7)
    ledger = tmp_path / "ledger.json"
    sol.update(projects, ledger, REPO, 30, pr_states=_states(7), pr_detail=_const_detail)
    # the next bounded list does not contain PR 7 at all
    sol.update(projects, ledger, REPO, 30, pr_states={}, pr_detail=_const_detail)
    stored = json.loads(ledger.read_text(encoding="utf-8"))["prs"]["7"]
    assert stored["state"] == "MERGED"  # not overwritten with UNKNOWN


def test_new_pr_outside_bounded_list_gets_state_from_its_own_lookup(tmp_path):
    projects = tmp_path / "projects"
    (projects / "proj").mkdir(parents=True)
    _write_session(projects / "proj" / "s1.jsonl", pr_number=7)
    ledger = tmp_path / "ledger.json"

    def detail(repo, number):
        return {"commits": 1, "reviews": 0, "changed_lines": 5, "state": "CLOSED"}

    sol.update(projects, ledger, REPO, 30, pr_states={}, pr_detail=detail)
    stored = json.loads(ledger.read_text(encoding="utf-8"))["prs"]["7"]
    assert stored["state"] == "CLOSED"


def test_repo_name_must_be_owner_slash_name():
    for bad in ("a\\..\\..\\settings", "../x", "x:y", "a/b/c", "", "a/..", "noslash"):
        with pytest.raises(ValueError):
            sol.check_repo(bad)
    assert sol.check_repo("owner/repo.name") == "owner/repo.name"


def test_default_path_cannot_leave_the_state_folder():
    with pytest.raises(ValueError):
        sol.default_ledger_path("a/..")


def test_other_repository_ledger_is_refused_even_with_old_schema(tmp_path):
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"schema": 2, "sessions": {}, "prs": {}}), encoding="utf-8")
    with pytest.raises(ValueError):
        sol.load_ledger(ledger, REPO)  # no repo field: not ours, not overwritten


def test_closed_pr_is_reread_and_a_reopened_merge_is_followed(tmp_path):
    projects = tmp_path / "projects"
    (projects / "proj").mkdir(parents=True)
    _write_session(projects / "proj" / "s1.jsonl", pr_number=7)
    ledger = tmp_path / "ledger.json"
    sol.update(
        projects,
        ledger,
        REPO,
        30,
        pr_states=_states(7, "CLOSED"),
        pr_detail=lambda r, n: {"commits": 2, "reviews": 0, "changed_lines": 4, "state": "CLOSED"},
    )
    # later the PR is reopened and merged, and it is outside the bounded list
    sol.update(
        projects,
        ledger,
        REPO,
        30,
        pr_states={},
        pr_detail=lambda r, n: {"commits": 3, "reviews": 0, "changed_lines": 9, "state": "MERGED"},
    )
    stored = json.loads(ledger.read_text(encoding="utf-8"))["prs"]["7"]
    assert stored["state"] == "MERGED" and stored["commits"] == 3


def test_unknown_state_string_is_not_stored(tmp_path):
    projects = tmp_path / "projects"
    (projects / "proj").mkdir(parents=True)
    _write_session(projects / "proj" / "s1.jsonl", pr_number=7)
    ledger = tmp_path / "ledger.json"
    sol.update(
        projects,
        ledger,
        REPO,
        30,
        pr_states={},
        pr_detail=lambda r, n: {
            "commits": 1,
            "reviews": 0,
            "changed_lines": 1,
            "state": "weird value",
        },
    )
    stored = json.loads(ledger.read_text(encoding="utf-8"))["prs"]["7"]
    assert "state" not in stored  # not one of OPEN, MERGED, CLOSED: ignored


def test_mcp_server_names_are_sanitised_and_no_project_field(tmp_path):
    f = tmp_path / "proj" / "s1.jsonl"
    f.parent.mkdir()
    lines = [
        {
            "type": "assistant",
            "sessionId": "s1",
            "requestId": "r1",
            "message": {
                "usage": {"input_tokens": 1},
                "content": [
                    {"type": "tool_use", "id": "m1", "name": "mcp__my bad srv__tool", "input": {}},
                ],
            },
        },
    ]
    f.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    row = sol.row_from_feats(sol.parse_transcript(str(f), REPO))
    assert row["mcp_servers"] == {"other": 1}
    assert "project" not in row
