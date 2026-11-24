#!/usr/bin/env python3
"""contract: turn a raw task into a goal contract and the tools to run it.

    python contract.py route "проверь, воспроизводятся ли графики из статьи"
    python contract.py draft "..."          # full contract draft for approval
    python contract.py cards                # list the contract cards
    python contract.py doctor [--strict]    # card routes that the index does not know
    python contract.py build-index          # regenerate index.json (add --check in CI)

Works from the repo (skills/core/contract) and from an install (~/.claude/skills/contract).
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import contracts_lib as lib  # noqa: E402
from build_index import build_index, dumps, unresolved_routes  # noqa: E402


def _layout() -> dict[str, object]:
    """Where the sources of the index live, for a repo checkout or an installed skill."""
    repo_skills = HERE.parent  # .../skills/core
    if (repo_skills.parent / "registry.yaml").is_file():  # repo: skills/{core,extensions}
        skills_root = repo_skills.parent
        return {
            "skills": [skills_root / "core", skills_root / "extensions"],
            "agents": skills_root.parent / "agents",
            "registry": skills_root / "registry.yaml",
        }
    # install: ~/.claude/skills/<skill>/ ; agents live next to the skills directory
    return {"skills": [HERE.parent], "agents": HERE.parent.parent / "agents", "registry": None}


def _load_stats(path: str | None) -> dict[str, dict[str, int]] | None:
    if not path:
        return None
    try:
        data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _index(path: str | None) -> dict | None:
    return lib.load_index(Path(path) if path else HERE / "index.json")


def cmd_build(args: argparse.Namespace) -> int:
    layout = _layout()
    skills = [Path(p) for p in args.skills_dir] if args.skills_dir else layout["skills"]
    agents = Path(args.agents_dir) if args.agents_dir else layout["agents"]
    index = build_index(HERE / "cards", skills, agents, layout["registry"])  # type: ignore[arg-type]
    text = dumps(index)
    out = Path(args.out) if args.out else HERE / "index.json"
    if args.check:
        current = out.read_text(encoding="utf-8") if out.is_file() else ""
        if current != text:
            print(f"{out} is stale: run `python contract.py build-index`", file=sys.stderr)
            return 1
        print(f"{out} is up to date ({len(index['cards'])} cards, {len(index['skills'])} skills)")
        return 0
    out.write_text(text, encoding="utf-8", newline="\n")
    print(
        f"wrote {out}: {len(index['cards'])} cards, {len(index['skills'])} skills, "
        f"{len(index['agents'])} agents"
    )
    return 0


def cmd_route(args: argparse.Namespace) -> int:
    index = _index(args.index)
    if index is None:
        print(
            "index.json missing or unreadable: run `python contract.py build-index`",
            file=sys.stderr,
        )
        return 2
    routed = lib.route(args.task, index, _load_stats(args.stats), explore=not args.no_explore)
    if args.json:
        print(json.dumps(routed, ensure_ascii=False, indent=1))
    else:
        print(lib.hint(routed) or "Подходящей карточки нет: общий контракт (команда `draft`).")
    return 0


def cmd_draft(args: argparse.Namespace) -> int:
    index = _index(args.index)
    if index is None:
        print(
            "index.json missing or unreadable: run `python contract.py build-index`",
            file=sys.stderr,
        )
        return 2
    routed = lib.route(args.task, index, _load_stats(args.stats), explore=not args.no_explore)
    print(lib.draft(routed, index, args.task))
    return 0


def cmd_cards(args: argparse.Namespace) -> int:
    index = _index(args.index)
    if index is None:
        print("index.json missing or unreadable", file=sys.stderr)
        return 2
    for card in index["cards"]:
        gap = f"  [пробел: {card['gap']}]" if card.get("gap") else ""
        print(f"{card['id']:28} {card['risk_tier']:7} {card['title']}{gap}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Report card routes that name a skill/agent the index does not know."""
    index = _index(args.index)
    if index is None:
        print("index.json missing or unreadable", file=sys.stderr)
        return 2
    missing = unresolved_routes(index)
    for line in missing:
        print("unresolved:", line)
    print(f"{len(index['cards'])} cards, {len(missing)} unresolved route name(s)")
    return 1 if missing and args.strict else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build-index", help="regenerate index.json")
    b.add_argument("--out")
    b.add_argument("--skills-dir", nargs="*", help="override skill roots (e.g. ~/.claude/skills)")
    b.add_argument("--agents-dir")
    b.add_argument("--check", action="store_true", help="fail if index.json is stale")
    b.set_defaults(func=cmd_build)

    for name, func, helptext in (
        ("route", cmd_route, "one-line suggestion for a task"),
        ("draft", cmd_draft, "full contract draft for approval"),
    ):
        r = sub.add_parser(name, help=helptext)
        r.add_argument("task")
        r.add_argument("--json", action="store_true")
        r.add_argument("--index")
        r.add_argument("--stats", help="outcome statistics JSON (optional)")
        r.add_argument("--no-explore", action="store_true")
        r.set_defaults(func=func)

    c = sub.add_parser("cards", help="list contract cards")
    c.add_argument("--index")
    c.set_defaults(func=cmd_cards)

    d = sub.add_parser("doctor", help="check that card routes resolve against the index")
    d.add_argument("--index")
    d.add_argument("--strict", action="store_true", help="exit 1 when something is unresolved")
    d.set_defaults(func=cmd_doctor)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
