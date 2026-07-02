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
import unicodedata
from typing import Any

from utils import emit_permission_decision, log_hook_trigger

HOOK_NAME = "input_guard"

# WHY: trusted MCP tools whose inputs are library docs, not user-controlled content.
# Context7 returns documentation from known package registries — not an injection vector.
# Allowlisting avoids 87+ false-positives/12d from backtick-heavy code examples in docs.
TRUSTED_MCP_PREFIXES: frozenset[str] = frozenset(
    {
        "mcp__context7__",  # library documentation lookups
        "mcp__9197cddb",  # context7 alternate ID prefix
    }
)

# WHY: leet-speak substitution table \u2014 normalise before pattern matching so
# "IGN0RE" and "byp4ss" match the same regex as plain ASCII.
# str.maketrans(from, to) returns dict[int, int] (codepoint\u2192codepoint) \u2014 used with str.translate().
_LEET: dict[int, int] = str.maketrans("01345@$", "oieasas")

# WHY: Cyrillic letters that are visually identical to ASCII are a distinct
# encoding attack vector: NFKC does NOT convert them (different Unicode blocks).
# Maps the most common Cyrillic confusables to their ASCII lookalikes.
_CYRILLIC_CONFUSABLES: dict[int, int] = str.maketrans(
    "\u0430\u0435\u043e\u0440\u0441\u0443\u0445\u0410\u0412\u0421\u0415\u041d\u041a\u041c\u041e\u0420\u0422\u0425",
    "aeopcyxABCEHKMOPTX",
)

# WHY: Unicode RTL-override and other invisible directional marks are a separate
# encoding attack vector not covered by zero-width char check.
_INVISIBLE_PATTERN = re.compile(r"[\u200b\u200c\u200d\ufeff\u202a-\u202e\u2066-\u2069\u00ad]")


def _normalize(text: str) -> str:
    """NFKC-normalise + Cyrillic confusables + leet + strip invisible chars.

    WHY: attackers use homoglyphs (Cyrillic '\u043e' U+043E vs ASCII 'o' U+006F),
    leet-speak ('0' for 'o'), and Unicode invisible marks to bypass ASCII-only
    regexes. NFKC collapses compatibility equivalents; confusable table handles
    Cyrillic\u2194ASCII lookalikes (NFKC alone does NOT); leet and invisible-strip
    catch the remaining vectors. Original text is preserved for output.
    """
    normalised = unicodedata.normalize("NFKC", text)
    normalised = normalised.translate(_CYRILLIC_CONFUSABLES)
    normalised = normalised.translate(_LEET)
    normalised = _INVISIBLE_PATTERN.sub("", normalised)
    return normalised


