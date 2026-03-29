#!/usr/bin/env python3
"""PreCompact hook: save critical context before compression.

WHY: When Claude compresses context, details of current work are lost.
This hook updates the timestamp AND extracts pending tasks from
activeContext.md into goals.md so they survive the /clear cycle.
It also applies progressive compression to activeContext.md itself,
so important decisions and errors are never lost to /clear.
It also deduplicates patterns.md and trims stale activeContext entries
so memory files do not grow unbounded over time.
"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from utils import find_project_memory

# WHY: these markers signal unfinished work that must survive compaction
PENDING_PATTERNS = re.compile(
    r"^[-*]\s*\[?\s?\]?\s*(TODO|NEXT|PENDING|BLOCKED|WIP|IN.PROGRESS)\b.*",
    re.IGNORECASE,
)

# WHY: sections that carry architectural/debugging history — losing them
# forces rediscovering bugs and revisiting rejected designs.
NEVER_SUMMARIZE_PREFIXES = ("## Error", "## Decision", "## Correction", "## Bug")

# Number of lines to keep verbatim at the tail of compressible sections.
# 20 gives enough recent-activity context without ballooning the file.
VERBATIM_TAIL = 20


class _Section(NamedTuple):
    """One markdown H2 section parsed from activeContext.md."""

    heading: str  # the full "## Heading" line
    lines: list[str]  # body lines (not including the heading line)


def _parse_sections(content: str) -> tuple[list[str], list[_Section]]:
    """Split markdown content into a preamble and H2 sections.

    Returns:
        preamble: lines before the first H2 heading.
        sections: list of _Section objects in document order.

    WHY: operating on parsed sections is safer than regex-replacing
    the raw text when some sections must be kept verbatim.
    """
    preamble: list[str] = []
    sections: list[_Section] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        if line.startswith("## "):
            if current_heading is not None:
                sections.append(_Section(current_heading, current_lines))
            elif current_lines or not sections:
                preamble = current_lines[:]
            current_heading = line
            current_lines = []
        else:
            current_lines.append(line)

    if current_heading is not None:
        sections.append(_Section(current_heading, current_lines))
    elif not sections:
        preamble = current_lines

    return preamble, sections


def _summarize_lines(lines: list[str]) -> str:
    """Produce a one-line summary from section body lines.

    Strategy: take the first non-empty, non-list-marker line.
    Falls back to a generic placeholder if the section is blank.

    WHY: a single representative sentence is enough to remind
    the model that this section existed without bloating the file.
    """
    for line in lines:
        stripped = line.strip()
        # Skip blank lines and pure list markers with no real content
        if stripped and not re.match(r"^[-*#>|]+\s*$", stripped):
            # Truncate very long lines so the summary stays scannable
            return stripped[:120] + ("..." if len(stripped) > 120 else "")
    return "(empty section)"


def _create_progressive_summary(active_path: Path) -> bool:
    """Compress activeContext.md in place, preserving critical sections verbatim.

    Algorithm per section:
    - Heading matches NEVER_SUMMARIZE_PREFIXES → keep entire section as-is.
    - Otherwise → keep last VERBATIM_TAIL lines verbatim; replace older lines
      with a single summary line (prefixed with "[summarized]").

    Returns True if the file was rewritten, False if nothing changed or the
    file did not exist (graceful degradation).

    WHY: activeContext.md grows unbounded during long sessions.  Compressing
    it here means /clear restores a concise context rather than the full
    session history, while never discarding architectural decisions or bug notes.
    """
    if not active_path.exists():
        return False

    original = active_path.read_text(encoding="utf-8")
    preamble, sections = _parse_sections(original)

    if not sections:
        # No H2 sections — nothing to compress, leave file intact
        return False

    compressed_sections: list[str] = []

    for section in sections:
        is_protected = any(section.heading.startswith(p) for p in NEVER_SUMMARIZE_PREFIXES)

        if is_protected:
            # Keep verbatim — join heading + original body
            block = "\n".join([section.heading] + section.lines)
            compressed_sections.append(block)
            continue

        body = section.lines
        # Strip trailing blank lines so tail calculation is meaningful
        while body and not body[-1].strip():
            body = body[:-1]

        if len(body) <= VERBATIM_TAIL:
            # Short enough — no compression needed
            block = "\n".join([section.heading] + section.lines)
            compressed_sections.append(block)
            continue

        # Summarize the head, keep the tail verbatim
        head = body[: len(body) - VERBATIM_TAIL]
        tail = body[len(body) - VERBATIM_TAIL :]
        summary_line = f"[summarized] {_summarize_lines(head)}"
        block = "\n".join([section.heading, summary_line] + tail)
        compressed_sections.append(block)

    new_content = "\n".join(preamble) + "\n" + "\n\n".join(compressed_sections) + "\n"

    if new_content == original:
        return False

    active_path.write_text(new_content, encoding="utf-8")
    return True


# WHY: matches the [×N] counter that patterns.md uses to track recurrences.
# A missing counter is treated as ×1 so it loses to any explicit counter.
_COUNTER_RE = re.compile(r"\[×(\d+)\]")

# WHY: ISO 8601 date (YYYY-MM-DD) is the project-wide convention for timestamps.
# We accept an optional time component (space or T + HH:MM…) so the same regex
# covers both "2026-03-28" and "2026-03-28 14:05".
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def _word_overlap(a: str, b: str) -> float:
    """Compute Jaccard similarity between the word sets of two strings.

    Returns a float in [0, 1].  Values >0.8 indicate near-duplicate titles.

    WHY: simple set intersection avoids importing difflib or any external lib
    while still being robust to reworded-but-same-topic headings.
    """
    words_a = set(re.sub(r"[^\w]", " ", a.lower()).split())
    words_b = set(re.sub(r"[^\w]", " ", b.lower()).split())
    if not words_a and not words_b:
        return 1.0
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def _extract_counter(heading: str) -> int:
    """Return the [×N] value from a patterns.md ### heading, defaulting to 1."""
    match = _COUNTER_RE.search(heading)
    return int(match.group(1)) if match else 1


