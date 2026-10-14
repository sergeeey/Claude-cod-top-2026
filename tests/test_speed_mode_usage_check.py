"""Tests for scripts/speed_mode_usage_check.py."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.speed_mode_usage_check import extract_turns, report


def _user(text: str) -> str:
    return json.dumps({"type": "user", "message": {"role": "user", "content": text}})


def _assistant(text: str) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
        }
    )


def _tool_result_user(text: str) -> str:
    # WHY: tool_result entries are also type=="user" but content is a LIST,
    # not a string -- must be excluded from real-prompt detection.
    return json.dumps(
        {
            "type": "user",
            "message": {"role": "user", "content": [{"type": "tool_result", "content": text}]},
        }
    )


def test_detects_speed_mode_prefix_case_insensitive(tmp_path: Path) -> None:
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        "\n".join(
            [_user("fast: do X"), _assistant("done"), _user("Just Do: do Y"), _assistant("ok")]
        ),
        encoding="utf-8",
    )
    turns = extract_turns(transcript)
    assert len(turns) == 2
    assert all(t.is_speed_mode for t in turns)


def test_baseline_turn_not_flagged_as_speed_mode(tmp_path: Path) -> None:
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        "\n".join([_user("explain this in detail"), _assistant("a long explanation here")]),
        encoding="utf-8",
    )
    turns = extract_turns(transcript)
    assert len(turns) == 1
    assert turns[0].is_speed_mode is False


def test_tool_result_not_counted_as_user_prompt(tmp_path: Path) -> None:
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        "\n".join(
            [
                _user("do something"),
                _tool_result_user("some tool output, not a real prompt"),
                _assistant("final answer"),
            ]
        ),
        encoding="utf-8",
    )
    turns = extract_turns(transcript)
    assert len(turns) == 1
    assert turns[0].prompt == "do something"


def test_response_chars_concatenates_multiple_assistant_blocks(tmp_path: Path) -> None:
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        "\n".join([_user("q"), _assistant("part1 "), _assistant("part2")]),
        encoding="utf-8",
    )
    turns = extract_turns(transcript)
    assert len(turns) == 1
    assert turns[0].response_chars == len("part1 part2")


def test_report_handles_zero_speed_mode_turns_honestly() -> None:
    from scripts.speed_mode_usage_check import Turn

    turns = [Turn(prompt="normal", response_chars=100, is_speed_mode=False)]
    text = report(turns)
    assert "[UNKNOWN]" in text
    assert "cannot be evaluated" in text


def test_report_computes_reduction_percentage_when_data_exists() -> None:
    from scripts.speed_mode_usage_check import Turn

    turns = [
        Turn(prompt="fast: x", response_chars=50, is_speed_mode=True),
        Turn(prompt="normal", response_chars=100, is_speed_mode=False),
    ]
    text = report(turns)
    assert "Estimated reduction: 50.0%" in text
    assert "[WEAK]" in text
