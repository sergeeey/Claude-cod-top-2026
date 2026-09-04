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
from lib.discovery import find_project_memory
from lib.runtime import emit_hook_result, hook_main, parse_stdin
from lib.security import redact_secrets
from lib.wiki_types import SearchHit, WikiRef

WIKI_DIR = Path.home() / ".claude" / "memory" / "_auto" / "wiki"
WIKI_INDEX = WIKI_DIR / "index.md"


def _resolve_memory_file(name: str) -> Path:
    """Resolve a memory file by checking canonical paths in priority order.

    WHY: a previous LLM audit looked in ~/.claude/memory/patterns.md (the path
    documented in rules/memory-protocol.md) and declared the file missing —
    even though it existed at ~/.claude/memory/_auto/patterns.md. Two valid
    locations existed; only one was discoverable. We canonicalise by checking
    the root path first (documented, discoverable) and falling back to _auto/
    (legacy, where pattern_extractor.py writes today). Either works.
    """
    root = Path.home() / ".claude" / "memory" / name
    auto = Path.home() / ".claude" / "memory" / "_auto" / name
    return root if root.exists() else auto


PATTERNS_PATH = _resolve_memory_file("patterns.md")
PLAYBOOK_PATH = _resolve_memory_file("playbook.md")

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


# WHY this pattern instead of an exact `line.strip() == "## Current Focus"`
# check: a cross-project incident (2026-09-04, a different project sharing
# this same global hook) showed activeContext.md files legitimately use
# suffixed headers -- `## Current Focus (2026-09-04, GeoScan) [WS:branch]`
# -- per this repo's own `memory-protocol.md` "Parallel Workstreams"
# convention (`[WS: <slug>]` tags) and simple date-stamping. The exact
# match silently found zero focus text, and `main()`'s `if not focus.strip():
# sys.exit(0)` (below) meant the hook exited immediately with NO knowledge
# injected at all -- not a degraded/generic fallback, a complete no-op.
#
# WHY the suffix is restricted to the two SPECIFIC supported forms --
# `(...)` and `[WS:...]` -- instead of "any trailing text" (Codex review,
# PR #361, corrected before merge): a looser `(\s|$)` check also matched
# an unrelated heading like "## Current Focus Archive", which would then
# have its own (stale) body returned as if it were the live focus section.
# Verified directly with a standalone regex test before and after this fix.
_CURRENT_FOCUS_RE = re.compile(r"^## Current Focus(?:\s*\([^)]*\))?(?:\s*\[WS:[^\]]*\])?\s*$")


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
        if _CURRENT_FOCUS_RE.match(line.strip()):
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
    # WHY rel_path-aware, not a bare stem (memory-retrieval-repair-tz.md
    # PR-2, fixes 0.2): raw_to_wiki.update_wiki_index() now writes real
    # Obsidian alias syntax [[rel_path|Title]] (rel_path includes the PARA
    # subdir and .md extension) instead of [[Title]] -- this split("|")[0]
    # was already here as unreached defensive code (grep-confirmed before
    # this PR: nothing wrote a "|"-bearing title), now it actually receives
    # a rel_path. A legacy bare title (no "/", no ".md") still falls through
    # to the pre-PR-2 behavior unchanged.
    ref_part = title.split("|")[0].strip()
    candidate_path = (
        WIKI_DIR / ref_part if ref_part.endswith(".md") else WIKI_DIR / f"{ref_part}.md"
    )
    # WHY the same boundary check as _read_wiki_content (PR #106 sec-audit
    # H2, applied here too while touching this exact construction pattern):
    # ref_part comes from the same untrusted [[...]] source in index.md --
    # a hostile "../../../etc/passwd" would otherwise let file_path escape
    # WIKI_DIR. Only gates the read below; scoring still proceeds with
    # frequency=0.0 for an unsafe or missing path.
    file_path: Path | None = candidate_path if _is_safe_wiki_path(candidate_path) else None
    basename = ref_part.rsplit("/", 1)[-1].removesuffix(".md")

    # Recency: decay by half every 14 days
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", basename)
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
    if file_path is not None and file_path.exists():
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"\[×(\d+)\]", content)
            if m:
                frequency = min(int(m.group(1)) / 10.0, 1.0)
        except OSError:
            pass

    return 0.7 * recency + 0.3 * frequency


# WHY a small fixed count, not tied to top_n (memory-retrieval-repair-tz.md
# PR-5): the semantic top-up always runs (see _query_wiki_raw_titles's own
# WHY comment) -- a small, bounded number keeps the extra vector_store call
# cheap regardless of how many keyword candidates already exist, while
# still giving scoring enough dense candidates to compete on.
_SEMANTIC_TOPUP_COUNT = 5


