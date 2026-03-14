#!/usr/bin/env python3
"""PostToolUse hook for Skill|Agent: detect drift from Scope Fence.

WHY: The most dangerous anti-pattern is "interest > priority" — switching
to a new exciting task instead of finishing the current one. This hook
reads the Scope Fence from activeContext.md and warns when the current
action looks like it belongs to the NOT NOW list.

Mechanism:
- Fires on Skill and Agent tool calls (signals of task switching)
- Reads Scope Fence from the nearest activeContext.md
- If the tool/skill name matches a keyword from NOT NOW — warns
- Lightweight: only string matching, no LLM calls, <50ms
"""

import json
import sys
from pathlib import Path


def find_scope_fence_source() -> Path | None:
    """Walk up from CWD looking for Scope Fence in multiple locations.

    Search order (first found wins):
    1. .scope-fence.md          — tool-agnostic, universal
    2. .claude/memory/activeContext.md  — Claude Code
    3. .cursor/memory_bank/activeContext.md — Cursor
    """
    cwd = Path.cwd()
    candidates = [
        ".scope-fence.md",
        str(Path(".claude") / "memory" / "activeContext.md"),
        str(Path(".cursor") / "memory_bank" / "activeContext.md"),
    ]
    for parent in [cwd, *cwd.parents]:
        for rel in candidates:
            full = parent / rel
            if full.exists():
                return full
    return None


def parse_scope_fence(content: str) -> dict[str, str]:
    """Extract Scope Fence fields from activeContext.md.

    Returns dict with keys: goal, boundary, done_when, not_now.
    """
    fence: dict[str, str] = {}
    in_fence = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "## Scope Fence":
            in_fence = True
            continue
        if in_fence and stripped.startswith("## "):
            break
        if not in_fence:
            continue

        if stripped.startswith("Goal:"):
            fence["goal"] = stripped[5:].strip()
        elif stripped.startswith("Boundary:"):
            fence["boundary"] = stripped[9:].strip()
        elif stripped.startswith("Done when:"):
            fence["done_when"] = stripped[10:].strip()
        elif stripped.startswith("NOT NOW:"):
            fence["not_now"] = stripped[8:].strip()

    return fence


def extract_not_now_keywords(not_now: str) -> list[str]:
    """Extract meaningful keywords from NOT NOW field.

    Splits by commas and common delimiters, lowercases, strips filler words.
    """
    if not not_now:
        return []

    # WHY: NOT NOW often contains phrases like "don't optimize config,
    # don't analyze competitors" — we extract the action nouns
    filler = {
        "не",
        "don't",
        "do",
        "not",
        "не делать",
        "avoid",
        "skip",
        "no",
        "нет",
        "без",
        "the",
        "a",
        "an",
        "this",
        "that",
    }

    raw_parts = not_now.replace(";", ",").replace("•", ",").replace("—", ",").split(",")
    keywords = []
    for part in raw_parts:
        words = part.lower().strip().split()
        meaningful = [w for w in words if w not in filler and len(w) > 2]
        keywords.extend(meaningful)

    return keywords


def check_drift(tool_name: str, tool_input: dict, not_now_keywords: list[str]) -> str | None:
    """Check if the current tool call drifts into NOT NOW territory.

    Returns warning message or None.
    """
    if not not_now_keywords:
        return None

    # Build a search string from tool metadata
    search_parts = [tool_name.lower()]

    # Extract skill/agent name from tool_input
    for key in ("skill", "name", "description", "prompt", "subagent_type"):
        val = tool_input.get(key, "")
        if val:
            search_parts.append(str(val).lower())

    search_text = " ".join(search_parts)

    # Check each NOT NOW keyword against the search text
    # WHY: "deployment" should match "deploy", so we check both directions
    # and also stem-like prefix matching (shared prefix >= 4 chars)
    matched = []
    search_words = search_text.split()
    for kw in not_now_keywords:
        if kw in search_text:
            matched.append(kw)
        elif any(kw.startswith(w[:4]) or w.startswith(kw[:4]) for w in search_words if len(w) >= 4):
            matched.append(kw)

    if matched:
        return (
            f"[drift-guard] Possible scope drift detected. "
            f"Scope Fence NOT NOW keywords matched: {', '.join(matched)}. "
            f"Current action: {tool_name}. "
            f"If this is intentional, proceed — but consider whether "
            f"this advances the current Goal or is a side quest."
        )

    return None


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", data)

    # Find and parse Scope Fence
    ctx_path = find_scope_fence_source()
    if ctx_path is None:
        return

    try:
        content = ctx_path.read_text(encoding="utf-8")
    except OSError:
        return

    fence = parse_scope_fence(content)
    not_now = fence.get("not_now", "")

    # Skip if no Scope Fence or NOT NOW is empty/placeholder
    if not not_now or not_now.startswith("{{"):
        return

    keywords = extract_not_now_keywords(not_now)
    warning = check_drift(tool_name, tool_input, keywords)

    if warning:
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": warning,
            }
        }
        print(json.dumps(result))


if __name__ == "__main__":
    main()
