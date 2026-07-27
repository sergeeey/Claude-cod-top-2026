#!/usr/bin/env python3
"""Structural validator for boyko-goal-expansion-100 reports.

WHY: the skill's discipline is enforced by re-checking the OUTPUT shape, not
by trusting the model followed every step of SKILL.md. This catches the
"corporate ritual of quantity over content" failure mode mechanically:
missing falsifier/cheapest-test, out-of-range scores, duplicate IDs, empty
categories.

Usage: python validate_output.py <path-to-report.md>
Exit code: 0 if no CRITICAL findings, 1 otherwise. Always prints a report
regardless of exit code -- warnings don't fail the run, only missing
required fields / duplicate IDs / out-of-range scores do.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_FIELDS = [
    "Type:",
    "Evidence:",
    "Core mechanism:",
    "Why it may work:",
    "Required assumptions:",
    "Main obstacle:",
    "Cheapest test:",
    "Falsifier:",
    "Expected output:",
    "Scores:",
]

VALID_TYPES = {
    "established_method",
    "extension",
    "cross_domain_transfer",
    "hybrid",
    "inverse_problem",
    "no_go",
    "computational_experiment",
    "new_hypothesis",
}

VALID_EVIDENCE = {"fact", "inference", "hypothesis", "unknown"}

SCORE_0_10 = ("relevance", "feasibility", "novelty", "expected_impact", "evidence_strength")

CARD_HEADER_RE = re.compile(r"^##\s+(\d+)\.\s*(.+)$", re.MULTILINE)


def split_cards(text: str) -> list[tuple[str, str, str]]:
    """Return list of (id, title, body) for each '## N. Title' block."""
    matches = list(CARD_HEADER_RE.finditer(text))
    cards = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        cards.append((m.group(1), m.group(2).strip(), text[start:end]))
    return cards


def check_card(card_id: str, title: str, body: str) -> tuple[list[str], list[str]]:
    """Return (critical, warnings) findings for one card."""
    critical: list[str] = []
    warnings: list[str] = []

    if not title:
        critical.append(f"Card {card_id}: empty title")

    for field in REQUIRED_FIELDS:
        if field not in body:
            critical.append(f"Card {card_id} ({title}): missing required field '{field}'")

    type_m = re.search(r"Type:\s*(\S+)", body)
    if type_m and type_m.group(1) not in VALID_TYPES:
        critical.append(f"Card {card_id} ({title}): invalid Type '{type_m.group(1)}'")

    ev_m = re.search(r"Evidence:\s*(\S+)", body)
    if ev_m and ev_m.group(1) not in VALID_EVIDENCE:
        critical.append(f"Card {card_id} ({title}): invalid Evidence '{ev_m.group(1)}'")

    for score_name in SCORE_0_10:
        m = re.search(rf"{score_name}:\s*([\d.]+)", body)
        if m:
            val = float(m.group(1))
            if not (0 <= val <= 10):
                critical.append(f"Card {card_id} ({title}): {score_name}={val} out of range 0-10")
        else:
            warnings.append(f"Card {card_id} ({title}): missing score '{score_name}'")

    conf_m = re.search(r"confidence:\s*([\d.]+)", body)
    if conf_m:
        val = float(conf_m.group(1))
        if not (0 <= val <= 1):
            critical.append(f"Card {card_id} ({title}): confidence={val} out of range 0.00-1.00")

    cheapest_m = re.search(r"Cheapest test:\s*\n?\s*(.+)", body)
    if cheapest_m and not cheapest_m.group(1).strip().startswith("["):
        pass  # non-empty and not a bare placeholder -- fine
    elif "Cheapest test:" in body:
        after = body.split("Cheapest test:", 1)[1].strip()
        if not after or after.startswith("Falsifier:"):
            critical.append(f"Card {card_id} ({title}): empty Cheapest test")

    return critical, warnings


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python validate_output.py <path-to-report.md>")
        return 1

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: {path} does not exist")
        return 1

    text = path.read_text(encoding="utf-8")
    cards = split_cards(text)

    if not cards:
        print("CRITICAL: no idea cards found (expected '## N. Title' headers)")
        return 1

    ids = [c[0] for c in cards]
    dup_ids = {i for i in ids if ids.count(i) > 1}

    all_critical: list[str] = []
    all_warnings: list[str] = []
    type_counts: dict[str, int] = {}

    for card_id, title, body in cards:
        critical, warnings = check_card(card_id, title, body)
        all_critical.extend(critical)
        all_warnings.extend(warnings)
        type_m = re.search(r"Type:\s*(\S+)", body)
        if type_m:
            type_counts[type_m.group(1)] = type_counts.get(type_m.group(1), 0) + 1

    if dup_ids:
        all_critical.append(f"Duplicate card IDs: {sorted(dup_ids)}")

    print(f"=== boyko-goal-expansion-100 validator: {path} ===")
    print(f"Cards found: {len(cards)}")
    print(f"Type distribution: {type_counts}")
    print(f"  cross_domain_transfer: {type_counts.get('cross_domain_transfer', 0)} (target >=25)")
    print(f"  no_go: {type_counts.get('no_go', 0)} (target >=10)")
    comp_count = type_counts.get("computational_experiment", 0)
    print(f"  computational_experiment: {comp_count} (target >=10)")
    print()

    if all_warnings:
        print(f"WARNINGS ({len(all_warnings)}):")
        for w in all_warnings:
            print(f"  - {w}")
        print()

    if all_critical:
        print(f"CRITICAL ({len(all_critical)}):")
        for c in all_critical:
            print(f"  - {c}")
        return 1

    print("No critical findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
