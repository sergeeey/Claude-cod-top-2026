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
from datetime import date
from pathlib import Path

import cogniml_client
import vector_store
from utils import emit_hook_result, find_project_memory, hook_main, parse_stdin

WIKI_DIR = Path.home() / ".claude" / "memory" / "_auto" / "wiki"
WIKI_INDEX = WIKI_DIR / "index.md"
PATTERNS_PATH = Path.home() / ".claude" / "memory" / "_auto" / "patterns.md"
PLAYBOOK_PATH = Path.home() / ".claude" / "memory" / "_auto" / "playbook.md"

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


def _score_entry(title: str) -> float:
    """Attention decay score: 70% recency + 30% frequency.

    WHY: keyword matching returns entries in index order — old entries rank
    equally with fresh ones. Attention decay mirrors human memory: recent
    lessons surface first, frequently-hit patterns stay relevant longer.
    Half-life = 14 days. [×N] counter boosts score up to +0.3.
    """
    stem = title.split("|")[0].strip()

    # Recency: decay by half every 14 days
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", stem)
    if date_match:
        try:
            days_ago = (date.today() - date.fromisoformat(date_match.group(1))).days
            recency = 1.0 / (1.0 + days_ago / 14)
        except ValueError:
            recency = 0.5
    else:
        recency = 0.5

    # Frequency: [×N] counter in file content, capped at 10
    frequency = 0.0
    file_path = WIKI_DIR / f"{stem}.md"
    if file_path.exists():
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"\[×(\d+)\]", content)
            if m:
                frequency = min(int(m.group(1)) / 10.0, 1.0)
        except OSError:
            pass

    return 0.7 * recency + 0.3 * frequency


def _query_wiki(keywords: list[str], focus_text: str = "") -> list[str]:
    """Return display titles of wiki entries that contain any keyword.

    WHY: When index.md exists, prefer entries mentioned there (they are
    structured and tagged). Falls back to full scan if index is missing.
    After keyword matching, if fewer than 3 results found, supplements with
    semantic search (vector_store) — catches synonyms and related concepts
    that exact keyword matching misses.
    """
    if not WIKI_DIR.exists() or not keywords:
        return []

    # Fast path: scan index.md for keyword matches (1 file instead of N)
    if WIKI_INDEX.exists():
        try:
            index_text = WIKI_INDEX.read_text(encoding="utf-8", errors="ignore")
            index_lines = index_text.splitlines()
            # WHY: lowercase only for matching; extract titles from original to preserve case
            index_lines_lower = index_text.lower().splitlines()
            matches: list[str] = []
            for orig_line, low_line in zip(index_lines, index_lines_lower, strict=True):
                if any(kw in low_line for kw in keywords):
                    # Extract [[Title]] from original line to preserve original case
                    found = re.findall(r"\[\[([^\]]+)\]\]", orig_line)
                    matches.extend(found)
            if matches:
                # Deduplicate then sort by attention decay score (recency + frequency)
                seen: set[str] = set()
                unique: list[str] = []
                for m in matches:
                    if m not in seen:
                        seen.add(m)
                        unique.append(m)
                unique.sort(key=_score_entry, reverse=True)
                result = [f"[[{m}]]" for m in unique[:3]]
                # Semantic supplement when keyword scan finds < 3 results
                if len(result) < 3:
                    query = focus_text or " ".join(keywords)
                    needed = 3 - len(result)
                    existing = {r.strip("[]") for r in result}
                    for title in vector_store.semantic_search(query, top_k=needed + 2):
                        if title not in existing and len(result) < 3:
                            result.append(f"[[{title}]]")
                            existing.add(title)
                return result
        except OSError:
            pass  # fall through to full scan

    # Slow path: full scan when no index exists
    # WHY: rglob recurses into PARA subdirs (projects/areas/resources/archives)
    # so entries routed there are still found even without index.md.
    scan_matches: list[str] = []
    for f in sorted(WIKI_DIR.rglob("*.md")):
        if f.name == "index.md":
            continue
        if "daily" in f.parts:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        if any(kw in text for kw in keywords):
            scan_matches.append(f.stem)
    # Sort by attention decay score before slicing
    scan_matches.sort(key=_score_entry, reverse=True)
    result = [f"[[{s}]]" for s in scan_matches[:3]]

    # Semantic fallback: supplement keyword results with vector similarity
    # WHY: if keyword grep finds < 3 results, vector search catches related
    # concepts (synonyms, paraphrases) that exact matching would miss.
    if len(result) < 3:
        query = focus_text or " ".join(keywords)
        needed = 3 - len(result)
        existing_titles = {r.strip("[]") for r in result}
        semantic = vector_store.semantic_search(query, top_k=needed + 2)
        for title in semantic:
            if title not in existing_titles and len(result) < 3:
                result.append(f"[[{title}]]")
                existing_titles.add(title)

    return result


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


def _top_avoid_patterns(limit: int = 5) -> list[str]:
    """Return top-N [AVOID] patterns by recurrence count [×N], unconditionally.

    WHY: keyword-matched patterns depend on focus text overlap — if keywords
    don't match, zero patterns surface. But the most repeated mistakes (high
    [×N]) are valuable regardless of current task. Showing them every session
    closes the "writes but never reads" loop.
    """
    if not PATTERNS_PATH.exists():
        return []
    try:
        content = PATTERNS_PATH.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    import re

    scored: list[tuple[int, str]] = []
    for line in content.splitlines():
        if "[AVOID]" not in line:
            continue
        m = re.search(r"\[×(\d+)\]", line)
        count = int(m.group(1)) if m else 1
        clean = line.strip().lstrip("- #").strip()[:120]
        scored.append((count, clean))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [f"  ⚠ [×{c}] {text}" for c, text in scored[:limit]]


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

    wiki_matches = _query_wiki(keywords, focus_text=focus)
    keyword_patterns = _query_patterns(keywords)
    top_avoids = _top_avoid_patterns(5)
    best = _best_approach()
    index_topics = _read_index_topics()

    parts: list[str] = []
    # WHY: show knowledge map first — agent knows what exists before grepping.
    if index_topics:
        parts.append(f"🗺 Knowledge base: {index_topics}")
    if wiki_matches:
        parts.append(f"📚 Relevant knowledge: {', '.join(wiki_matches)}")
    elif focus:
        cogniml_answer = cogniml_client.advise(focus[:300], top_k=2)
        if cogniml_answer:
            parts.append(f"🔍 CogniML insight: {cogniml_answer[:400]}")
    # WHY: keyword-matched patterns are task-specific (may be empty if keywords
    # don't overlap). Top avoids are unconditional — always show the most
    # repeated mistakes so they stay top-of-mind every session.
    if keyword_patterns:
        parts.append("⚠️ Known issues for this area:\n" + "\n".join(keyword_patterns))
    if top_avoids:
        parts.append("🔴 Top recurring mistakes (всегда помнить):\n" + "\n".join(top_avoids))
    if best:
        parts.append(f"✅ Best approach (ACE playbook): {best}")

    if not parts:
        sys.exit(0)

    context = "[knowledge-librarian] Pre-task context:\n" + "\n".join(parts)
    emit_hook_result("SessionStart", context)


if __name__ == "__main__":
    hook_main(main)