def _dedup_patterns(patterns_path: Path) -> int:
    """Remove near-duplicate entries from patterns.md.

    An "entry" is a block starting with a `###` heading.  Two entries are
    considered duplicates when the Jaccard similarity of their titles exceeds
    0.8.  The entry with the higher [×N] counter is kept; the other is dropped.
    When counters are equal the first occurrence wins (stable sort).

    Returns the number of entries removed.

    WHY: patterns.md accumulates duplicates over long sessions as the same
    lesson is re-extracted with slightly different wording.  De-duplication
    here ensures the file stays useful as a reference rather than a noisy log.
    Handles missing file gracefully (returns 0).
    """
    if not patterns_path.exists():
        return 0

    content = patterns_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # ── Parse into (preamble, list of (heading_line, body_lines)) ──
    preamble: list[str] = []
    entries: list[tuple[str, list[str]]] = []  # (heading, body_lines)
    current_heading: str | None = None
    current_body: list[str] = []

    for line in lines:
        if line.startswith("### "):
            if current_heading is not None:
                entries.append((current_heading, current_body))
            else:
                preamble = current_body[:]
            current_heading = line
            current_body = []
        else:
            current_body.append(line)

    if current_heading is not None:
        entries.append((current_heading, current_body))
    else:
        # No ### entries at all — nothing to deduplicate
        return 0

    # ── Greedy deduplication (O(n²) — patterns.md is small) ──
    kept: list[tuple[str, list[str]]] = []
    removed = 0

    for candidate_heading, candidate_body in entries:
        duplicate_found = False
        for i, (kept_heading, _) in enumerate(kept):
            # WHY: strip the counter and tag tokens for a cleaner title comparison
            title_a = _COUNTER_RE.sub("", kept_heading).lstrip("#").strip()
            title_b = _COUNTER_RE.sub("", candidate_heading).lstrip("#").strip()

            if _word_overlap(title_a, title_b) > 0.8:
                # Duplicate — keep whichever has the higher counter
                if _extract_counter(candidate_heading) > _extract_counter(kept_heading):
                    kept[i] = (candidate_heading, candidate_body)
                removed += 1
                duplicate_found = True
                break

        if not duplicate_found:
            kept.append((candidate_heading, candidate_body))

    if removed == 0:
        return 0

    # ── Rebuild file ──
    blocks: list[str] = preamble[:]
    for heading, body in kept:
        blocks.append(heading)
        blocks.extend(body)

    patterns_path.write_text("\n".join(blocks) + "\n", encoding="utf-8")
    return removed


