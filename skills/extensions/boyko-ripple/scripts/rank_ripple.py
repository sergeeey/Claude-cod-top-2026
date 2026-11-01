#!/usr/bin/env python3
"""Rank boyko-ripple opportunities with a fixed formula and check that the order is stable.

Formula (SKILL.md, Шаг 4): priority = value * coefficient(effect_confidence) / test_cost_days.
The coefficients are a design choice (heuristic), not a calibrated constant. Because of
that, the order is re-computed under alternative coefficient sets. If the order changes,
or two priorities tie, the result is "порядок неустойчив" and no winner is named.

Input: a JSON list of objects:
  {"name": "...", "value": 1..10, "effect_confidence": "HIGH|MEDIUM|LOW|SPECULATIVE",
   "test_cost_days": > 0}

Usage: python rank_ripple.py opportunities.json
Exit code: 0 stable ranking, 1 unstable, 2 invalid input.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_COEF = {"HIGH": 0.9, "MEDIUM": 0.5, "LOW": 0.2, "SPECULATIVE": 0.05}
ALT_COEFS = [
    {"HIGH": 0.7, "MEDIUM": 0.3, "LOW": 0.1, "SPECULATIVE": 0.02},
    {"HIGH": 1.0, "MEDIUM": 0.6, "LOW": 0.3, "SPECULATIVE": 0.1},
]


class InvalidInput(ValueError):
    pass


def validate(items: object) -> list[dict]:
    if not isinstance(items, list) or not items:
        raise InvalidInput("input must be a non-empty list of opportunities")
    for item in items:
        if not isinstance(item, dict):
            raise InvalidInput("every opportunity must be an object")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise InvalidInput("every opportunity needs a non-empty name")
        value = item.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 1 <= value <= 10:
            raise InvalidInput(f"{name}: value must be a number 1..10")
        conf = item.get("effect_confidence")
        if conf not in DEFAULT_COEF:
            raise InvalidInput(f"{name}: effect_confidence must be one of {sorted(DEFAULT_COEF)}")
        cost = item.get("test_cost_days")
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost <= 0:
            raise InvalidInput(f"{name}: test_cost_days must be a positive number")
    return items


def priorities(items: list[dict], coef: dict[str, float]) -> dict[str, float]:
    return {
        i["name"]: i["value"] * coef[i["effect_confidence"]] / i["test_cost_days"] for i in items
    }


def order_under(items: list[dict], coef: dict[str, float]) -> tuple[list[str], bool]:
    """Return (names sorted by priority desc, has_tie)."""
    prio = priorities(items, coef)
    values = sorted(prio.values())
    has_tie = any(a == b for a, b in zip(values, values[1:], strict=False))
    ranked = sorted(prio, key=lambda n: (-prio[n], n))
    return ranked, has_tie


def rank(items: list[dict]) -> dict:
    default_order, tie = order_under(items, DEFAULT_COEF)
    alt_orders = [order_under(items, c) for c in ALT_COEFS]
    stable = not tie and all(
        not alt_tie and alt_order == default_order for alt_order, alt_tie in alt_orders
    )
    prio = priorities(items, DEFAULT_COEF)
    return {
        "order": default_order,
        "priorities": {n: round(prio[n], 2) for n in default_order},
        "stable": stable,
        "verdict": (
            f"winner: {default_order[0]}" if stable else "порядок неустойчив: победитель не назван"
        ),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python rank_ripple.py opportunities.json")
        return 2
    try:
        items = validate(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, InvalidInput) as exc:
        print(f"ERROR: {exc}")
        return 2

    result = rank(items)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["stable"] else 1


if __name__ == "__main__":
    sys.exit(main())
