#!/usr/bin/env python3
"""Offline check of the contract router against real session transcripts.

    python scripts/eval_contract_router.py                  # aggregate numbers only
    python scripts/eval_contract_router.py --samples 25     # also print truncated hits to read

Reads Claude Code session logs (~/.claude/projects/*/*.jsonl), takes the user's typed prompts
(no tool results, no hook or system text), runs the same router the CLI prints and reports how
often it speaks and for which card. It answers one question: is the router quiet enough?

What it does NOT measure: whether a hint was RIGHT. That needs a human reading the samples or
the outcome ledger. Report firing rate and per-card counts as such, not as accuracy.
Prompt text never leaves this process unless --samples is given, and samples are for the
terminal only: do not paste them into a repo or a PR.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "core" / "contract"))

import contracts_lib as lib  # noqa: E402

_SKIP_PREFIX = ("<", "[", "Caveat:", "This session is being continued")


def user_prompts(path: Path) -> list[str]:
    out: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("type") != "user" or row.get("isMeta") or row.get("isSidechain"):
            continue
        content = (row.get("message") or {}).get("content")
        if isinstance(content, list):
            texts = [
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            if not texts or any(
                b.get("type") == "tool_result" for b in content if isinstance(b, dict)
            ):
                continue
            content = "\n".join(texts)
        if not isinstance(content, str):
            continue
        text = content.strip()
        if len(text) < 15 or text.startswith(_SKIP_PREFIX) or text.startswith("/"):
            continue
        if text.lower().startswith(("fast:", "just do:")):
            continue
        out.append(text)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--projects", default=str(Path.home() / ".claude" / "projects"))
    ap.add_argument("--index", default=str(ROOT / "skills" / "core" / "contract" / "index.json"))
    ap.add_argument("--samples", type=int, default=0)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    index = lib.load_index(Path(args.index))
    if index is None:
        print("index missing or unreadable", file=sys.stderr)
        return 2
    files = sorted(Path(args.projects).glob("*/*.jsonl"))
    prompts: list[tuple[str, str]] = []
    for f in files:
        prompts += [(f.stem[:8], p) for p in user_prompts(f)]
    if not prompts:
        print("no prompts found", file=sys.stderr)
        return 2

    hits: list[tuple[str, str, dict]] = []
    cards: Counter[str] = Counter()
    conf: Counter[str] = Counter()
    for sid, text in prompts:
        routed = lib.route(text, index)
        if routed["card"]:
            hits.append((sid, text, routed))
            cards[routed["card"]["id"]] += 1
            conf[routed["confidence"]] += 1

    n, h = len(prompts), len(hits)
    sessions = len({s for s, _ in prompts})
    print(f"sessions: {sessions}   prompts: {n}   hinted: {h} ({100 * h / n:.1f}%)")
    n_long = sum(len(p) > lib._LONG_INPUT for _, p in prompts)
    print(f"long prompts (> {lib._LONG_INPUT} chars): {n_long}")
    print("confidence:", dict(conf))
    for cid, c in cards.most_common():
        print(f"  {cid:28} {c}")
    hinted_sessions = len({s for s, _, _ in hits})
    print(f"sessions with at least one hint: {hinted_sessions} of {sessions}")

    if args.samples:
        rnd = random.Random(args.seed)
        for _sid, text, routed in rnd.sample(hits, min(args.samples, len(hits))):
            one = " ".join(text.split())[:130]
            print(f"- [{routed['card']['id']} {routed['confidence']}] {one}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
