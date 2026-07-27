#!/usr/bin/env python3
"""PostToolUse hook: capture experiment insights from decision.md writes.

WHY: Negative and archived experiment results contain mechanistic insights
("why it didn't work") that are valuable for OTHER problems. Without capture
these insights are lost after the session. This hook intercepts writes to
experiments/*/decision.md and automatically:
  1. Appends a row to null_results/INDEX.md (REJECT/ARCHIVE verdicts)
  2. Creates a raw note in ~/.claude/memory/raw/ for Obsidian import via
     session_save.py — pre-populated with reasoning so the insight survives

Triggers on: PostToolUse(Write|Edit) where file_path matches
experiments/*/decision.md

Design note: the raw note is a "starting point" — it captures what Claude
wrote in the Reasoning section. The human or next Claude session fills in
"where this insight might be a key". Low friction > perfect capture.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from utils import hook_main, parse_stdin

# Recursion guard — avoid loops inside Agent SDK sub-invocations.
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

DRY_RUN = os.environ.get("CLAUDE_DRY_RUN") == "1"

REPO_ROOT = Path(__file__).resolve().parent.parent
NULL_RESULTS_INDEX = REPO_ROOT / "null_results" / "INDEX.md"
RAW_DIR = Path.home() / ".claude" / "memory" / "_auto" / "raw"

_VERDICT_RE = re.compile(
    r"\[([xX])\]\s+\*{0,2}(PROMOTE|REPEAT|REJECT|ARCHIVE)\*{0,2}",
    re.IGNORECASE,
)
_ID_RE = re.compile(r"\*\*Experiment ID:\*\*\s*`?([^`\n]+)`?")
_DATE_RE = re.compile(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})")
_REASONING_RE = re.compile(r"##\s+Reasoning\s*\n(.*?)(?=\n##|\n---|\Z)", re.DOTALL | re.IGNORECASE)


def _parse_decision(text: str) -> dict:
    """Extract structured fields from decision.md content."""
    verdict_match = _VERDICT_RE.search(text)
    verdict = verdict_match.group(2).upper() if verdict_match else None

    id_match = _ID_RE.search(text)
    exp_id = id_match.group(1).strip() if id_match else "unknown"

    date_match = _DATE_RE.search(text)
    date = date_match.group(1) if date_match else datetime.now(UTC).strftime("%Y-%m-%d")

    reasoning_match = _REASONING_RE.search(text)
    reasoning = reasoning_match.group(1).strip() if reasoning_match else ""

    # Derive slug from experiment ID: take part after first dash-separated date
    # e.g. "20260514-prompt-injection" → "prompt-injection"
    slug_match = re.match(r"\d{8}-(.+)", exp_id)
    slug = slug_match.group(1) if slug_match else exp_id

    return {
        "verdict": verdict,
        "exp_id": exp_id,
        "date": date,
        "slug": slug,
        "reasoning": reasoning,
    }


def _update_null_results_index(parsed: dict) -> None:
    """Append one row to null_results/INDEX.md."""
    verdict = parsed["verdict"]
    exp_id = parsed["exp_id"]
    date = parsed["date"]
    slug = parsed["slug"]
    reasoning = parsed["reasoning"]

    # Summarise reasoning to ≤ 10 words for the index
    words = reasoning.split()
    short_why = " ".join(words[:10]) + ("…" if len(words) > 10 else "")
    if not short_why:
        short_why = "see decision.md for details"

    row = f"| {exp_id} | {date} | {slug} | {verdict} | {short_why} |\n"

    if DRY_RUN:
        print(f"[dry-run] would append to null_results/INDEX.md: {row.strip()}", file=sys.stderr)
        return

    if not NULL_RESULTS_INDEX.exists():
        return  # index file must exist — created by FL template setup

    content = NULL_RESULTS_INDEX.read_text(encoding="utf-8")

    # WHY: always insert after the LAST table row (line starting AND ending with |)
    # so new entries stay inside the table, not after ## How to Add an Entry sections.
    lines = content.split("\n")
    last_table_idx = max(
        (
            i
            for i, line in enumerate(lines)
            if line.strip().startswith("|") and line.strip().endswith("|")
        ),
        default=-1,
    )

    if last_table_idx == -1:
        return  # no table found — malformed index, skip

    if "No entries yet" in lines[last_table_idx]:
        lines[last_table_idx] = row.rstrip()
    else:
        lines.insert(last_table_idx + 1, row.rstrip())

    NULL_RESULTS_INDEX.write_text("\n".join(lines), encoding="utf-8")


def _create_raw_insight(parsed: dict) -> None:
    """Write a structured raw note for Obsidian import."""
    verdict = parsed["verdict"]
    exp_id = parsed["exp_id"]
    date = parsed["date"]
    slug = parsed["slug"]
    reasoning = parsed["reasoning"] or "[reasoning not found in decision.md]"

    tag = "archived" if verdict == "ARCHIVE" else "rejected"
    title = f"Инсайт: {slug}"

    note = f"""# {title}

#null-result #experiment-insight #{tag} #{slug.replace("-", "_")}

**Эксперимент:** `{exp_id}`
**Вердикт:** {verdict}
**Дата:** {date}

## Что не сработало / Reasoning

{reasoning}

## Что это говорит о механизме

> [заполнить: что именно мы узнали о том ПОЧЕМУ это не работает]

## Где этот инсайт может быть ключом

> [заполнить: в каком другом проекте / гипотезе это знание может помочь]

## Связанные эксперименты

> [заполнить: похожие попытки, предшественники]
"""

    safe_slug = re.sub(r"[^\w\-]", "_", f"{date}-{slug}")[:80]
    dest = RAW_DIR / f"{safe_slug}-insight.md"

    if dest.exists():
        return  # idempotent

    if DRY_RUN:
        print(f"[dry-run] would write raw insight: {dest}", file=sys.stderr)
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_text(note, encoding="utf-8")
    print(f"[experiment-insight] raw note created: {dest.name}", file=sys.stderr)


def main() -> None:
    data = parse_stdin()
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Only act on experiments/*/decision.md
    if not re.search(r"experiments/[^/]+/decision\.md$", file_path):
        return

    # Read the written content (from stdin payload or from disk)
    content = tool_input.get("content", "")
    if not content:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            return

    parsed = _parse_decision(content)

    if parsed["verdict"] not in {"REJECT", "ARCHIVE"}:
        # PROMOTE/REPEAT/None — no null_results entry needed
        return

    _update_null_results_index(parsed)
    _create_raw_insight(parsed)


if __name__ == "__main__":
    hook_main(main)
