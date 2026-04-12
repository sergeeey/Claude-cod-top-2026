#!/usr/bin/env python3
"""UserPromptSubmit hook: inject relevant wiki articles before each prompt.

WHY: knowledge_librarian.py runs at SessionStart (once per session).
This hook runs on EVERY prompt — so if the user switches topic mid-session,
they still get the relevant wiki context for the new question.
Borrowed pattern from ub3dqy/llm-wiki (shared_wiki_search.py), adapted
to use our index.md fast path instead of full file scan.

ACE paper role: Librarian (per-prompt variant) — just-in-time knowledge
retrieval, not just session-start injection.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from utils import emit_hook_result, hook_main, parse_stdin

# WHY: guard against hooks firing inside Agent SDK sub-invocations.
# coleam00/claude-memory-compiler pattern — prevents infinite recursion
# when compile.py spawns a Claude agent that runs hooks again.
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

WIKI_DIR = Path.home() / ".claude" / "memory" / "wiki"
WIKI_INDEX = WIKI_DIR / "index.md"

MAX_ARTICLES = 2  # WHY: cap at 2 — context budget, not a lecture
MAX_ARTICLE_CHARS = 1200  # WHY: enough for key facts, not full article
MIN_PROMPT_LEN = 15  # WHY: skip greetings / single-word prompts
MAX_CONTEXT_CHARS = 3000  # WHY: keep total injection under token budget

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
        "what",
        "how",
        "why",
        "where",
        "which",
        "there",
        "can",
        "you",
        "your",
        "not",
        "but",
        "are",
        "was",
        "its",
        "use",
        "это",
        "как",
        "что",
        "где",
        "когда",
        "зачем",
        "нужно",
        "можно",
        "для",
        "при",
        "над",
        "под",
        "все",
        "или",
        "после",
        "перед",
        "если",
        "очень",
        "мне",
        "мой",
        "нам",
        "наш",
        "тоже",
        "уже",
    }
)

_WORD_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9_-]{3,}")


def _extract_keywords(prompt: str) -> set[str]:
    """Extract meaningful keywords from the user's prompt."""
    words = _WORD_RE.findall(prompt.lower())
    return {w for w in words if w not in _STOP_WORDS}


def _find_relevant_from_index(keywords: set[str]) -> list[str]:
    """Search index.md for keyword matches → return matching wiki filenames.

    WHY: Read ONE file (index.md) instead of N files — O(1) vs O(N).
    Karpathy pattern: index as navigation map, not full-text grep.
    """
    if not WIKI_INDEX.exists() or not keywords:
        return []
    try:
        lines = WIKI_INDEX.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []

    matches: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if any(kw in line.lower() for kw in keywords):
            for title in re.findall(r"\[\[([^\]]+)\]\]", line):
                if title not in seen:
                    seen.add(title)
                    matches.append(title)
    return matches[:MAX_ARTICLES]


def _title_to_path(title: str) -> Path | None:
    """Find the wiki file for a given title string.

    WHY: index.md stores display titles like "AUC Red Flags", but files
    are named "2026-04-12_auc_red_flags.md". We match by slug comparison.
    """
    if not WIKI_DIR.exists():
        return None
    slug = re.sub(r"[^\w]", "_", title.lower()).strip("_")
    for f in WIKI_DIR.glob("*.md"):
        if f.name == "index.md":
            continue
        fstem = f.stem.lower()
        # Remove date prefix (YYYY-MM-DD_) if present
        fstem_no_date = re.sub(r"^\d{4}-\d{2}-\d{2}_", "", fstem)
        # WHY: only slug-in-filename direction. Reverse (fstem_no_date in slug)
        # causes false matches — "hooks" matches "how_session_hooks_work".
        if slug == fstem_no_date or slug in fstem_no_date:
            return f
    return None


def _format_articles(titles: list[str]) -> str:
    """Read matched wiki articles and format as injection context."""
    parts: list[str] = []
    total = 0

    for title in titles:
        path = _title_to_path(title)
        if path is None:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        if len(content) > MAX_ARTICLE_CHARS:
            content = content[:MAX_ARTICLE_CHARS] + "\n...(truncated)"

        entry = f"### [[{title}]]\n\n{content}"
        if total + len(entry) > MAX_CONTEXT_CHARS:
            break
        parts.append(entry)
        total += len(entry)

    if not parts:
        return ""
    return "## Relevant wiki articles\n\n" + "\n\n---\n\n".join(parts)


def main() -> None:
    data = parse_stdin()
    prompt = data.get("prompt", "")

    if len(prompt) < MIN_PROMPT_LEN:
        return

    keywords = _extract_keywords(prompt)
    if not keywords:
        return

    titles = _find_relevant_from_index(keywords)
    if not titles:
        return

    context = _format_articles(titles)
    if not context:
        return

    emit_hook_result("UserPromptSubmit", context)


if __name__ == "__main__":
    hook_main(main)