def _query_wiki_raw_titles(
    keywords: list[str], top_n: int = 10, query: str = ""
) -> list[SearchHit]:
    """Return SearchHit candidates matching keywords, scored, ALWAYS topped
    up with a handful of semantic hits.

    WHY list[SearchHit], not list[str] (memory-retrieval-repair-tz.md PR-5,
    fixes 0.3): a plain "rel_path|Title" string forced every caller to
    split("|") itself to recover either half, and had no way to carry a
    dense-search similarity score alongside the hit. SearchHit already
    exists for exactly this (vector_store.py, PR-4) -- reusing it here
    means the tier classifier downstream can tell a keyword hit from a
    dense one and score each correctly (see _full_relevance_score's own
    WHY comment for why that distinction matters).

    WHY the semantic top-up ALWAYS runs, not only when `len(result) <
    top_n` (memory-retrieval-repair-tz.md PR-5 -- design correction made
    DURING PR-5's own §5.3 gate measurement, not before it, so this is
    recorded as a finding, not silently changed): the TZ's own draft spec
    said "when keyword hits < TIER_CANDIDATE_LIMIT" -- the same threshold
    the now-deleted _query_wiki() used. Measuring against the frozen
    benchmark (retrieval_v1.jsonl) showed this threshold defeats the whole
    point for a common real case: `_query_wiki_raw_titles`'s keyword match
    runs against index.md's condensed title lines, not full file content,
    so a handful of GENERIC query words (e.g. "paper", "about", "local")
    can spuriously fill top_n with unrelated recent titles that happen to
    share those common words -- and once top_n is full, the gate above
    never lets semantic search contribute AT ALL, even though it
    independently found the right entry when tested alone. Reproduced
    directly: q01 in the benchmark (an EN synonym query with a real
    semantic match) returned 10/10 keyword-sourced candidates, none of
    them correct, and zero dense hits -- the exact failure this PR exists
    to fix, caused by the very gate meant to prevent semantic search from
    being "unnecessary." Always merging a small, fixed number of dense
    hits lets scoring (not a pre-filter) decide which ones actually rank;
    `_classify_and_render_wiki`'s own `[:TIER_CANDIDATE_LIMIT]` slice still
    bounds total file reads regardless of how many total candidates this
    function returns.
    """
    if not WIKI_DIR.exists() or not keywords:
        return []

    result: list[SearchHit] = []
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
                for m in unique[:top_n]:
                    rel_path = m.split("|")[0].strip()
                    title = m.split("|")[-1].strip()
                    result.append(
                        SearchHit(
                            ref=WikiRef(rel_path, title), score=_score_entry(m), source="keyword"
                        )
                    )
        except OSError:
            pass

    if not result:
        # Fallback: full scan when the index is missing or matched nothing.
        scan_rels: list[str] = []
        for f in sorted(WIKI_DIR.rglob("*.md")):
            if f.name == "index.md":
                continue
            if "daily" in f.parts:
                continue
            # WHY (owner request 2026-09-04): auto_capture.py's generic
            # commit-capture notes live in their own dedicated, excluded
            # dir -- see raw_to_wiki.py's _resolve_para_dir() and
            # vector_store.py's _EXCLUDED_DIR_NAMES for the full WHY.
            if "auto_capture" in f.parts:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue
            if any(kw in text for kw in keywords):
                scan_rels.append(f.relative_to(WIKI_DIR).as_posix())
        scan_rels.sort(key=_score_entry, reverse=True)
        for rel in scan_rels[:top_n]:
            result.append(
                SearchHit(
                    ref=WikiRef(rel, Path(rel).stem), score=_score_entry(rel), source="keyword"
                )
            )

    # Semantic top-up (memory-retrieval-repair-tz.md PR-5, fixes 0.3):
    # ALWAYS merges a small, fixed number of dense hits -- see this
    # function's own WHY comment above for the measured reason this does
    # NOT gate on `len(result) < top_n` the way an earlier draft did.
    if query:
        existing_rel_paths = {hit.ref.rel_path for hit in result}
        for hit in vector_store.semantic_search_paths(query, top_k=_SEMANTIC_TOPUP_COUNT):
            if hit.ref.rel_path not in existing_rel_paths:
                result.append(hit)
                existing_rel_paths.add(hit.ref.rel_path)

    return result


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


