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

import cogniml_client
from utils import emit_hook_result, find_project_memory, hook_main, parse_stdin

WIKI_DIR = Path.home() / ".claude" / "memory" / "wiki"
WIKI_INDEX = WIKI_DIR / "index.md"
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


def _read_index_topics() -> str:
    """Return a compact summary of the index.md topic map.

    WHY: Karpathy pattern — agent reads ONE file (index.md) to understand
    the full scope of the knowledge base, instead of grepping all files blind.
    Returns top-level topics + entry counts, e.g.:
      "research(3) python(8) hooks(5) archcode(2)"
    Injected at session start so Claude knows what knowledge exists before
    it even starts the task.
    """
    if not WIKI_INDEX.exists():
        return ""
    try:
        content = WIKI_INDEX.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""

    topics: list[str] = []
    for line in content.splitlines():
        # Match "### topic (N)" lines
        m = re.match(r"^###\s+(\S+)\s+\((\d+)\)", line)
        if m:
            topics.append(f"{m.group(1)}({m.group(2)})")
    return " · ".join(topics[:10]) if topics else ""


def _query_wiki(keywords: list[str]) -> list[str]:
    """Return display titles of wiki entries that contain any keyword.

    WHY: When index.md exists, prefer entries mentioned there (they are
    structured and tagged). Fall back to full scan if index is missing.
    """
    if not WIKI_DIR.exists() or not keywords:
        return []

    # Fast path: scan index.md for keyword matches (1 file instead of N)
    if WIKI_INDEX.exists():
        try:
            index_text = WIKI_INDEX.read_text(encoding="utf-8", errors="ignore").lower()
            index_lines = index_text.splitlines()
            matches: list[str] = []
            for line in index_lines:
                if any(kw in line for kw in keywords):
                    # Extract [[Title]] from line
                    found = re.findall(r"\[\[([^\]]+)\]\]", line)
                    matches.extend(found)
            if matches:
                # deduplicate preserving order
                seen: set[str] = set()
                result: list[str] = []
                for m in matches:
                    if m not in seen:
                        seen.add(m)
                        result.append(f"[[{m}]]")
                return result[:3]
        except OSError:
            pass  # fall through to full scan

    # Slow path: full scan when no index exists
    scan_matches: list[str] = []
    for f in sorted(WIKI_DIR.glob("*.md")):
        if f.name == "index.md":
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        if any(kw in text for kw in keywords):
            title = f.stem.replace("-", " ").replace("_", " ").title()
            scan_matches.append(f"[[{title}]]")
    return scan_matches[:3]


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
    index_topics = _read_index_topics()

    parts: list[str] = []
    # WHY: show knowledge map first — agent knows what exists before grepping.
    # Even if no keyword match, the map orients the agent to available knowledge.
    if index_topics:
        parts.append(f"🗺 Knowledge base: {index_topics}")
    if wiki_matches:
        parts.append(f"📚 Relevant knowledge: {', '.join(wiki_matches)}")
    elif focus:
        # WHY: semantic fallback — when grep finds nothing, CogniML's vector
        # search may match conceptually related Skills from ML experiments.
        # E.g. "hook timeout" → finds "daemon thread blocking" even with
        # different wording. Truncated to 300 chars to keep the query fast.
        cogniml_answer = cogniml_client.advise(focus[:300], top_k=2)
        if cogniml_answer:
            parts.append(f"🔍 CogniML insight: {cogniml_answer[:400]}")
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
