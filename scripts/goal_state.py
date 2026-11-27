#!/usr/bin/env python3
"""Goal state: an explicit, checkable Decide step for a long mission.

WHY: the operating loop (PRODUCT_CONSTITUTION v2, section 4) ends every verify step with one
decision (DONE / CONTINUE / REPLAN / BLOCKED / STOPPED) and keeps the invariant
turn_completed != goal_completed. Before this script the decision lived only in prose, so
nothing stopped a session from calling a mission done without evidence for each criterion, and
nothing noticed when a restored session silently rewrote the goal (observed 2026-11-26: a program
contract was lost after context compaction).

The contract stays a Markdown file the owner can read. This script protects the sections that must
not change during a mission (goal, definition of done, constraints) by hash, and keeps an
append-only decision log in a JSON state file next to it. It never edits the contract.

Usage:
    python scripts/goal_state.py init   --contract C.md --state S.json
    python scripts/goal_state.py check  --contract C.md --state S.json
    python scripts/goal_state.py decide --contract C.md --state S.json --verdict CONTINUE \
        --evidence "CI green on 1fd28f1" --next "run the install rehearsal"
    python scripts/goal_state.py decide ... --verdict DONE --dod 1 --dod 2 ... --evidence "..."

Exit codes: 0 ok, 1 drift or invalid decision, 2 usage or missing file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

VERDICTS = ("DONE", "CONTINUE", "REPLAN", "BLOCKED", "STOPPED")
# Sections whose text must not change during a mission. Matched by heading prefix, any language.
PROTECTED_PREFIXES = (
    "## Цель",
    "## DoD",
    "## Ограничения",
    "## Goal",
    "## Definition of done",
    "## Constraints",
)


_PREFIXES_LOWER = tuple(p.lower() for p in PROTECTED_PREFIXES)
_DOD_PREFIXES_LOWER = ("## dod", "## definition of done")
# A criterion: a top-level numbered item (1. or 1)) or a top-level bullet (-, *, +).
_DOD_ITEM_RE = re.compile(r"^(?:\d+[.)]|[-*+])\s", flags=re.MULTILINE)


def _is_protected(line: str) -> bool:
    # WHY case-insensitive: `## Dod` must not escape protection by a change of case.
    return line.lower().startswith(_PREFIXES_LOWER)


def protected_headings(text: str) -> list[str]:
    """Protected level-2 headings in order, duplicates included."""
    return [ln.strip() for ln in text.splitlines() if ln.startswith("## ") and _is_protected(ln)]


def duplicate_headings(text: str) -> list[str]:
    # WHY: sections are keyed by heading, so a second `## DoD` would silently replace the first;
    # a contract with a repeated protected heading is refused instead.
    seen: set[str] = set()
    dupes = []
    for h in protected_headings(text):
        key = h.lower()
        if key in seen:
            dupes.append(h)
        seen.add(key)
    return dupes


def protected_sections(text: str) -> dict[str, str]:
    """Return {heading: body} for protected level-2 sections, bodies stripped of trailing space."""
    sections: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(lines).strip()
            current = line.strip() if _is_protected(line) else None
            lines = []
        elif current is not None:
            lines.append(line.rstrip())
    if current is not None:
        sections[current] = "\n".join(lines).strip()
    return sections


def dod_count(sections: dict[str, str]) -> int:
    """Number of top-level criteria in the definition-of-done section."""
    for heading, body in sections.items():
        if heading.lower().startswith(_DOD_PREFIXES_LOWER):
            return len(_DOD_ITEM_RE.findall(body))
    return 0


def digest(sections: dict[str, str]) -> dict[str, str]:
    return {h: hashlib.sha256(b.encode("utf-8")).hexdigest() for h, b in sections.items()}


def load(path: Path) -> dict:
    data: dict = json.loads(path.read_text(encoding="utf-8"))
    return data


def save(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_init(contract: Path, state_path: Path) -> int:
    if state_path.exists():
        print(f"state already exists: {state_path} (refusing to overwrite the decision log)")
        return 1
    text = contract.read_text(encoding="utf-8")
    sections = protected_sections(text)
    if not sections:
        print("contract has no protected sections (## Цель / ## DoD / ## Ограничения)")
        return 1
    dupes = duplicate_headings(text)
    if dupes:
        print(f"refused: repeated protected headings {dupes}")
        return 1
    if dod_count(sections) == 0:
        # WHY: with zero criteria every DONE would pass the coverage check.
        print(
            "refused: no countable DoD criteria (numbered 1. / 1) or bullet - items under ## DoD)"
        )
        return 1
    save(
        state_path,
        {
            "contract": contract.name,
            "protected": digest(sections),
            "dod_count": dod_count(sections),
            "decisions": [],
        },
    )
    print(f"initialised: {len(sections)} protected sections, {dod_count(sections)} DoD criteria")
    return 0


def drift(contract: Path, state: dict) -> list[str]:
    text = contract.read_text(encoding="utf-8")
    now = digest(protected_sections(text))
    then = state["protected"]
    problems = [f"repeated heading: {h}" for h in duplicate_headings(text)]
    problems += [f"changed: {h}" for h in then if h in now and now[h] != then[h]]
    problems += [f"removed: {h}" for h in then if h not in now]
    problems += [f"added: {h}" for h in now if h not in then]
    return problems


def cmd_check(contract: Path, state_path: Path) -> int:
    state = load(state_path)
    problems = drift(contract, state)
    for d in state["decisions"]:
        if d.get("verdict") not in VERDICTS:
            problems.append(f"invalid verdict in log: {d.get('verdict')!r}")
    last = state["decisions"][-1] if state["decisions"] else None
    if problems:
        print("GOAL DRIFT OR INVALID STATE:")
        for p in problems:
            print("  -", p)
        return 1
    status = last["verdict"] if last else "NO_DECISION_YET"
    nxt = last.get("next", "") if last else ""
    print(f"ok: goal unchanged; last decision {status}; next: {nxt or '-'}")
    return 0


def cmd_decide(
    contract: Path,
    state_path: Path,
    verdict: str,
    evidence: list[str],
    dod: list[int],
    nxt: str,
    note: str,
) -> int:
    state = load(state_path)
    problems = drift(contract, state)
    if problems:
        print("refused: the protected goal sections changed since init:", "; ".join(problems))
        return 1
    if verdict not in VERDICTS:
        print(f"refused: verdict must be one of {', '.join(VERDICTS)}")
        return 1
    evidence = [e.strip() for e in evidence if e.strip()]
    if not evidence:
        print("refused: every decision needs at least one non-empty evidence item")
        return 1
    if verdict == "DONE":
        if state["dod_count"] == 0:
            print("refused: DONE with zero DoD criteria")
            return 1
        missing = sorted(set(range(1, state["dod_count"] + 1)) - set(dod))
        if missing:
            print(f"refused: DONE needs evidence for every DoD criterion; missing {missing}")
            return 1
    if verdict in ("CONTINUE", "REPLAN") and not nxt:
        print(f"refused: {verdict} needs a next action")
        return 1
    state["decisions"].append(
        {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "verdict": verdict,
            "dod_met": sorted(set(dod)),
            "evidence": evidence,
            "next": nxt,
            "note": note,
        }
    )
    save(state_path, state)
    print(f"recorded {verdict} ({len(state['decisions'])} decisions)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=("init", "check", "decide"))
    ap.add_argument("--contract", required=True, type=Path)
    ap.add_argument("--state", required=True, type=Path)
    ap.add_argument("--verdict", default="")
    ap.add_argument("--evidence", action="append", default=[])
    ap.add_argument("--dod", action="append", type=int, default=[])
    ap.add_argument("--next", default="")
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)
    if not a.contract.exists() or (a.command != "init" and not a.state.exists()):
        print("missing contract or state file")
        return 2
    if a.command == "init":
        return cmd_init(a.contract, a.state)
    if a.command == "check":
        return cmd_check(a.contract, a.state)
    return cmd_decide(a.contract, a.state, a.verdict, a.evidence, a.dod, a.next, a.note)


if __name__ == "__main__":
    sys.exit(main())
