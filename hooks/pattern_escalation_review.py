#!/usr/bin/env python3
"""SessionStart hook: weekly review of recurring [×N] patterns.

WHY: patterns.md accumulates entries tagged [×N] indicating how often the
mistake recurred. After [×3] the user's own protocol says "treat as hard
rule" — but the escalation is passive: no surface forces a review.
This hook fires the review on SessionStart, but only once per week,
listing all [×3+] patterns NOT already promoted to a [CRITICAL] tag,
so the user can decide whether to:
  - promote into ~/.claude/rules/*.md (hard rule)
  - add [CRITICAL] severity tag (recognised severity)
  - leave passive (counter keeps climbing)

The week timer lives in ~/.claude/state/last_pattern_escalation.txt
to avoid surfacing the same list on every session start.

The hook is fail-open: any error logs to stderr and exits 0 so it can't
block a session start.
"""

from __future__ import annotations

import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from utils import emit_hook_result, parse_stdin

# WHY: same resolution as knowledge_librarian — check canonical path
# first, fall back to _auto/. See rules/memory-protocol.md.
_MEMORY = Path.home() / ".claude" / "memory"
_PATTERNS_CANONICAL = _MEMORY / "patterns.md"
_PATTERNS_LEGACY = _MEMORY / "_auto" / "patterns.md"

# WHY: state lives outside of memory/ to avoid being mistaken for
# user knowledge — it is operational telemetry, not learning content.
_STATE_DIR = Path.home() / ".claude" / "state"
_LAST_REVIEW_FILE = _STATE_DIR / "last_pattern_escalation.txt"

# WHY: tuneable cadence. Weekly default — too short = noise, too long
# = escalation never fires. 7 days matches typical sprint review rhythm.
_REVIEW_INTERVAL_DAYS = 7

# WHY: [×N] entries below this threshold are "could be coincidence".
# At ×3+ user's own protocol classifies as systemic — escalation candidate.
_ESCALATION_THRESHOLD = 3

# WHY: patterns already tagged [CRITICAL] have been recognised — no need
# to re-surface them in the weekly review.
_ALREADY_ESCALATED = re.compile(r"\[(CRITICAL|HARD-RULE|RULE-PROMOTED)\]", re.IGNORECASE)

# WHY: actual patterns.md uses several heading formats — both H2 and H3,
# and the count can be tail "[×N]" OR fused "[AVOID×N]"/"[REPEAT×N]".
# Observed examples in ~/.claude/memory/_auto/patterns.md:
#   ## [AVOID] [Types] something [×3]
#   ### [2026-03-26] [AVOID] datetime mix [×3]
#   ### [2026-05-01] [AVOID×1] [CRITICAL] [agent:skeptic] Validation Theater
# Detect headers loosely, then count via two separate sub-patterns.
_HEADER_LINE = re.compile(r"^#{2,3}\s+(?P<title>.+)$")
_TAIL_COUNT = re.compile(r"\[×(\d+)\]")
_FUSED_COUNT = re.compile(r"\[(?:AVOID|REPEAT)×(\d+)\]")


def _resolve_patterns_path() -> Path | None:
    """Return whichever patterns.md exists, canonical first."""
    if _PATTERNS_CANONICAL.exists():
        return _PATTERNS_CANONICAL
    if _PATTERNS_LEGACY.exists():
        return _PATTERNS_LEGACY
    return None


def _last_review_date() -> date | None:
    """Parse the stored YYYY-MM-DD of the last review, or None if absent."""
    if not _LAST_REVIEW_FILE.exists():
        return None
    try:
        text = _LAST_REVIEW_FILE.read_text(encoding="utf-8").strip()
        return date.fromisoformat(text[:10])
    except (OSError, ValueError):
        return None


def _record_review_now() -> None:
    """Persist today's date so the next 6 sessions skip the review."""
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _LAST_REVIEW_FILE.write_text(datetime.now(UTC).date().isoformat(), encoding="utf-8")
    except OSError as e:  # noqa: BLE001
        print(f"[pattern-escalation] state write failed: {e}", file=sys.stderr)


