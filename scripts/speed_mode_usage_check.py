"""Measure whether Speed Mode (`fast:`/`just do:` prefix, CLAUDE.md WORKFLOW
section) actually produces shorter responses -- instead of assuming it does.

WHY this exists (2026-09-06): a real external insight (JuliusBrussee/caveman,
mined via graphify) made a 65%-token-savings claim for its own terse-language
technique, and its own recorded recommendation was "measure the savings, not
belief in it" (`caveman-stats.js`, priority 3, never built here). This repo
doesn't use Caveman's terse-speech style, but it DOES have its own untested
token-saving claim -- Speed Mode -- and applies the same discipline to it:
measure a real Claude Code session transcript instead of trusting the claim.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SPEED_MODE_PATTERN = re.compile(r"^\s*(fast:|just do:)", re.IGNORECASE)


@dataclass
class Turn:
    prompt: str
    response_chars: int
    is_speed_mode: bool


def _extract_user_prompt(obj: dict) -> str | None:
    """Real user-typed turns have message.content as a plain string.
    Tool results (also role=="user" in this transcript format) carry
    content as a list -- excluded here so we don't count those as prompts.
    """
    if obj.get("type") != "user":
        return None
    content = obj.get("message", {}).get("content")
    if isinstance(content, str) and content.strip():
        return content
    return None


def _extract_assistant_text(obj: dict) -> str:
    if obj.get("type") != "assistant":
        return ""
    content = obj.get("message", {}).get("content", [])
    if not isinstance(content, list):
        return ""
    parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    return "".join(parts)


def extract_turns(transcript_path: Path) -> list[Turn]:
    """Pairs each real user prompt with the concatenated assistant text
    that follows it, up to the next real user prompt.
    """
    lines = transcript_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    parsed = []
    for line in lines:
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    turns: list[Turn] = []
    current_prompt: str | None = None
    current_response = ""

    def flush() -> None:
        nonlocal current_prompt, current_response
        if current_prompt is not None:
            turns.append(
                Turn(
                    prompt=current_prompt,
                    response_chars=len(current_response),
                    is_speed_mode=bool(SPEED_MODE_PATTERN.match(current_prompt)),
                )
            )
        current_prompt = None
        current_response = ""

    for obj in parsed:
        prompt = _extract_user_prompt(obj)
        if prompt is not None:
            flush()
            current_prompt = prompt
            continue
        if current_prompt is not None:
            current_response += _extract_assistant_text(obj)
    flush()
    return turns


def report(turns: list[Turn]) -> str:
    speed = [t for t in turns if t.is_speed_mode]
    baseline = [t for t in turns if not t.is_speed_mode]

    lines = [f"Total real user turns found: {len(turns)}"]
    lines.append(f"Speed Mode turns (fast:/just do:): {len(speed)}")
    lines.append(f"Baseline turns: {len(baseline)}")

    if not speed:
        lines.append(
            "\n[UNKNOWN] Zero Speed Mode turns found in this transcript -- the "
            "65%-style savings claim pattern (assert a number, never check it) "
            "cannot be evaluated here. This is itself the honest finding: "
            "Speed Mode's claimed benefit has apparently never been used in "
            "this session, so it has never been empirically checked either."
        )
        return "\n".join(lines)

    avg_speed = sum(t.response_chars for t in speed) / len(speed)
    avg_baseline = sum(t.response_chars for t in baseline) / len(baseline) if baseline else 0.0
    lines.append(f"Avg response chars — Speed Mode: {avg_speed:.0f}")
    lines.append(f"Avg response chars — Baseline:   {avg_baseline:.0f}")
    if avg_baseline:
        pct = (1 - avg_speed / avg_baseline) * 100
        lines.append(f"Estimated reduction: {pct:.1f}%")
    lines.append(
        f"\n[WEAK] n={len(speed)} Speed Mode sample -- too small for a "
        "confident claim either way; re-run on more sessions before quoting "
        "a percentage anywhere."
    )
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python speed_mode_usage_check.py <transcript.jsonl>")
        return 1
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"[SKIPPED] transcript not found: {path}")
        return 0
    turns = extract_turns(path)
    print(report(turns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
