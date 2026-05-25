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

import functools
import os
import re
import sys
from datetime import date
from pathlib import Path

import cogniml_client
import vector_store
from utils import (
    emit_hook_result,
    find_project_memory,
    hook_main,
    parse_stdin,
    redact_secrets,
)

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


@functools.lru_cache(maxsize=512)
def _score_entry(title: str) -> float:
    """Attention decay score: 70% recency + 30% frequency. Cached per title within a session.

    WHY: keyword matching returns entries in index order — old entries rank
    equally with fresh ones. Attention decay mirrors human memory: recent
    lessons surface first, frequently-hit patterns stay relevant longer.
    Half-life = 14 days. [×N] counter boosts score up to +0.3.
    lru_cache is safe here because wiki files don't change during a single session.
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


def _query_wiki_raw_titles(keywords: list[str], top_n: int = 10) -> list[str]:
    """Return raw wiki titles (no [[]] wrapping) matching keywords, scored.

    WHY: separate from _query_wiki because the tiered renderer needs RAW
    titles to look up file content for HOT-tier snippet rendering. Existing
    _query_wiki returns top-3 wrapped strings — sufficient for legacy
    inject path, insufficient for tier-based selection that needs more
    candidates to choose from. No semantic-search supplement here: tiered
    pipeline already classifies by keyword overlap explicitly.
    """
    if not WIKI_DIR.exists() or not keywords:
        return []

    if WIKI_INDEX.exists():
        try:
            index_text = WIKI_INDEX.read_text(encoding="utf-8", errors="ignore")
            index_lines = index_text.splitlines()
            index_lines_lower = index_text.lower().splitlines()
            matches: list[str] = []
            for orig_line, low_line in zip(index_lines, index_lines_lower, strict=True):
                if any(kw in low_line for kw in keywords):
                    found = re.findall(r"\[\[([^\]]+)\]\]", orig_line)
                    matches.extend(found)
            if matches:
                seen: set[str] = set()
                unique: list[str] = []
                for m in matches:
                    if m not in seen:
                        seen.add(m)
                        unique.append(m)
                unique.sort(key=_score_entry, reverse=True)
                return unique[:top_n]
        except OSError:
            pass

    # Fallback: full scan when index is missing.
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
    scan_matches.sort(key=_score_entry, reverse=True)
    return scan_matches[:top_n]


def _query_patterns(keywords: list[str]) -> list[str]:
    """Return [AVOID] pattern lines matching any keyword, filtered by severity.

    WHY: patterns.md now has [CRITICAL]/[HIGH]/[LOW] severity tags.
    Injecting all 35+ patterns creates noise. Only [CRITICAL] + [HIGH]
    surface by default — [LOW] shown only when nothing higher matches.
    """
    if not PATTERNS_PATH.exists() or not keywords:
        return []
    try:
        content = PATTERNS_PATH.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    critical: list[str] = []
    high: list[str] = []
    low: list[str] = []

    for line in content.splitlines():
        # WHY: match both [AVOID] (old format) and [AVOID×N] (new severity format)
        if "AVOID" not in line and "[×" not in line:
            continue
        if not any(kw in line.lower() for kw in keywords):
            continue
        clean = line.strip().lstrip("- ").strip()
        if "[CRITICAL]" in line:
            critical.append(f"  ⚠ [CRITICAL] {clean[:120]}")
        elif "[HIGH]" in line:
            high.append(f"  ⚠ [HIGH] {clean[:120]}")
        else:
            low.append(f"  ⚠ {clean[:120]}")

    # WHY: show highest severity first; fall back to low only if nothing else found
    results = critical + high
    if not results:
        results = low
    return results[:3]


def _top_avoid_patterns(limit: int = 5) -> list[str]:
    """Return top-N [AVOID] patterns sorted by severity then recurrence.

    WHY: [CRITICAL] patterns always surface first regardless of count.
    Previously sorted only by [×N] count — a [CRITICAL] pattern with
    [×1] was buried below [LOW] patterns with [×3]. Severity now takes
    priority: CRITICAL(1000) > HIGH(100) > no-tag(1) + count.
    """
    _SEVERITY_WEIGHT = {"CRITICAL": 1000, "HIGH": 100}

    if not PATTERNS_PATH.exists():
        return []
    try:
        content = PATTERNS_PATH.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    scored: list[tuple[int, str]] = []
    for line in content.splitlines():
        if "[AVOID]" not in line:
            continue
        m = re.search(r"\[×(\d+)\]", line)
        count = int(m.group(1)) if m else 1

        severity = "LOW"
        if "[CRITICAL]" in line:
            severity = "CRITICAL"
        elif "[HIGH]" in line:
            severity = "HIGH"

        score = _SEVERITY_WEIGHT.get(severity, 1) + count
        prefix = f"[{severity}] " if severity != "LOW" else ""
        clean = line.strip().lstrip("- #").strip()[:120]
        scored.append((score, f"  ⚠ {prefix}[×{count}] {clean}"))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in scored[:limit]]


# --- HOT/WARM/COLD attention decay layer -----------------------------------
# WHY: existing wiki injection only emits `[[Title]]` references — Claude has
# to open each file manually. For high-relevance entries that wastes tool
# calls. The tiered renderer below classifies entries by combined score
# (keyword overlap × recency × frequency) and inlines the top hits so they
# enter context immediately. Below threshold = COLD (excluded entirely).
#
# Pattern adopted from Claude Cognitive (HOT/WARM/COLD attention scoring).
# Our prior implementation only had recency + frequency; adding keyword
# overlap finishes the trio that was the documented gap from the external
# Claude Code architecture audit (2026-05-06).
#
# Budget caps below derived from Claude Code context window math:
# - HOT_MAX_CHARS=300 × 5 entries = 1500 chars HOT injection
# - WARM is title-only references = ~30 chars × 8 = 240 chars
# Total ~1750 chars worst case, well below 25k injection ceiling.

HOT_THRESHOLD = 0.65
WARM_THRESHOLD = 0.35
HOT_MAX_CHARS = 300
HOT_BUDGET_CHARS = 1500  # ~5 HOT entries
WARM_MAX_ENTRIES = 8
TIER_CANDIDATE_LIMIT = 10  # cap I/O — never read more than 10 wiki files per session


def _keyword_overlap_score(content_lower: str, keywords: list[str]) -> float:
    """Fraction of keywords present in content (0.0–1.0).

    WHY: existing scan already filtered for ANY keyword match (binary). For
    tier classification we need the strength of match — entries hitting 5/5
    keywords should rank above ones hitting 1/5 even with same recency.
    """
    if not keywords:
        return 0.0
    hits = sum(1 for kw in keywords if kw in content_lower)
    return hits / len(keywords)


def _full_relevance_score(title: str, content_lower: str, keywords: list[str]) -> float:
    """Combined relevance: 50% keyword overlap + 50% recency/frequency mix.

    WHY: keyword overlap dominates because a stale-but-exact-match entry is
    more useful than a fresh-but-tangential one. _score_entry already
    returns the recency × frequency blend (0..1).
    """
    keyword_part = _keyword_overlap_score(content_lower, keywords)
    base_part = _score_entry(title)
    return 0.5 * keyword_part + 0.5 * base_part


def _classify_tier(score: float) -> str:
    """HOT (full snippet) / WARM (title ref) / COLD (excluded)."""
    if score >= HOT_THRESHOLD:
        return "HOT"
    if score >= WARM_THRESHOLD:
        return "WARM"
    return "COLD"


# WHY: read_text size cap. 256 KB is ~50× normal wiki entry — a single
# entry larger than that is either malformed or hostile. Without this cap
# a 1 GB poisoned wiki file would OOM the SessionStart hook (sec-auditor
# finding L3, PR #106 review).
_MAX_WIKI_FILE_BYTES = 256_000


def _is_safe_wiki_path(path: Path) -> bool:
    """Return True only when path stays inside WIKI_DIR after resolution.

    WHY: the stem fed to _read_wiki_content originates from `[[...]]`
    matches inside index.md (line 270 of this file). If a future writer
    of index.md ever accepts external input — URL titles, MCP responses,
    paste from email — a stem like `../../../etc/passwd` (or Windows
    equivalent) would let WIKI_DIR / f"{stem}.md" escape the boundary
    and leak arbitrary `*.md` files into the SessionStart context.
    Closes sec-auditor finding H2 from PR #106 review with deterministic
    exploit chain. Boundary check via resolve() + relative_to handles
    both `..` traversal and symlink escape (L1).
    """
    try:
        # WIKI_DIR may not yet exist in early test fixtures; resolve() still
        # works on non-existent paths in 3.11+ (returns canonical absolute).
        wiki_root = WIKI_DIR.resolve()
        candidate = path.resolve()
        candidate.relative_to(wiki_root)
        return True
    except (ValueError, OSError):
        return False


def _read_wiki_content(stem: str) -> str | None:
    """Read wiki entry by stem, stripping frontmatter. None if not found,
    if the path escapes WIKI_DIR, or if the file is suspiciously large.

    Defense in depth (PR #106 sec-audit):
    - Reject obviously hostile stems (path separators, NUL, ..) before any I/O
    - resolve() + relative_to(WIKI_DIR) boundary check on the final path
    - 256 KB size cap on read_text()
    """
    # Cheap stem sanity check before any path math. WHY: most attacks
    # show up here long before resolve() is needed; failing fast keeps
    # filesystem traffic minimal under abusive index.md.
    if not stem or any(ch in stem for ch in ("/", "\\", "\x00")) or ".." in stem:
        return None

    file_path = WIKI_DIR / f"{stem}.md"
    if not file_path.exists():
        # Try PARA subdirs (projects/areas/resources/archives) as a fallback.
        # WHY: session_save can route entries to PARA folders; bare WIKI_DIR
        # lookup misses those. Cap at 4 candidates — not a full glob.
        for sub in ("projects", "areas", "resources", "archives"):
            candidate = WIKI_DIR / sub / f"{stem}.md"
            if candidate.exists():
                file_path = candidate
                break
        else:
            return None

    # WHY: even after stem sanitisation, resolve() + relative_to is the
    # authoritative check — covers symlinks, OS-specific quirks, and
    # double-encoded inputs the cheap check might miss.
    if not _is_safe_wiki_path(file_path):
        return None

    try:
        # WHY: cap before read to prevent OOM on hostile / corrupted entries.
        if file_path.stat().st_size > _MAX_WIKI_FILE_BYTES:
            return None
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    # Strip frontmatter so the snippet starts at real content.
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            text = text[end + 3 :].lstrip()
    return text


def _render_hot(title: str, content: str) -> str:
    """HOT tier: title + ~300 char snippet, single line for easy injection.

    Snippet runs through redact_secrets() before injection. WHY: HOT entries
    enter Claude's SessionStart context verbatim. Wiki files are auto-
    populated from session memory and may contain secrets pasted into
    earlier sessions (env dumps, error tracebacks with API keys). Without
    redaction those would land in every subsequent session's context and
    leak into screenshots / logs / audit. Closes sec-auditor finding H1
    from PR #106 review.

    Note: redact_secrets is defense in depth — the primary defense is
    input_guard / sanitize layers upstream that prevent secrets from
    reaching wiki in the first place. This is the last line.
    """
    safe_content = redact_secrets(content)
    snippet = safe_content[:HOT_MAX_CHARS].replace("\n", " ").strip()
    if len(safe_content) > HOT_MAX_CHARS:
        snippet += " …"
    return f"  🔥 [[{title}]] — {snippet}"


def _render_warm(title: str) -> str:
    """WARM tier: title-only reference, identical to legacy format."""
    return f"  📑 [[{title}]]"


def _classify_and_render_wiki(
    candidate_titles: list[str], keywords: list[str]
) -> tuple[list[str], list[str]]:
    """Classify candidate wiki titles into HOT/WARM tiers and render each.

    Args:
        candidate_titles: titles already filtered by keyword presence in index.
        keywords: extracted keywords from current focus, for overlap scoring.

    Returns:
        (hot_lines, warm_lines) — each pre-rendered for injection. COLD
        entries are excluded entirely. HOT respects HOT_BUDGET_CHARS;
        overflow demoted to WARM. WARM truncated to WARM_MAX_ENTRIES.
    """
    if not candidate_titles or not keywords:
        return [], []

    scored: list[tuple[float, str, str | None]] = []
    for title in candidate_titles[:TIER_CANDIDATE_LIMIT]:
        stem = title.split("|")[0].strip()
        content = _read_wiki_content(stem)
        if content is None:
            # Cannot read → fall back to score without keyword overlap (recency only).
            scored.append((_score_entry(title) * 0.5, title, None))
            continue
        score = _full_relevance_score(title, content.lower(), keywords)
        scored.append((score, title, content))

    # Highest score first. Budget cap on HOT so a single huge entry can't
    # eat the whole window.
    scored.sort(key=lambda x: x[0], reverse=True)

    hot_lines: list[str] = []
    warm_lines: list[str] = []
    hot_used_chars = 0

    for score, title, content in scored:
        # WHY: every candidate already passed the keyword filter in
        # _query_wiki_raw_titles, so it is keyword-relevant by definition.
        # Only the HOT promotion needs to clear the score threshold —
        # everything else lands in WARM, never COLD. Pure _classify_tier()
        # is the right model for ranking, but orchestration treats the
        # candidate list as the floor (no double-filter).
        if score >= HOT_THRESHOLD and content is not None:
            line = _render_hot(title, content)
            if hot_used_chars + len(line) > HOT_BUDGET_CHARS:
                # Demote HOT overflow to WARM rather than dropping silently.
                warm_lines.append(_render_warm(title))
                continue
            hot_lines.append(line)
            hot_used_chars += len(line)
        else:
            warm_lines.append(_render_warm(title))

    return hot_lines, warm_lines[:WARM_MAX_ENTRIES]


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
    # WHY: prevent recursion when this hook fires inside a subagent's
    # SessionStart/etc — see hooks/CLAUDE.md "Recursion guard" section.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    # WHY: parse_stdin returns the full hook payload — Claude Code v2.1.141+ includes
    # `effort.level` ("low"|"medium"|"high") so hooks can scale work to user intent.
    # On `low` effort we skip the full HOT/WARM render to keep the session lean;
    # on `high` we surface more candidates than the default.
    payload = parse_stdin() or {}
    effort_level = (payload.get("effort") or {}).get("level", "medium")
    if effort_level == "low":
        # Skip injection entirely — user signalled minimal context overhead.
        sys.exit(0)

    focus = _read_current_focus()
    if not focus.strip():
        sys.exit(0)

    keywords = _extract_keywords(focus)
    if not keywords:
        sys.exit(0)

    # WHY: tiered path — pull more candidates (up to 10) and classify each
    # into HOT (full snippet inlined) / WARM (title-only ref) / COLD (skip).
    # _query_wiki_raw_titles is a separate gather — it does NOT semantic-
    # supplement, because tier scoring already weighs keyword overlap.
    candidate_titles = _query_wiki_raw_titles(keywords, top_n=TIER_CANDIDATE_LIMIT)
    hot_lines, warm_lines = _classify_and_render_wiki(candidate_titles, keywords)

    keyword_patterns = _query_patterns(keywords)
    top_avoids = _top_avoid_patterns(5)
    best = _best_approach()
    index_topics = _read_index_topics()

    parts: list[str] = []
    # WHY: show knowledge map first — agent knows what exists before grepping.
    if index_topics:
        parts.append(f"🗺 Knowledge base: {index_topics}")
    # WHY: HOT/WARM split mirrors Claude Cognitive attention pattern.
    # HOT entries inline content so the agent doesn't need to open files;
    # WARM listed as references in case they're needed but no budget burn.
    if hot_lines:
        parts.append("🔥 High-relevance knowledge (inlined):\n" + "\n".join(hot_lines))
    if warm_lines:
        parts.append("📑 Related (open if useful): " + ", ".join(warm_lines).strip())
    if not hot_lines and not warm_lines and focus:
        # Semantic fallback only when no keyword-matched entries surfaced at all.
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
