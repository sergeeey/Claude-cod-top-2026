"""Add or remove the skill-search instruction block in a CLAUDE.md (reversible).

    python scripts/skill_search_toggle.py --target ~/.claude/CLAUDE.md          # preview
    python scripts/skill_search_toggle.py --target ~/.claude/CLAUDE.md --apply  # install
    python scripts/skill_search_toggle.py --target ~/.claude/CLAUDE.md --remove --apply

The block sits between two marker lines, so removal restores the file byte for byte. Nothing else
in the target is touched, and the script never picks a target on its own.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

BEGIN = "<!-- skill-search:begin (experimental; remove with skill_search_toggle.py --remove) -->"
END = "<!-- skill-search:end -->"

BLOCK = """{begin}
## Skill discovery (experimental)

The skill list in context is the fast path: if a listed skill clearly fits, invoke it, no search.
Otherwise, before a non-trivial task of the audit / review / analysis / research / planning /
document-writing kind, run ONE search first, even if you could do the task with plain tools: a
specialised skill may exist that is not described in the list.
Never search for chat, questions, simple edits, continuations ("go on", "yes"), or when the user
named a skill. At most one search per task.

How: run `python "{script}" "<2-4 content words naming the capability the current goal needs>"`.
Use the user's own domain words, in Russian or English. Do not put destructive shell phrases or
private data in the query (Bash filters block words like "drop table"); paraphrase instead.
The output starts with `[skill-search]`. If it says "no confident match", do the task directly;
otherwise read the candidate's description and invoke it with the Skill tool only if it really
fits. The user never has to know skill names or this tool.
{end}
"""


def render(script: Path) -> str:
    return BLOCK.format(begin=BEGIN, end=END, script=script.as_posix())


def strip_block(text: str) -> str:
    start = text.find(BEGIN)
    if start < 0:
        return text
    stop = text.find(END, start)
    if stop < 0:
        return text
    cut_end = stop + len(END)
    if text[cut_end : cut_end + 1] == "\n":
        cut_end += 1
    head = text[:start]
    if head.endswith("\n\n"):  # the one blank line this script added before the block
        head = head[:-1]
    return head + text[cut_end:]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--target", required=True, help="CLAUDE.md to edit (no default on purpose)")
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--apply", action="store_true", help="write the change (default: preview)")
    ap.add_argument("--script", default=str(Path(__file__).with_name("skill_search.py")))
    a = ap.parse_args(argv)
    target = Path(a.target).expanduser()
    old = target.read_bytes().decode("utf-8") if target.exists() else ""
    base = strip_block(old)
    if a.remove:
        new = base
    else:
        nl = chr(10)
        sep = "" if not base else (nl if base.endswith(nl) else nl * 2)
        new = base + sep + render(Path(a.script).resolve())
    if new == old:
        print("[skill-search-toggle] nothing to change")
        return 0
    if not a.apply:
        print(f"[skill-search-toggle] PREVIEW for {target} (use --apply to write):\n")
        print(render(Path(a.script).resolve()) if not a.remove else "(block would be removed)")
        return 0
    if target.exists():
        shutil.copy2(target, target.with_name(target.name + ".bak-skill-search"))
    target.write_bytes(new.encode("utf-8"))
    print(f"[skill-search-toggle] {'removed from' if a.remove else 'installed in'} {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