def _is_review_due(today: date) -> bool:
    """True if no review recorded OR ≥ _REVIEW_INTERVAL_DAYS since last."""
    last = _last_review_date()
    if last is None:
        return True
    return today - last >= timedelta(days=_REVIEW_INTERVAL_DAYS)


def _extract_escalation_candidates(text: str) -> list[tuple[str, int]]:
    """Parse patterns.md text and return [(title, count), ...].

    Only entries with count >= _ESCALATION_THRESHOLD AND not already
    tagged [CRITICAL]/[HARD-RULE]/[RULE-PROMOTED] are returned.
    """
    lines = text.splitlines()
    candidates: list[tuple[str, int]] = []
    for line in lines:
        header = _HEADER_LINE.match(line)
        if not header:
            continue
        title = header.group("title").strip()
        # Must be a pattern entry, not arbitrary heading.
        if "[AVOID" not in title and "[REPEAT" not in title:
            continue
        # WHY: count may come from either tail "[×N]" or fused "[AVOID×N]".
        # Prefer tail because it's the documented format in error-to-lesson.
        count: int | None = None
        tail = _TAIL_COUNT.search(title)
        if tail:
            count = int(tail.group(1))
        else:
            fused = _FUSED_COUNT.search(title)
            if fused:
                count = int(fused.group(1))
        if count is None or count < _ESCALATION_THRESHOLD:
            continue
        if _ALREADY_ESCALATED.search(title):
            continue
        # Strip the count markers from the displayed title for cleanliness —
        # the count is shown separately. Preserves [AVOID]/[REPEAT]/category tags.
        clean_title = _TAIL_COUNT.sub("", title)
        clean_title = _FUSED_COUNT.sub(lambda m: m.group(0).split("×")[0] + "]", clean_title)
        clean_title = clean_title.strip().rstrip()
        candidates.append((clean_title, count))
    # WHY: sort by count desc — highest pain first.
    candidates.sort(key=lambda x: -x[1])
    return candidates


def _format_message(candidates: list[tuple[str, int]]) -> str:
    """Render the escalation suggestion block for emit_hook_result."""
    if not candidates:
        return (
            "[pattern-escalation] Weekly review: no patterns reached "
            f"[×{_ESCALATION_THRESHOLD}+] without an escalation tag. "
            "System healthy."
        )
    lines = [
        "[pattern-escalation] Weekly review — these patterns recurred "
        f"≥{_ESCALATION_THRESHOLD} times without escalation. "
        "Consider promoting each to a hard rule (~/.claude/rules/*.md) "
        "or adding a [CRITICAL] severity tag in patterns.md:",
    ]
    # WHY: cap at 10 — past that the user stops reading.
    for title, count in candidates[:10]:
        lines.append(f"  • [×{count}] {title}")
    if len(candidates) > 10:
        lines.append(f"  ... and {len(candidates) - 10} more.")
    lines.append(
        "Suggested action: open patterns.md, pick the top 1, decide:"
        " promote-to-rule / mark [CRITICAL] / accept-as-known."
    )
    return "\n".join(lines)


def main() -> None:
    # Consume stdin (SessionStart sends a payload) — fail-open on parse error.
    parse_stdin()

    today = datetime.now(UTC).date()
    if not _is_review_due(today):
        sys.exit(0)

    patterns_path = _resolve_patterns_path()
    if patterns_path is None:
        # No patterns.md anywhere — nothing to review.
        sys.exit(0)

    try:
        text = patterns_path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:  # noqa: BLE001
        print(f"[pattern-escalation] read failed: {e}", file=sys.stderr)
        sys.exit(0)

    candidates = _extract_escalation_candidates(text)
    message = _format_message(candidates)
    emit_hook_result("SessionStart", message)
    _record_review_now()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        # Fail-open: never block SessionStart on hook error.
        print(f"[pattern-escalation] fatal: {e}", file=sys.stderr)
        sys.exit(0)