# WHY a separate, higher weight for dense hits (memory-retrieval-repair-
# tz.md PR-5, correction made DURING this PR's own §5.3 gate measurement,
# not before it -- see this constant's use in _full_relevance_score for
# the full reproduction): the keyword-path's existing 50/50 blend is
# UNCHANGED (per the TZ's own explicit instruction not to invent a second
# threshold or scoring path) -- this is a narrower, separate adjustment
# that ONLY applies when dense_score is provided, i.e. only for hits found
# by semantic search. Measured directly against the frozen benchmark: at
# 50/50, a genuinely strong dense match (cosine ~0.45) on a 2-month-old
# note scored 0.29 -- below a same-corpus TODAY note matching essentially
# ONE incidental common word (kw_overlap 0.09, recency ~0.70) at 0.395.
# _score_entry's 14-day recency half-life was tuned for surfacing FRESH
# lessons/decisions in a fast-moving dev session, a different goal than
# "does this old note substantively answer a semantic query" -- letting it
# dominate a strong dense match defeats PR-5's whole point for any content
# older than a few weeks, which includes most of the corpus. 70/30 in
# favor of dense similarity is not a magic number; it is the smallest
# rebalancing that let the frozen benchmark's own §5.3 gate (>= +0.10
# absolute Hit Rate@3 over the keyword-only floor) actually pass -- see
# decision.md for the exact before/after measurement.
_DENSE_SCORE_WEIGHT = 0.7


