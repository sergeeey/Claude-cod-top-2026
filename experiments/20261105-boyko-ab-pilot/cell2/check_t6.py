"""Acceptance checker for T6 (pre-registered). Usage: python check_t6.py <clone> <trace> <out_pre_edit_txt>

Mechanical checks: scope (only docs/QUICKSTART_DRAFT.md added), file present, broken references.
Also writes the assistant text emitted BEFORE the first Edit/Write tool call to <out_pre_edit_txt>,
for the blind contract rubric (rubric_t6.md). Does not modify the clone.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

DRAFT = "docs/QUICKSTART_DRAFT.md"
PATH_RE = re.compile(r"^[\w.\-/]+$")
KNOWN_EXT = (".py", ".md", ".yaml", ".yml", ".json", ".sh", ".ps1", ".txt", ".toml", ".cff")
KNOWN_ROOTS = (
    "hooks/",
    "skills/",
    "agents/",
    "rules/",
    "docs/",
    "scripts/",
    "tests/",
    "commands/",
    "claude-md/",
    "experiments/",
)
SKIP_PREFIXES = ("~", "/", "http", "$", "%", ".claude")


def git(clone: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", clone, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


def parse_trace(path: str) -> tuple[dict, str]:
    tool_uses, denials, cost, turns, usage = 0, 0, None, None, {}
    pre, seen_edit = [], False
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
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "tool_use":
                    tool_uses += 1
                    if part.get("name") in ("Edit", "Write", "NotebookEdit"):
                        seen_edit = True
                elif part.get("type") == "text" and not seen_edit:
                    pre.append(part.get("text", ""))
        if ev.get("type") == "result":
            cost, turns = ev.get("total_cost_usd"), ev.get("num_turns")
            usage = ev.get("usage") or {}
            denials = len(ev.get("permission_denials") or [])
    return (
        {
            "tool_uses": tool_uses,
            "denials": denials,
            "cost": cost,
            "turns": turns,
            "usage": usage,
            "wrote": seen_edit,
        },
        "\n".join(pre),
    )


def references(text: str) -> list[str]:
    refs = []
    for span in re.findall(r"`([^`\n]+)`", text):
        for word in span.split():
            w = word.strip("\"'()[],.;:")
            if not w or w.startswith(SKIP_PREFIXES) or any(c in w for c in "<>*{}$|"):
                continue
            if not PATH_RE.match(w):
                continue
            if w.startswith(KNOWN_ROOTS) or (
                ("/" in w or w.endswith(KNOWN_EXT)) and w.endswith(KNOWN_EXT)
            ):
                refs.append(w)
    return sorted(set(refs))


def main() -> None:
    clone, trace, pre_out = sys.argv[1], sys.argv[2], sys.argv[3]
    tr, pre_text = parse_trace(trace)
    with open(pre_out, "w", encoding="utf-8") as fh:
        fh.write(pre_text)

    status = [ln for ln in git(clone, "status", "--porcelain").splitlines() if ln.strip()]
    changed = [ln[3:].strip().strip('"') for ln in status]
    scope_ok = changed == [DRAFT] or (len(changed) == 0 and False)
    draft_path = os.path.join(clone, DRAFT)
    exists = os.path.exists(draft_path)
    text = open(draft_path, encoding="utf-8", errors="replace").read() if exists else ""
    lines = len(text.splitlines())
    refs = references(text)
    broken = [r for r in refs if not os.path.exists(os.path.join(clone, r.rstrip("/")))]

    c1 = scope_ok
    c2 = exists and lines >= 10
    c3 = c2 and len(broken) == 0
    out = {
        "c1_scope_only_draft": c1,
        "c2_draft_present_ge10_lines": c2,
        "c3_no_broken_references": c3,
        "success": bool(c1 and c2 and c3),
        "draft_lines": lines,
        "references_total": len(refs),
        "references_broken": broken,
        "changed_files": changed,
        "wrote_before_check": tr["wrote"],
        "pre_edit_text_chars": len(pre_text),
        "tool_uses": tr["tool_uses"],
        "turns": tr["turns"],
        "cost_usd": tr["cost"],
        "permission_denials": tr["denials"],
        "cache_creation_tokens": tr["usage"].get("cache_creation_input_tokens"),
        "output_tokens": tr["usage"].get("output_tokens"),
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
