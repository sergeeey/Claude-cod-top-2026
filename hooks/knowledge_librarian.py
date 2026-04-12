#!/usr/bin/env python3
"""SessionStart hook: inject relevant knowledge before task starts.

WHY: Claude begins each task knowing only activeContext.md. The wiki/,
patterns.md, and playbook.md contain accumulated institutional knowledge
that is NEVER surfaced unless manually referenced — this is the "amnesia"
problem described by Karpathy. This hook queries the knowledge base for
task-relevant entries and injects them proactively.

ACE paper (arXiv:2510.04618) role: Librarian — knows the knowledge graph,
extracts what's relevant for the current task before the Generator starts.
"""

import re
import sys
from pathlib import Path

from utils import emit_hook_result, find_project_memory, hook_main, parse_stdin

WIKI_DIR = Path.home() / ".claude" / "memory" / "wiki"
PATTERNS_PATH = Path.home() / ".claude" / "memory" / "patterns.md"
PLAYBOOK_PATH = Path.home() / ".claude" / "memory" / "playbook.md"

# WHY: stop words produce false-positive keyword matches ("the" matches everything).
# Bilingual set covers both EN and RU session notes.
_STOP_WORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "have",
        "will",
        "been",
        "they",
        "were",
        "when",
        "than",
        "into",
        "also",
        "some",
        "only",
        "это",
        "для",
        "при",
        "над",
        "под",
        "все",
        "как",
        "что",
        "нет",
        "или",
        "после",
        "перед",
        "через",
        "чтобы",
        "если",
        "когда",
        "очень",
    }
)


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords (4+ chars, not stop words, deduplicated)."""
    words = re.findall(r"\b[a-zA-Zа-яА-Я]{4,}\b", text)
    seen: set[str] = set()
    result: list[str] = []
    for w in words:
        wl = w.lower()
        if wl not in _STOP_WORDS and wl not in seen:
            seen.add(wl)
            result.append(wl)
    return result[:15]


def _read_current_focus() -> str:
    """Extract ## Current Focus section from project activeContext.md."""
    ctx = find_project_memory()
    if not ctx:
        return ""
    try:
        content = ctx.read_text(encoding="utf-8")
    except OSError:
        return ""

    in_focus = False
    lines: list[str] = []
    for line in content.splitlines():
        if line.strip() == "## Current Focus":
            in_focus = True
            continue
        if in_focus:
            if line.startswith("## "):
                break
            lines.append(line)
    return " ".join(lines)


def _query_wiki(keywords: list[str]) -> list[str]:
    """Return display titles of wiki entries that contain any keyword."""
    if not WIKI_DIR.exists() or not keywords:
        return []

    matches: list[str] = []
    for f in sorted(WIKI_DIR.glob("*.md")):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        if any(kw in text for kw in keywords):
            title = f.stem.replace("-", " ").replace("_", " ").title()
            matches.append(f"[[{title}]]")
    return matches[:3]


def _query_patterns(keywords: list[str]) -> list[str]:
    """Return [AVOID] pattern lines that match any keyword."""
    if not PATTERNS_PATH.exists() or not keywords:
        return []
    try:
        content = PATTERNS_PATH.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    results: list[str] = []
    for line in content.splitlines():
        if "[AVOID]" not in line and "[×" not in line:
            continue
        if any(kw in line.lower() for kw in keywords):
            clean = line.strip().lstrip("- ").strip()
            results.append(f"  ⚠ {clean[:120]}")
    return results[:3]


def _best_approach() -> str:
    """Return the top-ranked approach name from playbook.md.

    WHY: playbook.md is sorted by net score (helpful - harmful).
    The first ### entry is always the most proven approach.
    """
    if not PLAYBOOK_PATH.exists():
        return ""
    try:
        content = PLAYBOOK_PATH.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""

    for line in content.splitlines():
        if line.startswith("### "):
            return line[4:].strip()
    return ""


def main() -> None:
    parse_stdin()  # consume stdin — SessionStart may send hook metadata

    focus = _read_current_focus()
    if not focus.strip():
        sys.exit(0)

    keywords = _extract_keywords(focus)
    if not keywords:
        sys.exit(0)

    wiki_matches = _query_wiki(keywords)
    avoid_patterns = _query_patterns(keywords)
    best = _best_approach()

    parts: list[str] = []
    if wiki_matches:
        parts.append(f"📚 Relevant knowledge: {', '.join(wiki_matches)}")
    if avoid_patterns:
        parts.append("⚠️ Known issues for this area:\n" + "\n".join(avoid_patterns))
    if best:
        parts.append(f"✅ Best approach (ACE playbook): {best}")

    if not parts:
        sys.exit(0)

    context = "[knowledge-librarian] Pre-task context:\n" + "\n".join(parts)
    emit_hook_result("SessionStart", context)


if __name__ == "__main__":
    hook_main(main)
