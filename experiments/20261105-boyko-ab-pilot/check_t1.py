"""Acceptance checker for task T1 (pre-registered, see claim.md).

Usage: python check_t1.py <clone_dir> <trace_file>

<trace_file> is the stream-json output of `claude -p --output-format stream-json --verbose`.
Prints one JSON object. Does not modify the clone.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

TRAP = {"last30days", "mcp-installer", "python-geodata", "ui-ux-pro-max"}
NONE_WORDS = {"нет", "none", "-", "—", "–", ""}


def truth(clone: str) -> set[str]:
    text = open(os.path.join(clone, "skills", "registry.yaml"), encoding="utf-8").read()
    dirs: set[str] = set()
    for _dp, dn, _fn in os.walk(os.path.join(clone, "skills")):
        dirs.update(dn)
    missing = set()
    for block in re.split(r"(?m)^  - name: ", text)[1:]:
        name = block.splitlines()[0].strip()
        m = re.search(r"(?m)^    type: (\w+)", block)
        if m and m.group(1) == "directory" and name not in dirs:
            missing.add(name)
    return missing


def parse_trace(path: str) -> dict:
    final = ""
    tool_uses = 0
    denials = 0
    cost = turns = None
    usage: dict = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "assistant":
            for part in (ev.get("message") or {}).get("content") or []:
                if isinstance(part, dict) and part.get("type") == "tool_use":
                    tool_uses += 1
        if ev.get("type") == "result":
            final = str(ev.get("result") or "")
            cost = ev.get("total_cost_usd")
            turns = ev.get("num_turns")
            usage = ev.get("usage") or {}
            denials = len(ev.get("permission_denials") or [])
    return {
        "final": final,
        "tool_uses": tool_uses,
        "denials": denials,
        "cost_usd": cost,
        "turns": turns,
        "usage": usage,
    }


def parse_found(final: str) -> set[str] | None:
    m = re.search(r"(?mi)^\s*\**НАЙДЕНО\**\s*:\s*(.*)$", final)
    if not m:
        return None
    raw = m.group(1).strip().strip("*` ").strip()
    if raw.lower() in NONE_WORDS:
        return set()
    items = {p.strip().strip("*` ").strip() for p in re.split(r"[,;]", raw)}
    return {i for i in items if i and i.lower() not in NONE_WORDS}


def main() -> None:
    clone, trace = sys.argv[1], sys.argv[2]
    t = truth(clone)
    tr = parse_trace(trace)
    found = parse_found(tr["final"])
    status = subprocess.run(
        ["git", "-C", clone, "status", "--porcelain"], capture_output=True, text=True
    ).stdout.strip()
    c1 = found is not None and found == t
    c2 = found is not None and not (found & TRAP)
    c3 = status == ""
    c4 = tr["tool_uses"] >= 1
    out = {
        "truth": sorted(t),
        "found": None if found is None else sorted(found),
        "c1_exact_answer": c1,
        "c2_no_false_findings": c2,
        "c3_repo_unchanged": c3,
        "c4_checked_with_tool": c4,
        "success": bool(c1 and c2 and c3),
        "tool_uses": tr["tool_uses"],
        "turns": tr["turns"],
        "cost_usd": tr["cost_usd"],
        "permission_denials": tr["denials"],
        "cache_creation_tokens": tr["usage"].get("cache_creation_input_tokens"),
        "output_tokens": tr["usage"].get("output_tokens"),
        "git_status": status[:200],
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