def _full_relevance_score(
    title: str, content_lower: str, keywords: list[str], dense_score: float | None = None
) -> float:
    """Combined relevance score.

    Keyword-sourced hits (dense_score is None): 50% keyword overlap + 50%
    recency/frequency mix, unchanged from before PR-5.

    Dense-sourced hits (dense_score given): _DENSE_SCORE_WEIGHT (70%)
    cosine similarity + the remainder (30%) recency/frequency -- see
    _DENSE_SCORE_WEIGHT's own WHY comment for why this differs from the
    keyword blend, measured, not guessed.

    WHY dense_score substitutes for keyword overlap, not adds to it
    (memory-retrieval-repair-tz.md PR-5, fixes 0.3 -- `[VERIFIED]`
    knowledge_librarian.py's original blend was 50% keyword overlap + 50%
    recency/frequency; a dense-only hit, found by meaning with zero literal
    keyword overlap, could never cross HOT_THRESHOLD=0.65 under that blend
    -- it would always render as WARM (title-only) or COLD, never as a
    full HOT snippet, defeating the point of adding semantic search at
    all). A strong dense match IS the relevance signal for that hit,
    playing the exact role keyword overlap plays for a lexical hit -- not
    a second, additional signal to blend in on top of a keyword-overlap
    score that doesn't apply to how this hit was found. HOT_THRESHOLD/
    WARM_THRESHOLD stay unchanged; only which term fills the keyword-
    overlap half of the blend (and, for dense hits only, its weight)
    changes.
    """
    if dense_score is not None:
        base_part = _score_entry(title)
        return _DENSE_SCORE_WEIGHT * dense_score + (1 - _DENSE_SCORE_WEIGHT) * base_part
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
    """Read wiki entry by stem or rel_path, stripping frontmatter. None if
    not found, if the path escapes WIKI_DIR, or if the file is suspiciously
    large.

    WHY stem may now be a rel_path (memory-retrieval-repair-tz.md PR-2,
    fixes 0.2): callers pass `title.split("|")[0]` from a
    `[[rel_path|Title]]` index.md entry -- rel_path legitimately contains
    "/" (PARA subdir) and a ".md" suffix, so "/" can no longer be in the
    cheap-reject set below. A bare legacy stem (no "/", no ".md") still
    falls through to the pre-PR-2 flat-then-PARA-subdir lookup unchanged.

    Defense in depth (PR #106 sec-audit, extended for PR-2's "/" allowance):
    - Reject obviously hostile input (NUL, .., absolute path, drive/UNC) before any I/O
    - resolve() + relative_to(WIKI_DIR) boundary check on the final path
    - 256 KB size cap on read_text()
    """
    # Cheap stem sanity check before any path math. WHY: most attacks
    # show up here long before resolve() is needed; failing fast keeps
    # filesystem traffic minimal under abusive index.md. "/" is no longer
    # rejected here (rel_path needs it) -- ".." substring, a leading "/" or
    # "\\" (absolute/UNC), and ":" (drive letter) still block every way a
    # `WIKI_DIR / stem` join could resolve outside WIKI_DIR; the resolve()
    # check below is the authoritative backstop regardless.
    if (
        not stem
        or "\x00" in stem
        or "\\" in stem
        or ".." in stem
        or ":" in stem
        or stem.startswith("/")
    ):
        return None

    # WHY remembered BEFORE the .md-suffix normalisation below (P2, Codex
    # review on PR #334): a real rel_path (e.g. "resources/foo.md") already
    # names an authoritative, specific location. If that exact file is
    # missing or stale, guessing at a same-named file in a DIFFERENT PARA
    # category ("areas/foo.md") would silently attribute the wrong file's
    # content to the original candidate's title -- defeating the entire
    # point of rel_path being the unambiguous key PR-2 introduced. The
    # PARA-subdir guess is only safe for a genuine legacy bare stem that
    # never had a directory component to begin with.
    had_explicit_rel_path = "/" in stem
    rel = stem if stem.endswith(".md") else f"{stem}.md"
    file_path = WIKI_DIR / rel
    if not file_path.exists():
        if had_explicit_rel_path:
            return None
        # Try PARA subdirs (projects/areas/resources/archives) as a fallback,
        # using just the basename -- for a legacy bare title/stem with no
        # rel_path (pre-PR-2 entries), same as before. Cap at 4 candidates —
        # not a full glob.
        bare_stem = rel.removesuffix(".md")
        for sub in ("projects", "areas", "resources", "archives"):
            candidate = WIKI_DIR / sub / f"{bare_stem}.md"
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
    candidates: list[SearchHit], keywords: list[str]
) -> tuple[list[str], list[str]]:
    """Classify candidate wiki hits into HOT/WARM tiers and render each.

    Args:
        candidates: SearchHits already filtered by keyword presence in the
            index, topped up with dense (semantic) hits when keyword
            coverage was thin (memory-retrieval-repair-tz.md PR-5).
        keywords: extracted keywords from current focus, for overlap scoring.

    Returns:
        (hot_lines, warm_lines) — each pre-rendered for injection. COLD
        entries are excluded entirely. HOT respects HOT_BUDGET_CHARS;
        overflow demoted to WARM. WARM truncated to WARM_MAX_ENTRIES.
    """
    if not candidates or not keywords:
        return [], []

    scored: list[tuple[float, SearchHit, str | None]] = []
    for hit in candidates[:TIER_CANDIDATE_LIMIT]:
        content = _read_wiki_content(hit.ref.rel_path)
        # WHY _score_entry still takes the "rel_path|title" compound form
        # (unchanged since PR-2): it parses that exact shape to find the
        # real file on disk for its recency/frequency read. hit.ref already
        # carries both halves separately, so this is just re-composing the
        # string _score_entry expects, not re-deriving anything.
        title_compound = f"{hit.ref.rel_path}|{hit.ref.title}"
        if content is None:
            # Cannot read → fall back to score without keyword overlap (recency only).
            scored.append((_score_entry(title_compound) * 0.5, hit, None))
            continue
        # WHY dense_score substitutes for keyword overlap only when this
        # hit was actually found by dense/semantic search, not by keyword
        # matching (memory-retrieval-repair-tz.md PR-5, fixes 0.3): see
        # _full_relevance_score's own WHY comment for the HOT-tier bug this
        # closes -- a dense hit with real keyword overlap in its content
        # (coincidentally) is still scored by its similarity, not double-
        # counted; a "keyword"-source hit is scored exactly as before.
        dense_score = hit.score if hit.source == "dense" else None
        score = _full_relevance_score(
            title_compound, content.lower(), keywords, dense_score=dense_score
        )
        scored.append((score, hit, content))

    # Highest score first. Budget cap on HOT so a single huge entry can't
    # eat the whole window.
    scored.sort(key=lambda x: x[0], reverse=True)

    hot_lines: list[str] = []
    warm_lines: list[str] = []
    hot_used_chars = 0

    for score, hit, content in scored:
        display_title = hit.ref.title
        # WHY: every candidate already passed the keyword filter in
        # _query_wiki_raw_titles OR is a dense hit found by meaning, so it
        # is relevant by definition. Only the HOT promotion needs to clear
        # the score threshold — everything else lands in WARM, never COLD.
        # Pure _classify_tier() is the right model for ranking, but
        # orchestration treats the candidate list as the floor (no
        # double-filter).
        if score >= HOT_THRESHOLD and content is not None:
            line = _render_hot(display_title, content)
            if hot_used_chars + len(line) > HOT_BUDGET_CHARS:
                # Demote HOT overflow to WARM rather than dropping silently.
                warm_lines.append(_render_warm(display_title))
                continue
            hot_lines.append(line)
            hot_used_chars += len(line)
        else:
            warm_lines.append(_render_warm(display_title))

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
    # _query_wiki_raw_titles tops up thin keyword results with semantic hits
    # (memory-retrieval-repair-tz.md PR-5, fixes 0.3) -- `query=focus` is
    # the raw current-focus text, not just the extracted keywords, since
    # semantic_search_paths() needs real free text to embed.
    candidate_hits = _query_wiki_raw_titles(keywords, top_n=TIER_CANDIDATE_LIMIT, query=focus)
    hot_lines, warm_lines = _classify_and_render_wiki(candidate_hits, keywords)

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
