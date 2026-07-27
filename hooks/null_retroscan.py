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
  2. Tokenize the new slug.
  3. Scan every experiments/*/decision.md marked [x] PROMOTE; tokenize its claim.
  4. Warn for each PROMOTE claim sharing >= MATCH_THRESHOLD tokens with the slug.
"""

import json
import os
import re
import sys
from pathlib import Path

MIN_TOKEN_LEN = 4
MATCH_THRESHOLD = 2

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


def _tokenize(text: str) -> set[str]:
    """Lowercase alpha tokens of meaningful length, minus stopwords."""
    raw = re.findall(r"[a-zа-яё]+", text.lower())
    return {t for t in raw if len(t) >= MIN_TOKEN_LEN and t not in STOPWORDS}


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
        if len(overlap) >= MATCH_THRESHOLD:
            matches.append((decision.parent.name, sorted(overlap)))
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
    triggering_slug = ""
    for slug in slugs:
        slug_tokens = _tokenize(slug)
        if not slug_tokens:
            continue
        for exp_id, overlap in _scan_active_promotes(root, slug_tokens):
            if exp_id not in all_matches:
                all_matches[exp_id] = overlap
                triggering_slug = slug

    if not all_matches:
        sys.exit(0)  # silent — no dependency, no noise

    lines = [
        f"  • {exp_id} (shared: {', '.join(ov)})" for exp_id, ov in sorted(all_matches.items())
    ]
    msg = (
        f"[null-retroscan] ⚠️  New NULL '{triggering_slug}' may undercut active PROMOTE claims:\n"
        + "\n".join(lines)
        + "\n\n→ Principle 5 (immediate retroscan): re-check whether these claims depend on "
        "the just-falsified ground before trusting them."
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
