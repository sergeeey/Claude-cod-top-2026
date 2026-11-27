"""Deterministic checker for a ru-writing-standard rewrite (pre-registered 2026-11-24).

Usage: python check_rewrite.py ORIGINAL.txt REWRITE.txt

Exit code 0 when every check passes, 1 otherwise. The checks are fixed before the
rewrite exists, so the rewrite cannot be tuned to the checker after the fact.
"""

import re
import sys

# Template phrases named in skills/extensions/ru-writing-standard/SKILL.md section 1,
# plus the two phrases the skill's own PR-description example removes.
BANNED = [
    "играет ключевую роль",
    "важно отметить",
    "следует подчеркнуть",
    "быстро меняющемся мире",
    "открывает новые горизонты",
    "неотъемлемой частью",
    "в рамках данного",
    "комплексн",
]
PREAMBLES = ("важно", "следует", "в рамках", "стоит отметить")
REQUIRED = ["_sealed_ground_truth.md", "3 файла", "+8", "77", "истори", "CI"]
MAX_LENGTH_RATIO = 0.6


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def run(original: str, rewrite: str) -> list[tuple[str, bool, str]]:
    low = rewrite.lower()
    hits = [p for p in BANNED if p in low]
    first = low.strip().split(".")[0].strip().lstrip("«\"' ")
    new_numbers = numbers(rewrite) - numbers(original)
    missing = [t for t in REQUIRED if t.lower() not in low]
    ratio = len(rewrite) / max(len(original), 1)
    return [
        ("1 no template phrases", not hits, f"found: {hits}" if hits else "none found"),
        ("2 required facts kept", not missing, f"missing: {missing}" if missing else "all kept"),
        ("3 no invented numbers", not new_numbers, f"new: {sorted(new_numbers)}"),
        ("4 length ratio <= 0.6", ratio <= MAX_LENGTH_RATIO, f"ratio {ratio:.2f}"),
        ("5 no preamble opening", not first.startswith(PREAMBLES), f"opening: {first[:40]!r}"),
    ]


def main() -> int:
    original = open(sys.argv[1], encoding="utf-8").read()
    rewrite = open(sys.argv[2], encoding="utf-8").read()
    results = run(original, rewrite)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  ({detail})")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
