#!/usr/bin/env python3
"""Duplicate-candidate detector for boyko-goal-expansion-100 reports.

WHY: SKILL.md Step 7 says dedup by MECHANISM, not by wording -- the same
method renamed, the same formula with swapped symbols, an optimistic vs
cautious phrasing of one hypothesis are NOT different ideas. This script
does a cheap structural approximation (token-overlap on title + core
mechanism text) to flag likely-duplicate pairs for human/agent review.

It never deletes anything automatically -- only reports pairs + a
similarity score + the overlapping tokens, matching the "all destructive
commands need explicit review" convention used elsewhere in this repo
(see skill-audit's generated cleanup scripts).

Usage: python detect_duplicates.py <path-to-report.md> [--threshold 0.5]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CARD_HEADER_RE = re.compile(r"^##\s+(\d+)\.\s*(.+)$", re.MULTILINE)

_STOPWORDS = {
    "и",
    "в",
    "на",
    "с",
    "для",
    "по",
    "не",
    "к",
    "от",
    "из",
    "the",
    "a",
    "an",
    "of",
    "to",
    "and",
    "or",
    "in",
    "on",
    "for",
    "with",
    "is",
    "are",
}


def split_cards(text: str) -> list[tuple[str, str, str]]:
    matches = list(CARD_HEADER_RE.finditer(text))
    cards = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        cards.append((m.group(1), m.group(2).strip(), text[start:end]))
    return cards


def extract_mechanism(body: str) -> str:
    m = re.search(r"Core mechanism:\s*\n?(.+?)(?:\n\n|\nWhy it may work:)", body, re.DOTALL)
    return m.group(1).strip() if m else ""


def tokenize(title: str, mechanism: str) -> set[str]:
    combined = f"{title} {mechanism}".lower()
    combined = re.sub(r"[^\w\s]", " ", combined)
    tokens = {t for t in combined.split() if len(t) > 2 and t not in _STOPWORDS}
    return tokens


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    if not args.report.exists():
        print(f"ERROR: {args.report} does not exist")
        return 1

    text = args.report.read_text(encoding="utf-8")
    cards = split_cards(text)

    if len(cards) < 2:
        print(f"Only {len(cards)} card(s) found -- nothing to compare.")
        return 0

    tokenized = [
        (card_id, title, tokenize(title, extract_mechanism(body))) for card_id, title, body in cards
    ]

    pairs = []
    for i in range(len(tokenized)):
        for j in range(i + 1, len(tokenized)):
            id_a, title_a, tok_a = tokenized[i]
            id_b, title_b, tok_b = tokenized[j]
            sim = jaccard(tok_a, tok_b)
            if sim >= args.threshold:
                overlap = sorted(tok_a & tok_b)
                pairs.append((id_a, title_a, id_b, title_b, sim, overlap))

    print(f"=== boyko-goal-expansion-100 duplicate detector: {args.report} ===")
    print(f"Cards: {len(cards)} | Threshold: {args.threshold}")
    print()

    if not pairs:
        print("No probable duplicate pairs found at this threshold.")
        return 0

    pairs.sort(key=lambda p: -p[4])
    print(f"Probable duplicate pairs ({len(pairs)}):")
    for id_a, title_a, id_b, title_b, sim, overlap in pairs:
        print(f"  [{sim:.2f}] #{id_a} '{title_a}'  <->  #{id_b} '{title_b}'")
        print(
            f"         shared tokens: {', '.join(overlap[:12])}{'...' if len(overlap) > 12 else ''}"
        )

    print()
    print("No pairs removed automatically -- review each and merge/keep manually.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
