"""Tests for scripts/session_outcome_ledger.py. No network: `gh` is replaced by fixed functions."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

import session_outcome_ledger as sol  # noqa: E402

REPO = "owner/repo"


def _write_session(path: Path, pr_number: int | None, prompts: str = "do the task") -> None:
    lines = [
        {
            "type": "user",
            "sessionId": "s1",
            "cwd": "D:/work",
            "gitBranch": "feat/x",
            "timestamp": "2026-11-01T10:00:00Z",
            "message": {"content": prompts},
        },
        {
            "type": "attachment",
            "sessionId": "s1",
            "timestamp": "2026-11-01T10:00:01Z",
            "attachment": {"text": "[routing-floor] RESEARCH tier"},
        },
        {
            "type": "assistant",
            "sessionId": "s1",
            "timestamp": "2026-11-01T10:00:02Z",
            "requestId": "r1",
            "message": {
                "usage": {
                    "input_tokens": 100,
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
                "sessionId": "s1",
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


def _fake_states(numbers):
    return lambda repo: {
        n: {
            "state": "MERGED",
            "createdAt": "2026-11-01T00:00:00Z",
            "mergedAt": "2026-11-02T00:00:00Z",
        }
        for n in numbers
    }


def _fake_detail(repo, number):
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
    assert "do the task" not in json.dumps(row)  # prompt text is never stored


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

    counts1 = sol.update(
        projects, ledger, REPO, 30, pr_states=_fake_states([7])(REPO), pr_detail=_fake_detail
    )
    assert counts1["parsed"] == 1
    counts2 = sol.update(
        projects, ledger, REPO, 30, pr_states=_fake_states([7])(REPO), pr_detail=_fake_detail
    )
    assert counts2["parsed"] == 0  # unchanged file is not re-parsed

    stored = json.loads(ledger.read_text(encoding="utf-8"))
    assert stored["prs"]["7"]["state"] == "MERGED"
    assert stored["prs"]["7"]["commits"] == 3

    text = sol.report(ledger, min_n=30)
    assert "| 1 | 1 | 0 | 0 | 3 | 120 |" in text  # one PR, merged, 3 commits, 120 lines
    assert "| RESEARCH |" in text
    assert "yes: no conclusion" in text  # n=1 is below min_n=30
    assert "Descriptive only" in text


def test_report_empty_ledger_has_no_rows(tmp_path):
    ledger = tmp_path / "none.json"
    text = sol.report(ledger, min_n=30)
    assert "Sessions that created PRs: 0" in text
