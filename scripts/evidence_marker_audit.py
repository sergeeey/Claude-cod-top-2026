#!/usr/bin/env python3
"""Evidence-marker audit — a mechanical `sorry`-counter for prose claims.

WHY (methodology-comparison audit, 2026-09-01, comparing this repo's own
audit-verification-gate.md/falsification-ladder.md against Anthropic's
formal-math/zeta23/AUDIT.md): Lean's `sorry` token is counted by the compiler
itself, not by a human re-reading the proof -- an unproven placeholder cannot
silently hide in a promoted result. This repo's own evidence markers
([VERIFIED], [HYPOTHESIS], [WEAKENED], [UNKNOWN], [CONFLICTING], [INFERRED],
[WEAK], [MEMORY]) exist in `rules/integrity.md` and `rules/falsification-
ladder.md` for exactly the same purpose -- but nothing in this repo counted
them mechanically before this script. A `decision.md`/`claim.md` could be
called "promoted" while still carrying unresolved [UNKNOWN]/[HYPOTHESIS]
markers, and nothing would catch it except a human re-reading the whole file.

Deliberately NOT a promotion gate itself (that's promotion_gate_guard.py's
job, which checks section presence). This script answers a narrower,
purely-mechanical question: "how many of each evidence marker appear in this
file, and are any of the 'unresolved' ones present?" -- the same question
`grep -c sorry` answers for a Lean file, no more.

Usage:
  python scripts/evidence_marker_audit.py <file_or_glob> [--strict]

  --strict: exit 1 if any UNRESOLVED marker ([UNKNOWN], [HYPOTHESIS],
            [WEAKENED], [CONFLICTING]) is present. Without --strict, always
            exits 0 -- this script reports, promotion_gate_guard.py decides.
"""

from __future__ import annotations

import argparse
import glob
import re
import sys
from collections import Counter
from pathlib import Path

# Evidence markers from rules/integrity.md + rules/falsification-ladder.md.
# RESOLVED: the claim has been checked, one way or another -- a promoted
# result may legitimately carry these.
RESOLVED_MARKERS = ["VERIFIED", "DOCS", "CODE", "CONFIRMED-REAL"]

# UNRESOLVED: the claim is explicitly NOT yet settled -- per this repo's own
# Skeptic Response Matrix and Promotion Rule, these should not survive
# unaddressed into a "promoted" artifact without an explicit response
# recorded (Accepted/Mitigated/Dismissed).
UNRESOLVED_MARKERS = ["UNKNOWN", "HYPOTHESIS", "WEAKENED", "CONFLICTING"]

# INFORMATIONAL: lower-confidence but not a hard stop by themselves.
INFO_MARKERS = ["INFERRED", "WEAK", "MEMORY", "ANALYSIS-DERIVED"]

ALL_MARKERS = RESOLVED_MARKERS + UNRESOLVED_MARKERS + INFO_MARKERS

# WHY the trailing `(?=[\]:])`, not a bare `\]`: real usage in this repo is
# both the canonical bare form (`[VERIFIED]`) and an inline-cited form
# (`[VERIFIED: git log -1]`, `[VERIFIED-tool]`) -- confirmed by grepping
# .claude/memory/activeContext.md, which uses only the cited form. A regex
# requiring an immediate `]` matched zero markers in that real file.
_MARKER_RE = re.compile(r"\[(" + "|".join(re.escape(m) for m in ALL_MARKERS) + r")(?=[\]:-])")


def count_markers(text: str) -> Counter[str]:
    """Count each known evidence marker's literal occurrences in `text`."""
    return Counter(m for m in _MARKER_RE.findall(text))


def audit_file(path: Path) -> Counter[str]:
    return count_markers(path.read_text(encoding="utf-8", errors="replace"))


def format_report(path: Path, counts: Counter[str]) -> str:
    lines = [f"# {path}"]
    total = sum(counts.values())
    if total == 0:
        lines.append("  (no evidence markers found)")
        return "\n".join(lines)
    for group_name, group in (
        ("resolved", RESOLVED_MARKERS),
        ("unresolved", UNRESOLVED_MARKERS),
        ("informational", INFO_MARKERS),
    ):
        group_counts = {m: counts[m] for m in group if counts[m]}
        if group_counts:
            rendered = ", ".join(f"[{m}]×{n}" for m, n in group_counts.items())
            lines.append(f"  {group_name}: {rendered}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("path", help="File path or glob pattern to audit")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any UNRESOLVED marker is present in any matched file",
    )
    args = parser.parse_args(argv)

    matches = sorted(Path(p) for p in glob.glob(args.path, recursive=True) if Path(p).is_file())
    if not matches:
        single = Path(args.path)
        matches = [single] if single.is_file() else []
    if not matches:
        print(f"evidence_marker_audit: no files matched {args.path!r}", file=sys.stderr)
        return 2

    had_unresolved = False
    for path in matches:
        counts = audit_file(path)
        print(format_report(path, counts))
        if any(counts[m] for m in UNRESOLVED_MARKERS):
            had_unresolved = True

    if args.strict and had_unresolved:
        print(
            "\nevidence_marker_audit --strict: unresolved marker(s) present.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