def _trim_old_entries(context_path: Path, max_age_days: int = 90) -> int:
    """Remove stale H2 sections from activeContext.md.

    A section is removed when ALL of the following are true:
    - Its heading does NOT start with any prefix in NEVER_SUMMARIZE_PREFIXES.
    - At least one YYYY-MM-DD date is found in the section body.
    - The most recent of those dates is older than max_age_days ago.

    Sections with no parseable date are left untouched (conservative default).

    Returns the number of sections removed.

    WHY: activeContext.md accumulates session notes indefinitely.  Entries
    older than 90 days are no longer "active" context — they belong in
    decisions.md or patterns.md.  Removing them here keeps the file focused
    and prevents the context window cost from growing with project age.
    Handles missing file gracefully (returns 0).
    """
    if not context_path.exists():
        return 0

    content = context_path.read_text(encoding="utf-8")
    preamble, sections = _parse_sections(content)

    if not sections:
        return 0

    cutoff = datetime.now() - timedelta(days=max_age_days)
    kept_sections: list[_Section] = []
    removed = 0

    for section in sections:
        # Protected sections are always kept regardless of age
        is_protected = any(section.heading.startswith(p) for p in NEVER_SUMMARIZE_PREFIXES)
        if is_protected:
            kept_sections.append(section)
            continue

        # Find the newest date mentioned in the section body
        body_text = "\n".join(section.lines)
        date_strings = _DATE_RE.findall(body_text)

        if not date_strings:
            # WHY: no date → we cannot safely judge age → keep it
            kept_sections.append(section)
            continue

        newest_date = max(datetime.strptime(d, "%Y-%m-%d") for d in date_strings)

        if newest_date < cutoff:
            removed += 1
        else:
            kept_sections.append(section)

    if removed == 0:
        return 0

    # ── Rebuild file ──
    compressed_sections = ["\n".join([s.heading] + s.lines) for s in kept_sections]
    new_content = "\n".join(preamble) + "\n" + "\n\n".join(compressed_sections) + "\n"
    context_path.write_text(new_content, encoding="utf-8")
    return removed


def extract_pending_items(content: str) -> list[str]:
    """Extract lines matching TODO/NEXT/PENDING/BLOCKED from activeContext."""
    return [line.strip() for line in content.splitlines() if PENDING_PATTERNS.match(line.strip())]


def save_pending_to_goals(items: list[str], active_path: Path) -> None:
    """Append pending items to goals.md in the same memory directory."""
    if not items:
        return
    goals_path = active_path.parent / "goals.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    block = f"\n### Carried from compaction ({timestamp})\n"
    block += "\n".join(f"- {item}" for item in items) + "\n"

    if goals_path.exists():
        existing = goals_path.read_text(encoding="utf-8")
        goals_path.write_text(existing.rstrip() + "\n" + block, encoding="utf-8")
    else:
        goals_path.write_text(f"# Goals\n{block}", encoding="utf-8")


def main():
    active = find_project_memory()
    if active is not None:
        content = active.read_text(encoding="utf-8")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 1. Extract pending tasks before they are lost
        pending = extract_pending_items(content)
        if pending:
            save_pending_to_goals(pending, active)
            print(f"[PreCompact] Saved {len(pending)} pending items to goals.md")

        # 2. Progressive compression — runs BEFORE the timestamp update so
        #    the rewrite does not clobber the freshly written timestamp line.
        #    WHY: compression must happen first; updating the timestamp after
        #    means the final file always reflects the compaction moment.
        compressed = _create_progressive_summary(active)
        if compressed:
            print(f"[PreCompact] Progressive summary written to {active}")
        else:
            print("[PreCompact] No compression needed (file unchanged).")

        # 3. Memory hygiene — dedup patterns.md and trim stale context entries.
        #    WHY: run after compression so we operate on already-tightened
        #    content; both functions are idempotent and handle missing files.
        patterns_path = active.parent / "patterns.md"
        deduped = _dedup_patterns(patterns_path)
        if deduped:
            print(f"[PreCompact] Removed {deduped} duplicate pattern(s) from {patterns_path.name}")

        trimmed = _trim_old_entries(active)
        if trimmed:
            print(f"[PreCompact] Trimmed {trimmed} stale section(s) from {active.name}")

        # 4. Update the "Updated:" line (re-read after potential compression)
        lines = active.read_text(encoding="utf-8").split("\n")
        for i, line in enumerate(lines):
            if line.startswith("## Updated:"):
                lines[i] = f"## Updated: {timestamp} (pre-compact)"
                break
        active.write_text("\n".join(lines), encoding="utf-8")
        print(f"[PreCompact] Updated {active} timestamp to {timestamp}")
    else:
        print("[PreCompact] No project activeContext.md found.")

    # Log compaction event
    log_dir = os.path.expanduser("~/.claude/logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "sessions.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} | COMPACT | cwd={os.getcwd()}\n")


if __name__ == "__main__":
    main()
