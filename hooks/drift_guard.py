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

from utils import emit_hook_result, find_scope_fence, get_tool_input, parse_scope_fence, parse_stdin


def extract_not_now_keywords(not_now: str) -> list[str]:
    """Extract meaningful keywords from NOT NOW field.

    Splits by commas and common delimiters, lowercases, strips filler words.
    """
    if not not_now:
        return []

    # WHY: NOT NOW often contains phrases like "don't optimize config,
    # don't analyze competitors" — we extract the action nouns
    filler = {
        "not",
        "don't",
        "do",
        "do not",
        "avoid",
        "skip",
        "no",
        "without",
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
    data = parse_stdin()
    if not data:
        return

    tool_name = data.get("tool_name", "")
    tool_input = get_tool_input(data)

    # Find and parse Scope Fence
    ctx_path = find_scope_fence()
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
        emit_hook_result("PostToolUse", warning)


if __name__ == "__main__":
    main()
