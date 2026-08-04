#!/usr/bin/env python3
"""PostToolUse(Write|Edit) hook: retro-scan active PROMOTE claims on a new NULL.

WHY: research-methodology.md principle 5 ("немедленный ретроскан") — a new NULL
result must be applied to ALL existing claims immediately, not deferred. The
existing null_results_pre_check.py guards the INPUT (re-proposing a killed idea);
this guards the opposite direction: when a NEW null is recorded, which already
PROMOTED claims might now rest on the just-falsified ground?

Without this, the claim chain ages silently (error type 4: "лаг обновления").

Fires on: Write|Edit to **/null_results/INDEX.md.
Soft nudge via additionalContext (never blocks). Silent when no overlap.

Algorithm:
  1. Extract slug(s) of the NEW null entry (from new_string on Edit, or the last
     data row on full Write).
  2. Tokenize the new slug (words + alphanumeric identifiers, see _identifiers).
  3. Scan every experiments/*/decision.md marked [x] PROMOTE; tokenize its claim.
  4. Scan paper/ and manuscript/ deliverables, per .tex section (see _scan_deliverables).
  5. Warn where the weighted overlap reaches MATCH_THRESHOLD (see _overlap_score).

Extended 2026-08-04 (steps 2, 4, 5). Motivating incident, Buckholtz audit: a
provenance finding retracted the *subject* of several published results; the
write-up went on asserting them under the old frame for 12 days because every
artifact in the project sat behind a gate except the write-up itself. Measured
against that repo's 5 most recent NULLs the extension fires 3 times, all true
positives; against 3 deliberately unrelated slugs it stays silent. The identifier
work exists because the alpha-only tokenizer could not see `7:9:17` at all — the
subject of one of those very NULLs — and its silence was indistinguishable from
"no dependency".
"""

import json
import os
import re
import sys
from pathlib import Path

MIN_TOKEN_LEN = 4
MATCH_THRESHOLD = 2
# WHY separate, shorter floor: see _identifiers.__doc__ — `a1`, `n5` are
# distinctive *because* they are short; MIN_TOKEN_LEN would erase them.
IDENT_MIN_LEN = 2

# Deliverables scanned alongside experiments/. Self-scoping: absent dir → skipped,
# so projects without a paper/ see no behaviour change.
DELIVERABLE_DIRS = ("paper", "manuscript")
DELIVERABLE_SUFFIXES = (".tex", ".md")

# WHY: generic words that would create spurious overlaps between unrelated claims.
STOPWORDS = {
    "this",
    "that",
    "with",
    "from",
    "test",
    "null",
    "result",
    "results",
    "claim",
    "experiment",
    "hypothesis",
    "гипотеза",
    "результат",
    "тест",
    "эксперимент",
    "via",
    "using",
    "does",
    "have",
}


def _is_null_index(file_path: str) -> bool:
    """Return True if the path is a null_results/INDEX.md file."""
    p = Path(file_path)
    return p.name == "INDEX.md" and "null_results" in set(p.parts)


def _identifiers(text: str) -> set[str]:
    """Alphanumeric and ratio identifiers that _tokenize's alpha-only pattern drops.

    WHY (2026-08-04): the alpha-only tokenizer silently erases exactly the terms
    research projects name their subjects with — `Eq.32`, `7:9:17`, `Table A1`,
    `N=5`, `H1e`, `R011`. Measured on 5 real NULL slugs: `79-17-rg-boundary-
    condition` reduced to {boundary, condition}, so a paper actively discussing
    7:9:17 drew silence. Silence read as "no dependency" when it meant "cannot
    see". These carry their own shorter length floor because an identifier like
    `a1` is distinctive precisely by being short, unlike a 2-letter word.
    """
    low = text.lower()
    found = set()
    # letter+digit mixes in either order: eq32, a1, n5, h1e, r011, 4d
    found |= set(re.findall(r"\b(?:[a-z]+\d+[a-z\d]*|\d+[a-z]+[a-z\d]*)\b", low))
    # Separated numeric groups, normalised to a digits-only key so that the same
    # subject matches across the notations a project actually uses: a paper writes
    # `7:9:17`, its null_results slug compresses it to `79-17`, LaTeX renders it
    # `$7\!:\!9\!:\!17$` — all three collapse to `7917`. The >=4-digit floor keeps
    # incidental ranges (`1-2`, `z=3-5`) out; bare numbers never become tokens at all.
    cleaned = re.sub(r"\\[!,;:> ]", "", low)
    for match in re.findall(r"\b\d+(?:[:\-–]\d+)+\b", cleaned):
        digits = re.sub(r"[^0-9]", "", match)
        if len(digits) >= 4:
            found.add(f"num:{digits}")
    return {t for t in found if len(t) >= IDENT_MIN_LEN and t not in STOPWORDS}