# WHY: categories are separated by threat semantics, not syntax --
# this allows more precise block reason messages to the user.
PATTERNS: dict[str, re.Pattern[str]] = {
    "system_override": re.compile(
        # EN + RU variants of system-override phrases
        r"ignore previous|disregard instructions|you are now|new instructions:"
        r"|\u0438\u0433\u043d\u043e\u0440\u0438\u0440\u0443\u0439 (\u043f\u0440\u0435\u0434\u044b\u0434\u0443\u0449\u0438\u0435|\u0432\u0441\u0435) \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u0438"
        r"|\u0437\u0430\u0431\u0443\u0434\u044c (\u0432\u0441\u0435 |\u043f\u0440\u0435\u0434\u044b\u0434\u0443\u0449\u0438\u0435 )?\u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u0438"
        r"|\u043e\u0442\u043c\u0435\u043d\u0438 (\u043f\u0440\u0435\u0434\u044b\u0434\u0443\u0449\u0438\u0435 |\u0432\u0441\u0435 )?\u043f\u0440\u0430\u0432\u0438\u043b\u0430"
        r"|\u043d\u043e\u0432\u044b\u0435 \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u0438:",
        re.IGNORECASE,
    ),
    "jailbreak": re.compile(
        r"DAN mode|jailbreak|bypass safety|pretend you"
        r"|\u0440\u0435\u0436\u0438\u043c DAN|\u043e\u0431\u043e\u0439\u0434\u0438 (\u0437\u0430\u0449\u0438\u0442\u0443|\u0444\u0438\u043b\u044c\u0442\u0440\u044b|\u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0435\u043d\u0438\u044f)"
        r"|\u043f\u0440\u0438\u0442\u0432\u043e\u0440\u0438\u0441\u044c \u0447\u0442\u043e \u0442\u044b",
        re.IGNORECASE,
    ),
    "encoding_attack": re.compile(
        r"\x00|[\u200b\u200c\u200d\ufeff\u202a-\u202e\u2066-\u2069]",
    ),
    "data_exfil": re.compile(
        r"send to http|curl |wget |fetch\("
        r"|\u043e\u0442\u043f\u0440\u0430\u0432\u044c \u043d\u0430 http|\u043f\u0435\u0440\u0435\u0434\u0430\u0439 \u043d\u0430 (\u0441\u0435\u0440\u0432\u0435\u0440|\u0430\u0434\u0440\u0435\u0441)",
        re.IGNORECASE,
    ),
    "role_injection": re.compile(
        r"```system|\[SYSTEM\]|<system>|Human:|Assistant:",
        re.IGNORECASE,
    ),
    "credential_harvest": re.compile(
        r"what is your api key|show me your token|print your password"
        r"|\u043a\u0430\u043a\u043e\u0439 \u0443 \u0442\u0435\u0431\u044f api.?key|\u043f\u043e\u043a\u0430\u0436\u0438 (\u0441\u0432\u043e\u0439 |\u0442\u0432\u043e\u0439 )?(\u0442\u043e\u043a\u0435\u043d|\u043f\u0430\u0440\u043e\u043b\u044c|\u043a\u043b\u044e\u0447)",
        re.IGNORECASE,
    ),
    "command_injection": re.compile(
        # WHY: negative lookbehind (?<!\| ) excludes markdown table cells
        # like `| `--flag` |` while still catching `whoami`, `dangerous_cmd`.
        # Fixed-length lookbehind (exactly "| ") is supported by re module.
        r"; rm |\| cat /etc|&& curl|\$\(|(?<!\| )`(?!-)[^`]+`",
    ),
    # WHY: social engineering attacks wrap harmful instructions in polite
    # context ("as your developer...", "for debugging purposes...") to bypass
    # regex-only guards. These phrases have no legitimate use in tool inputs.
    "social_engineering": re.compile(
        r"please ignore (all |the )?(previous|prior|above|earlier)"
        r" (instructions?|rules?|constraints?)|"
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

# WHY: the command_injection backtick clause matches ANY inline-code span to
# catch command substitution like `whoami` or `curl evil.com | sh`. But that
# also flags harmless code references like `func_name()` or `path/to/file.py`
# — these have no whitespace or shell metacharacters, so nothing in them can
# execute. Confirmed false-positive via golden-set probe (2026-07-02): a
# tool_input containing `rotate_log_if_large()` in `hooks/utils.py` was
# blocked as HIGH-priority command_injection despite being a bare code
# reference. This does NOT cover bare single-token commands like `whoami` or
# `rm` (no path separator, no call parens) — those remain flagged, matching
# the existing test_command_injection_backticks contract.
#
# WHY the path branch requires a dotted extension (not just "word/word"):
# an independent review pass found that a looser "word[./]word" shape also
# admits bare system-binary paths like `bin/sh` or `bin/bash` — those have no
# shell metacharacters either, but they're not "code references" in the
# sense this fix is meant to exempt, and whitelisting them is an unnecessary
# widening of trust. Requiring the final segment to end in `.ext` keeps every
# confirmed sa1 case (`hooks/utils.py`, `tests/test_input_guard.py`,
# `docs/README.md`, `input_guard.py`) matching, while `bin/sh`-style paths
# (no extension) fall through and stay flagged.
_SAFE_BACKTICK_CONTENT = re.compile(
    r"^[\w\-]+(?:/[\w\-]+)*\.[\w\-]+$"  # path-like: word[/word]*.ext
    r"|^[A-Za-z_]\w*\(\)$"  # bare function call: name()
)


def _filter_safe_backtick_matches(matches: list[str]) -> list[str]:
    """Drop command_injection matches that are bare code identifiers/paths.

    WHY: only backtick-shaped matches are filtered here — the other
    command_injection alternatives ("; rm ", "&& curl", "$(") are untouched,
    so this only narrows the one clause responsible for the confirmed
    false positive, not the category's overall detection.
    """
    return [
        m
        for m in matches
        if not (m.startswith("`") and m.endswith("`") and _SAFE_BACKTICK_CONTENT.match(m[1:-1]))
    ]


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
    """Return dict {category: match_count} for all strings.

    WHY: each string is scanned twice — once as-is (catches verbatim attacks)
    and once normalised via NFKC + leet-table (catches homoglyph / leet bypass).
    Deduplication via max() prevents double-counting on the same pattern.
    """
    hits: dict[str, int] = {}
    for text in strings:
        normed = _normalize(text)
        for category, pattern in PATTERNS.items():
            raw_matches = pattern.findall(text)
            norm_matches = pattern.findall(normed) if normed != text else []
            if category == "command_injection":
                raw_matches = _filter_safe_backtick_matches(raw_matches)
                norm_matches = _filter_safe_backtick_matches(norm_matches)
            raw_count = len(raw_matches)
            norm_count = len(norm_matches)
            count = max(raw_count, norm_count)
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

    # WHY: trusted MCP tools return structured library docs, not user-controlled content.
    # Scanning them produces false-positives (backticks in code examples → command_injection).
    # 87 false-positives/12d confirmed via hook_triggers.jsonl before this allowlist was added.
    if any(tool_name.startswith(prefix) for prefix in TRUSTED_MCP_PREFIXES):
        sys.exit(0)

    tool_input: Any = data.get("tool_input", {})
    strings = collect_strings(tool_input)
    hits = scan(strings)

    if not hits:
        # NONE -- allow, return sanitized input
        clean_input = sanitize(tool_input)
        emit_permission_decision(decision="allow", updated_input=clean_input)
        sys.exit(0)

    categories = list(hits.keys())
    total_matches = sum(hits.values())
    # WHY: role_injection matching twice within one string (e.g. a transcript
    # quoting both "Human:" and "Assistant:" once each) is a repeated WEAK
    # signal, not two independent attack vectors. Capping only its own
    # contribution at 1 stops that transcript-quoting shape from crossing the
    # escalation threshold on its own, while a co-occurring category
    # (system_override, jailbreak, command_injection, ...) still adds its real
    # count, so genuine multi-vector attacks still escalate normally. This is
    # deliberately narrow to role_injection only — total_matches (used for
    # logging below) and every other category's counting are unchanged.
    # Confirmed false positive via golden-set probe (2026-07-02).
    escalation_score = sum(
        1 if category == "role_injection" else count for category, count in hits.items()
    )
    is_high = escalation_score >= 2 or any(c in HIGH_PRIORITY_CATEGORIES for c in categories)

    # WHY: log the trigger BEFORE block/sanitize so we capture even
    # the cases that get blocked (those are the most valuable signals
    # for measuring guard precision).
    session_id = data.get("session_id", "")
    sample = f"tool={tool_name} categories={categories} matches={total_matches}"

    if is_high:
        log_hook_trigger(
            hook_name=HOOK_NAME,
            trigger_type="prompt_injection_high",
            action="block",
            sample=sample,
            session_id=session_id,
        )
        reason = f"Prompt injection detected: {', '.join(categories)}"
        emit_permission_decision(decision="deny", reason=reason)
        sys.exit(0)

    # LOW -- allow with warning, sanitize output
    log_hook_trigger(
        hook_name=HOOK_NAME,
        trigger_type="prompt_injection_low",
        action="sanitize",
        sample=sample,
        session_id=session_id,
    )
    print(
        f"[input-guard] LOW threat in {tool_name}: {categories} ({total_matches} match). Allowed.",
        file=sys.stderr,
    )
    clean_input = sanitize(tool_input)
    emit_permission_decision(decision="allow", updated_input=clean_input)
    sys.exit(0)


if __name__ == "__main__":
    from utils import hook_main

    hook_main(main)
