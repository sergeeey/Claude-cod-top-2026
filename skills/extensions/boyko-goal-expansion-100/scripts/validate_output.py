#!/usr/bin/env python3
"""Structural validator for boyko-goal-expansion-100 reports.

WHY: the skill's discipline is enforced by re-checking the OUTPUT shape, not
by trusting the model followed every step of SKILL.md. This catches the
"corporate ritual of quantity over content" failure mode mechanically:
missing or EMPTY falsifier/cheapest-test, missing or out-of-range scores,
a missing falsifiability or speculation_penalty, a published adjusted_score
that does not match its components, duplicate IDs.

Usage: python validate_output.py <path-to-report.md>
Exit code: 0 if no CRITICAL findings, 1 otherwise. Always prints a report.
Warnings (e.g. type-distribution targets) do not fail the run.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Text fields: must be present AND carry content (not empty, not a bare template placeholder).
TEXT_FIELDS = [
    "Type",
    "Evidence",
    "Core mechanism",
    "Why it may work",
    "Required assumptions",
    "Main obstacle",
    "Cheapest test",
    "Falsifier",
    "Expected output",
]

# Labels that terminate a free-text field's value. Covers every label a card uses.
ALL_LABELS = TEXT_FIELDS + [
    "Source domains",
    "Target gap",
    "Scores",
    "Sources",
    "relevance",
    "feasibility",
    "novelty",
    "expected_impact",
    "evidence_strength",
    "falsifiability",
    "speculation_penalty",
    "confidence",
    "priority_score",
    "adjusted_score",
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

# 0-10 scores that enter the priority formula (scoring-model.md).
SCORE_0_10 = (
    "relevance",
    "feasibility",
    "novelty",
    "expected_impact",
    "evidence_strength",
    "falsifiability",
)

PRIORITY_WEIGHTS = {
    "relevance": 0.25,
    "feasibility": 0.20,
    "expected_impact": 0.20,
    "evidence_strength": 0.15,
    "novelty": 0.10,
    "falsifiability": 0.10,
}

CARD_HEADER_RE = re.compile(r"^##\s+(\d+)\.\s*(.+)$", re.MULTILINE)
ADJUSTED_TOLERANCE = 0.05


def split_cards(text: str) -> list[tuple[str, str, str]]:
    """Return list of (id, title, body) for each '## N. Title' block."""
    matches = list(CARD_HEADER_RE.finditer(text))
    cards = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        cards.append((m.group(1), m.group(2).strip(), text[start:end]))
    return cards


def field_value(body: str, label: str) -> str | None:
    """Text after '<label>:' up to the next known label, or None if the label is absent."""
    labels_alt = "|".join(re.escape(lbl) for lbl in ALL_LABELS)
    pattern = re.compile(
        rf"^[ \t]*{re.escape(label)}:[ \t]*(.*?)(?=^[ \t]*(?:{labels_alt}):|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(body)
    if m is None:
        return None
    return m.group(1).strip()


def is_placeholder(value: str) -> bool:
    """A value that is only a template hint, e.g. '[Какой результат ...]'."""
    return value.startswith("[") and value.endswith("]")


def numeric_field(body: str, name: str) -> float | None:
    """Value of a 'name: <number>' line, or None if the line is absent.

    Raises ValueError if the line exists but is not a number (e.g. '0-10').
    Accepts a leading minus sign, so negative values are seen and rejected by range.
    """
    m = re.search(rf"^[ \t]*{re.escape(name)}:[ \t]*([^\n]*)$", body, re.MULTILINE)
    if m is None:
        return None
    raw = m.group(1).strip()
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} is not a number: {raw!r}") from exc


def check_card(card_id: str, title: str, body: str) -> tuple[list[str], list[str]]:
    """Return (critical, warnings) findings for one card."""
    critical: list[str] = []
    warnings: list[str] = []
    where = f"Card {card_id} ({title})"

    if not title:
        critical.append(f"{where}: empty title")

    # --- text fields: present and non-empty -----------------------------------
    for field in TEXT_FIELDS:
        value = field_value(body, field)
        if value is None:
            critical.append(f"{where}: missing required field '{field}:'")
        elif not value or is_placeholder(value):
            critical.append(f"{where}: field '{field}:' is empty or still a template placeholder")

    type_value = field_value(body, "Type")
    if type_value:
        type_token = type_value.split()[0]
        if type_token not in VALID_TYPES:
            critical.append(f"{where}: invalid Type '{type_token}'")

    ev_value = field_value(body, "Evidence")
    if ev_value:
        ev_token = ev_value.split()[0]
        if ev_token not in VALID_EVIDENCE:
            critical.append(f"{where}: invalid Evidence '{ev_token}'")

    # --- numeric scores -------------------------------------------------------
    values: dict[str, float] = {}
    for name in SCORE_0_10:
        try:
            val = numeric_field(body, name)
        except ValueError as exc:
            critical.append(f"{where}: {exc}")
            continue
        if val is None:
            critical.append(f"{where}: missing score '{name}'")
            continue
        if not (0 <= val <= 10):
            critical.append(f"{where}: {name}={val:g} out of range 0-10")
            continue
        values[name] = val

    try:
        penalty = numeric_field(body, "speculation_penalty")
    except ValueError as exc:
        critical.append(f"{where}: {exc}")
        penalty = None
    if penalty is None and "speculation_penalty:" not in body:
        critical.append(f"{where}: missing 'speculation_penalty' (0-4)")
    elif penalty is not None and not (0 <= penalty <= 4 and penalty == int(penalty)):
        critical.append(f"{where}: speculation_penalty={penalty:g} must be an integer 0-4")

    try:
        conf = numeric_field(body, "confidence")
    except ValueError as exc:
        critical.append(f"{where}: {exc}")
        conf = None
    if conf is None and "confidence:" not in body:
        critical.append(f"{where}: missing 'confidence' (0.00-1.00)")
    elif conf is not None and not (0 <= conf <= 1):
        critical.append(f"{where}: confidence={conf:g} out of range 0.00-1.00")

    # --- optional: a published adjusted_score must match its components -------
    if "adjusted_score:" in body and len(values) == len(SCORE_0_10) and penalty is not None:
        try:
            published = numeric_field(body, "adjusted_score")
        except ValueError as exc:
            critical.append(f"{where}: {exc}")
            published = None
        if published is not None:
            priority = sum(PRIORITY_WEIGHTS[k] * values[k] for k in SCORE_0_10)
            expected = priority - penalty
            if abs(published - expected) > ADJUSTED_TOLERANCE:
                critical.append(
                    f"{where}: adjusted_score={published:g} does not match formula "
                    f"({expected:.2f} = priority {priority:.2f} - penalty {penalty:g})"
                )

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
        type_value = field_value(body, "Type")
        if type_value:
            type_token = type_value.split()[0]
            type_counts[type_token] = type_counts.get(type_token, 0) + 1

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
