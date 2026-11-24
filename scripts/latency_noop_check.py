#!/usr/bin/env python3
"""Which hooks of one turn shape do nothing for the input? One run per hook, counts only.

A hook counts as a no-op for the payload when it wrote nothing to stdout, exited 0 and changed
no file in the fixture repository or the isolated HOME. stderr length is printed, not judged.
This is evidence for the one input it was run on, not a proof for every input. Used to size the
gating what-if of latency_stand.py (--gate); the manifest is not changed by this script.

Inputs (--target, post_edit only except py):
  py          the stand's own Edit payload on the fixture src/mod.py (file not edited, as before)
  py_after    the same file already containing the edit
  md          Edit of docs/notes.md
  decision    Edit of experiments/exp-probe/decision.md, with claim.md beside it
  test        Edit of tests/test_mod.py

Usage: latency_noop_check.py --python <python 3.11> --hooks <dir> --shape post_edit [--target py]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import latency_stand as ls  # noqa: E402

# target -> (file in the fixture, content after the edit, old_string, new_string, sibling files)
TARGETS: dict[str, tuple[str, str, str, str, dict[str, str]]] = {
    "py_after": (
        "src/mod.py",
        "def add(a, b):\n    return a + b  # sum\n",
        "return a + b",
        "return a + b  # sum",
        {},
    ),
    "md": (
        "docs/notes.md",
        "# Заметки\n\nreturn a + b  # sum\n",
        "return a + b",
        "return a + b  # sum",
        {},
    ),
    "decision": (
        "experiments/exp-probe/decision.md",
        "# Решение\n\nreturn a + b  # sum\n",
        "return a + b",
        "return a + b  # sum",
        {"experiments/exp-probe/claim.md": "# Claim\n\nreturn a + b\n"},
    ),
    "test": (
        "tests/test_mod.py",
        "from src.mod import add\n\n\ndef test_add():\n    assert add(1, 2) == 3  # sum\n",
        "assert add(1, 2) == 3",
        "assert add(1, 2) == 3  # sum",
        {},
    ),
}


def tree(*roots: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for root in roots:
        for p in root.rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def edit_payload(repo: Path, sid: str, rel: str, old: str, new: str) -> bytes:
    """The stand's post-edit payload, pointed at another file."""
    data = {
        "session_id": sid,
        "cwd": str(repo),
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(repo / rel), "old_string": old, "new_string": new},
        "tool_response": {"success": True},
    }
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--python", required=True)
    parser.add_argument("--hooks", required=True, type=Path)
    parser.add_argument("--shape", required=True, choices=[s.name for s in ls.SHAPES])
    parser.add_argument("--target", default="py", choices=["py", *TARGETS])
    args = parser.parse_args()
    # the child runs in a fixture repo, so a relative path would not resolve
    args.hooks = args.hooks.resolve()
    if args.target != "py" and args.shape != "post_edit":
        parser.error("targets other than py are defined for --shape post_edit only")
    shape = next(s for s in ls.SHAPES if s.name == args.shape)
    manifest = json.loads((args.hooks / "settings.json").read_text(encoding="utf-8"))
    names = ls.select_hooks(manifest, shape)
    work = Path(tempfile.mkdtemp(prefix="noop-"))
    sess = ls.Session(work / "s", "noop")
    # plan_mode_guard keeps its state in the system temp dir, which outlives a run and made
    # verdicts depend on earlier runs; keep that state inside the isolated HOME instead
    tmp = str(sess.home / "tmp")
    sess.env.update(TEMP=tmp, TMP=tmp, TMPDIR=tmp)
    print(f"target={args.target} shape={args.shape} hooks={len(names)}")
    noop: list[str] = []
    for name in names:
        sess.reset()
        (sess.home / "tmp").mkdir(parents=True, exist_ok=True)
        if args.target != "py":
            rel, content, _, _, siblings = TARGETS[args.target]
            for path_rel, text in [(rel, content), *siblings.items()]:
                path = sess.repo / path_rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
        before = tree(sess.repo, sess.home)
        if args.target == "py":
            payload = ls.payload_for(shape, sess.repo, sess.sid)
        else:
            rel, _, old, new, _ = TARGETS[args.target]
            payload = edit_payload(sess.repo, sess.sid, rel, old, new)
        stats = work / f"st-{uuid.uuid4().hex}.txt"
        proc = subprocess.run(
            [
                args.python,
                "-S",
                str(ls.CHILD),
                "--hook",
                str(args.hooks / name),
                "--stats",
                str(stats),
            ],
            input=payload,
            capture_output=True,
            cwd=str(sess.repo),
            env=sess.env,
        )
        after = tree(sess.repo, sess.home)
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        is_noop = proc.returncode == 0 and not proc.stdout and not changed
        if is_noop:
            noop.append(name)
        print(
            f"{'NOOP  ' if is_noop else 'ACTIVE'} {name:<34} stdout={len(proc.stdout):>5} "
            f"rc={proc.returncode} files_changed={len(changed)} stderr={len(proc.stderr):>5}"
        )
    print(f"noop={len(noop)} of {len(names)}")
    print("noop list: " + ", ".join(noop))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