def _tokenize(text: str) -> set[str]:
    """Lowercase alpha tokens of meaningful length, plus alphanumeric identifiers."""
    raw = re.findall(r"[a-zа-яё]+", text.lower())
    words = {t for t in raw if len(t) >= MIN_TOKEN_LEN and t not in STOPWORDS}
    return words | _identifiers(text)


def _slug_from_row(row: str) -> str | None:
    """Extract the slug column from a null_results table row: | id | date | slug | ... |."""
    if not row.strip().startswith("|") or "---" in row:
        return None
    parts = [p.strip() for p in row.strip().strip("|").split("|")]
    if len(parts) < 3 or parts[0].lower() in ("id", ""):
        return None
    return parts[2]


def _new_slugs(content: str, new_string: str) -> list[str]:
    """Determine the slug(s) of the just-added null entry.

    On Edit we get new_string (the inserted text) — parse all rows there.
    On full Write we only have content — take the last data row (most recent).
    """
    slugs: list[str] = []
    if new_string:
        for line in new_string.splitlines():
            slug = _slug_from_row(line)
            if slug:
                slugs.append(slug)
    if slugs:
        return slugs
    # Fallback: last data row of the full file.
    last = None
    for line in content.splitlines():
        slug = _slug_from_row(line)
        if slug:
            last = slug
    return [last] if last else []


def _repo_root(index_path: str) -> Path:
    """null_results/INDEX.md → repo root (parent of null_results/)."""
    return Path(index_path).resolve().parent.parent


def _claim_tokens(exp_dir: Path) -> set[str]:
    """Tokens describing the claim — from claim.md if present, else decision.md rationale."""
    claim_md = exp_dir / "claim.md"
    if claim_md.exists():
        try:
            return _tokenize(claim_md.read_text(encoding="utf-8"))
        except OSError:
            pass
    decision = exp_dir / "decision.md"
    if decision.exists():
        try:
            text = decision.read_text(encoding="utf-8")
            # Use the experiment id line + rationale only (avoid template noise).
            head = "\n".join(text.splitlines()[:3])
            return _tokenize(head)
        except OSError:
            pass
    return set()


def _has_promote(text: str) -> bool:
    return bool(re.search(r"\[x\]\s*PROMOTE", text, re.IGNORECASE))


def _scan_active_promotes(root: Path, slug_tokens: set[str]) -> list[tuple[str, list[str]]]:
    """Return (experiment_id, overlap) for PROMOTE claims overlapping the new slug."""
    matches: list[tuple[str, list[str]]] = []
    exp_root = root / "experiments"
    if not exp_root.is_dir():
        return matches
    for decision in exp_root.glob("*/decision.md"):
        try:
            text = decision.read_text(encoding="utf-8")
        except OSError:
            continue
        if not _has_promote(text):
            continue
        overlap = slug_tokens & _claim_tokens(decision.parent)
        if _overlap_score(overlap) >= MATCH_THRESHOLD:
            matches.append((decision.parent.name, sorted(overlap)))
    return matches


def _tex_sections(text: str) -> list[tuple[str, str]]:
    """Split a .tex body into (section title, body) pairs; whole file if unsectioned.

    The pre-first-section chunk is kept, not discarded: in a paper that region holds
    the title and abstract, i.e. the most load-bearing claims in the document. Dropping
    it was a real miss caught in testing — main.tex states its headline results there.
    """
    normalised = text.replace("\\subsection{", "\\section{")
    chunks = normalised.split("\\section{")
    if len(chunks) == 1:
        return [("", text)]
    out = [("(title/abstract)", chunks[0])]
    out += [(c.split("}")[0][:60], c) for c in chunks[1:]]
    return out


