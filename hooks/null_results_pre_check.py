#!/usr/bin/env python3
"""UserPromptSubmit hook: check if a new experiment/hypothesis was already killed.

WHY: Researchers (and LLMs) re-propose ideas already falsified in null_results/.
Catching this at prompt-time costs ~10ms vs. re-running a dead experiment.

Algorithm:
1. Extract claim-relevant keywords from user prompt.
2. Search null_results/INDEX.md for slug overlap (≥2 shared tokens).
3. Emit additionalContext warning with matching entry for Claude to see.
"""

import json
import os
import re
import sys
from pathlib import Path

# Keywords that indicate the user is proposing a new experiment/hypothesis.
# Must appear in the prompt for the hook to engage — avoids noise on every message.
TRIGGER_KEYWORDS = {
    "experiment",
    "hypothesis",
    "гипотеза",
    "claim",
    "хочу проверить",
    "попробую",
    "тест",
    "проверим",
    "давай проверим",
    "new claim",
    "i want to test",
    "let me try",
    "what if",
    "null_results",
}

# Tokens shorter than this are too generic to match on (e.g., "a", "to", "is").
MIN_TOKEN_LEN = 4

# How many tokens must overlap between prompt and null_results slug.
MATCH_THRESHOLD = 2


def _is_triggered(prompt: str) -> bool:
    lower = prompt.lower()
    return any(kw in lower for kw in TRIGGER_KEYWORDS)


def _tokenize(text: str) -> set[str]:
    """Split slug or prompt into lowercase alpha tokens of meaningful length."""
    raw = re.findall(r"[a-zа-яё]+", text.lower())
    return {t for t in raw if len(t) >= MIN_TOKEN_LEN}


def _find_null_results_index() -> Path | None:
    """Search upward from CWD for null_results/INDEX.md."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / "null_results" / "INDEX.md"
        if candidate.exists():
            return candidate
    return None


def _parse_null_results(index_path: Path) -> list[dict]:
    """Parse null_results/INDEX.md into list of {id, date, slug, verdict, why}."""
    entries: list[dict] = []
    try:
        content = index_path.read_text(encoding="utf-8")
    except OSError:
        return entries

    for line in content.splitlines():
        # Table rows: | id | date | slug | verdict | why |
        if not line.startswith("|") or "---" in line or "Slug" in line:
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 4:  # noqa: PLR2004
            continue
        entries.append(
            {
                "id": parts[0],
                "date": parts[1] if len(parts) > 1 else "",
                "slug": parts[2] if len(parts) > 2 else "",
                "verdict": parts[3] if len(parts) > 3 else "",
                "why": parts[4] if len(parts) > 4 else "",
            }
        )
    return entries


def _find_matches(prompt: str, entries: list[dict]) -> list[dict]:
    """Return entries whose slug overlaps ≥ MATCH_THRESHOLD tokens with prompt."""
    prompt_tokens = _tokenize(prompt)
    matches = []
    for entry in entries:
        slug_tokens = _tokenize(entry["slug"])
        overlap = prompt_tokens & slug_tokens
        if len(overlap) >= MATCH_THRESHOLD:
            entry["_overlap"] = sorted(overlap)
            matches.append(entry)
    return matches


def main() -> None:
    # WHY: recursion guard — this hook reads filesystem; if Claude invokes it
    # via subagent, we'd loop. Guard exits silently.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    prompt: str = data.get("prompt", "")
    if not isinstance(prompt, str) or not prompt.strip():
        sys.exit(0)

    if not _is_triggered(prompt):
        sys.exit(0)

    index_path = _find_null_results_index()
    if index_path is None:
        sys.exit(0)

    entries = _parse_null_results(index_path)
    if not entries:
        sys.exit(0)

    matches = _find_matches(prompt, entries)
    if not matches:
        sys.exit(0)

    # Build warning message for Claude context
    lines = ["[null-results-pre-check] ⚠️  POSSIBLE DUPLICATE — already in null_results/:"]
    for m in matches:
        lines.append(
            f"  • [{m['id']}] {m['slug']} ({m['verdict']}) — {m['why']}"
            f" [matched: {', '.join(m.get('_overlap', []))}]"
        )
    lines.append(
        "  → Read null_results/INDEX.md + prior decision.md BEFORE re-running."
        " Bypass with: 'I know this was killed, new condition: ...'"
    )

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": "\n".join(lines),
                }
            }
        )
    )


if __name__ == "__main__":
    main()
