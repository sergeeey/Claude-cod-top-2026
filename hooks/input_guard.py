#!/usr/bin/env python3
"""PreToolUse hook: detect prompt injection in MCP server responses and tool inputs.

Reads JSON from stdin (Claude Code hook protocol), scans all string values in
tool_input recursively for known injection patterns, and blocks HIGH-threat payloads.

Threat levels:
- NONE  -> allow silently
- LOW   -> allow, log warning to stderr
- HIGH  -> block with decision JSON to stdout
"""

import json
import re
import sys
from typing import Any

# WHY: categories are separated by threat semantics, not syntax --
# this allows more precise block reason messages to the user.
PATTERNS: dict[str, re.Pattern[str]] = {
    "system_override": re.compile(
        r"ignore previous|disregard instructions|you are now|new instructions:",
        re.IGNORECASE,
    ),
    "jailbreak": re.compile(
        r"DAN mode|jailbreak|bypass safety|pretend you",
        re.IGNORECASE,
    ),
    "encoding_attack": re.compile(
        r"\x00|[\u200b\u200c\u200d\ufeff]",
    ),
    "data_exfil": re.compile(
        r"send to http|curl |wget |fetch\(",
        re.IGNORECASE,
    ),
    "role_injection": re.compile(
        r"```system|\[SYSTEM\]|<system>|Human:|Assistant:",
        re.IGNORECASE,
    ),
    "credential_harvest": re.compile(
        r"what is your api key|show me your token|print your password",
        re.IGNORECASE,
    ),
    "command_injection": re.compile(
        r"; rm |\| cat /etc|&& curl|\$\(|`[^`]+`",
    ),
    # WHY: social engineering attacks wrap harmful instructions in polite
    # context ("as your developer...", "for debugging purposes...") to bypass
    # regex-only guards. These phrases have no legitimate use in tool inputs.
    "social_engineering": re.compile(
        r"please ignore (all |the )?(previous|prior|above|earlier) (instructions?|rules?|constraints?)|"
        r"kindly disregard|forget (all |your )?(previous |prior )?instructions|"
        r"as your (developer|admin|creator|owner|operator)|"
        r"for (debug(ging)?|test(ing)?|demo) purposes[,.]? (ignore|bypass|skip|disable)|"
        r"your new (role|persona|instructions?|directives?|task) (is|are)|"
        r"from now on (you (are|will|must|should)|ignore)|"
        r"starting (now|immediately)[,.]? you (are|will|must)|"
        r"(acting|pretend(ing)?|roleplay(ing)?) as .{0,30}(without|ignoring|bypass)",
        re.IGNORECASE,
    ),
}

# WHY: these categories immediately escalate to HIGH even on a single match --
# they carry direct operational risk (code execution, encoding bypass).
HIGH_PRIORITY_CATEGORIES = {"encoding_attack", "command_injection"}

# Null bytes and zero-width characters -- the only things safe to strip automatically
SANITIZE_PATTERN = re.compile(r"\x00|[\u200b\u200c\u200d\ufeff]")


def collect_strings(value: Any) -> list[str]:
    """Recursively collect all string values from an arbitrary data structure."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        results: list[str] = []
        for v in value.values():
            results.extend(collect_strings(v))
        return results
    if isinstance(value, list):
        results = []
        for item in value:
            results.extend(collect_strings(item))
        return results
    return []


def sanitize(value: Any) -> Any:
    """Recursively remove null bytes and zero-width characters from strings."""
    if isinstance(value, str):
        return SANITIZE_PATTERN.sub("", value)
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def scan(strings: list[str]) -> dict[str, int]:
    """Return dict {category: match_count} for all strings."""
    hits: dict[str, int] = {}
    for text in strings:
        for category, pattern in PATTERNS.items():
            count = len(pattern.findall(text))
            if count:
                hits[category] = hits.get(category, 0) + count
    return hits


def main() -> None:
    # WHY: intentionally NOT using parse_stdin() from utils -- different semantics.
    # parse_stdin() returns {} on failure (fail-silent), but this security hook
    # must sys.exit(0) on parse failure (fail-open: allow the call to proceed).
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name: str = data.get("tool_name", "")

    # WHY: only check MCP tools -- they accept external data;
    # built-in Claude tools (Read, Bash, etc.) are trusted by definition.
    if not tool_name.startswith("mcp__"):
        sys.exit(0)

    tool_input: Any = data.get("tool_input", {})
    strings = collect_strings(tool_input)
    hits = scan(strings)

    if not hits:
        # NONE -- allow, return sanitized input
        clean_input = sanitize(tool_input)
        print(json.dumps({"tool_input": clean_input}))
        sys.exit(0)

    categories = list(hits.keys())
    total_matches = sum(hits.values())
    is_high = total_matches >= 2 or any(c in HIGH_PRIORITY_CATEGORIES for c in categories)

    if is_high:
        reason = f"Prompt injection detected: {', '.join(categories)}"
        print(json.dumps({"decision": "block", "reason": reason}))
        sys.exit(0)

    # LOW -- allow with warning, sanitize output
    print(
        f"[input-guard] LOW threat in {tool_name}: {categories} ({total_matches} match). Allowed.",
        file=sys.stderr,
    )
    clean_input = sanitize(tool_input)
    print(json.dumps({"tool_input": clean_input}))
    sys.exit(0)


if __name__ == "__main__":
    from utils import hook_main

    hook_main(main)