def _is_strong(token: str) -> bool:
    """A token naming a specific subject (Eq.32, 7:9:17, H1e) rather than describing it.

    Such a token is worth more than a shared common word: when two texts both say
    `eq32`, they are about the same object, whereas two texts sharing `boundary` may
    not be. Weighted accordingly in _overlap_score. Calendar-shaped numbers are
    excluded — a shared date says nothing about a shared subject.
    """
    if token.startswith("num:"):
        digits = token[4:]
        if len(digits) == 8 and digits[:2] in ("19", "20"):
            return False  # yyyymmdd
        return True
    return bool(re.search(r"\d", token))


def _overlap_score(overlap: set[str]) -> int:
    """Threshold score: identifiers count double, plain words count once."""
    return sum(2 if _is_strong(t) else 1 for t in overlap)


def _scan_deliverables(root: Path, slug_tokens: set[str]) -> list[tuple[str, list[str]]]:
    """Return (location, overlap) for paper/manuscript text overlapping the new slug.

    WHY (2026-08-04): every other artifact in a Full-Ladder project sits behind a
    gate — promotion, reject, retroscan — but the write-up sits behind none, so it
    ages by hand and silently. Observed in the Buckholtz audit: finding B0 landed
    2026-08-03 and retracted the *subject* of several results; paper/main.tex was
    last revised 2026-07-22 and kept presenting them under the old frame for 12
    days. Nothing flagged it. Measured on that repo's 5 most recent NULLs this
    scan fired twice, both true positives, zero false positives.
    """
    matches: list[tuple[str, list[str]]] = []
    for dirname in DELIVERABLE_DIRS:
        ddir = root / dirname
        if not ddir.is_dir():
            continue  # self-scoping: no deliverable dir → no behaviour change
        for path in sorted(ddir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in DELIVERABLE_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            if path.suffix.lower() == ".tex":
                for title, body in _tex_sections(text):
                    overlap = slug_tokens & _tokenize(body)
                    if _overlap_score(overlap) >= MATCH_THRESHOLD:
                        where = f"{rel} § {title}" if title else rel
                        matches.append((where, sorted(overlap)))
            else:
                overlap = slug_tokens & _tokenize(text)
                if _overlap_score(overlap) >= MATCH_THRESHOLD:
                    matches.append((rel, sorted(overlap)))
    return matches


def main() -> None:
    # WHY: recursion guard — this hook reads the filesystem.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    if data.get("tool_name", "") not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path or not _is_null_index(file_path):
        sys.exit(0)

    content = tool_input.get("content", "")
    new_string = tool_input.get("new_string", "")
    if not content and not new_string:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            sys.exit(0)

    slugs = _new_slugs(content, new_string)
    if not slugs:
        sys.exit(0)

    root = _repo_root(file_path)
    all_matches: dict[str, list[str]] = {}
    paper_matches: dict[str, list[str]] = {}
    triggering_slug = ""
    for slug in slugs:
        slug_tokens = _tokenize(slug)
        if not slug_tokens:
            continue
        for exp_id, overlap in _scan_active_promotes(root, slug_tokens):
            if exp_id not in all_matches:
                all_matches[exp_id] = overlap
                triggering_slug = slug
        for where, overlap in _scan_deliverables(root, slug_tokens):
            if where not in paper_matches:
                paper_matches[where] = overlap
                triggering_slug = triggering_slug or slug

    if not all_matches and not paper_matches:
        sys.exit(0)  # silent — no dependency, no noise

    blocks = []
    if all_matches:
        blocks.append(
            "Active PROMOTE claims:\n"
            + "\n".join(
                f"  • {exp_id} (shared: {', '.join(ov)})"
                for exp_id, ov in sorted(all_matches.items())
            )
        )
    if paper_matches:
        blocks.append(
            "Write-up passages (subject may now be stale):\n"
            + "\n".join(
                f"  • {where} (shared: {', '.join(ov)})"
                for where, ov in sorted(paper_matches.items())
            )
        )
    msg = (
        f"[null-retroscan] ⚠️  New NULL '{triggering_slug}' may undercut:\n"
        + "\n\n".join(blocks)
        + "\n\n→ Principle 5 (immediate retroscan): re-check whether these depend on "
        "the just-falsified ground before trusting them. A write-up hit often means the "
        "*subject* of a sentence changed, not its arithmetic."
    )

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": msg,
                }
            }
        )
    )


if __name__ == "__main__":
    main()
