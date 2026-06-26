#!/usr/bin/env python3
"""PostToolUse(Write|Edit) hook: enforce the NULL Exploitation Gate on REJECT.

WHY: research-methodology.md requires every NULL/REJECT to document not only
"what was killed" but "what opens next" (Relaxation Map). Without enforcement a
researcher can mark REJECT with an empty Kill Analysis template, and
experiment_insight.py will silently archive the hollow record. That breaks the
"bonus chain": a NULL without constraint-extraction is a dead end, not a fork.

Symmetric to promotion_gate_guard.py (which gates PROMOTE). This gates REJECT.

Fires on: Write|Edit to **/experiments/**/decision.md when [x] REJECT is set.
Soft nudge via additionalContext (never blocks). Checks 4 conditions:
  1. "What Was Killed" filled       — specific, not empty template braces
  2. "What Was NOT Killed" filled   — at least one survivor named
  3. Relaxation Map has >=1 real row — not A_/V1: placeholders
  4. Kill reason is specific        — not "didn't work" / "too hard" / "no data"
"""

import json
import os
import re
import sys
from pathlib import Path

# WHY: vague reasons break the chain — a NULL must yield a structural constraint,
# not a feeling. These phrases signal an un-analysed failure.
VAGUE_REASONS = [
    "не получилось",
    "не сработало",
    "не вышло",
    "didn't work",
    "did not work",
    "слишком сложно",
    "too hard",
    "too complex",
    "не хватает данных",
    "not enough data",
    "insufficient data",
]

# WHY: tokens that are pure template scaffolding — presence of only these in a
# field means the author left it unfilled.
_PLACEHOLDERS = {
    "",
    "a_",
    "a₁",
    "a₂",
    "a₃",
    "v1",
    "v2",
    "v3",
    "v1:",
    "v2:",
    "v3:",
    "no",
    "yes / no",
    "check:",
    "remove",
    "weaken",
    "replace",
    "survived because",
    "survived because:",
    "reasoning",
    "concern",
    "test, n days",
    "[test, n days]",
}


def _is_decision_md(file_path: str) -> bool:
    """Return True if the path is a decision.md inside an experiments/ directory."""
    p = Path(file_path)
    return p.name == "decision.md" and "experiments" in set(p.parts)


def _has_reject(content: str) -> bool:
    """Return True if decision.md marks REJECT as the chosen verdict."""
    return bool(re.search(r"\[x\]\s*REJECT", content, re.IGNORECASE))


def _is_placeholder(val: str) -> bool:
    """Return True if a cell/value is empty or pure template scaffolding."""
    v = val.strip().lower().strip("{}[]()* ")
    if not v:
        return True
    return v in _PLACEHOLDERS


def _section(content: str, phrase: str) -> str | None:
    """Extract a markdown section body by header phrase.

    Matches the first header (## or deeper) whose text contains `phrase`,
    returns lines until the next header of the same-or-higher level.
    """
    lines = content.splitlines()
    start = None
    start_level = 0
    for i, line in enumerate(lines):
        m = re.match(r"^(#{2,})\s+(.*)", line)
        if m and phrase.lower() in m.group(2).lower():
            start = i + 1
            start_level = len(m.group(1))
            break
    if start is None:
        return None
    out = []
    for line in lines[start:]:
        m = re.match(r"^(#{1,})\s+", line)
        if m and len(m.group(1)) <= start_level:
            break
        out.append(line)
    return "\n".join(out)


def _values_after_colon(section: str) -> list[str]:
    """Collect non-placeholder text that appears after a colon in real lines."""
    vals = []
    for raw in section.splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or (s.startswith("_") and s.endswith("_")):
            continue
        if ":" in s:
            after = s.split(":", 1)[1]
            after = re.sub(r"\{[^}]*\}", "", after)  # drop { } templates
            after = re.sub(r"\(.*?\)", "", after)  # drop (instructions)
            after = after.strip(" .{}[]")
            if after and not _is_placeholder(after):
                vals.append(after)
    return vals


def _check_what_killed(content: str) -> tuple[bool, str]:
    """Condition 1: 'What Was Killed' names a specific killed claim/assumption."""
    sec = _section(content, "What Was Killed")
    if sec is None:
        return False, "section 'What Was Killed' missing"
    if _values_after_colon(sec):
        return True, "'What Was Killed' filled ✓"
    return False, "'What Was Killed' empty — state what specifically was killed (not just braces)"


def _check_what_survived(content: str) -> tuple[bool, str]:
    """Condition 2: 'What Was NOT Killed' names >=1 surviving mechanism/assumption."""
    sec = _section(content, "What Was NOT Killed")
    if sec is None:
        return False, "section 'What Was NOT Killed' missing"
    for raw in sec.splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or (s.startswith("_") and s.endswith("_")):
            continue
        # A checked survivor box with trailing text counts.
        if re.search(r"\[x\]", s, re.IGNORECASE):
            txt = re.sub(r".*\[x\]", "", s, flags=re.IGNORECASE)
            txt = re.sub(r"\{[^}]*\}", "", txt)
            txt = txt.strip(" :.{}[]")
            if txt and not _is_placeholder(txt) and len(txt) > 3:
                return True, "'What Was NOT Killed' has a survivor ✓"
    if _values_after_colon(sec):
        return True, "'What Was NOT Killed' filled ✓"
    return False, "'What Was NOT Killed' empty — name at least one surviving assumption/mechanism"


def _check_relaxation_map(content: str) -> tuple[bool, str]:
    """Condition 3: Relaxation Map has >=1 real path (not A_/V1: placeholders)."""
    sec = _section(content, "Relaxation Map")
    if sec is None:
        return False, "Relaxation Map section missing — define what opens next"
    for raw in sec.splitlines():
        if not raw.strip().startswith("|"):
            continue
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if not cells:
            continue
        # Skip header row and separator row.
        if cells[0].lower() == "assumption" or set(cells[0]) <= set("-: "):
            continue
        assumption = cells[0]
        new_path = cells[2] if len(cells) > 2 else ""
        np_clean = re.sub(r"v[123]\s*:?", "", new_path, flags=re.IGNORECASE).strip(" :")
        if not _is_placeholder(assumption) and np_clean and not _is_placeholder(np_clean):
            return True, "Relaxation Map has a real path ✓"
    return False, "Relaxation Map empty (only A_/V1: placeholders) — define ≥1 path that opens next"


def _check_reason_specific(content: str) -> tuple[bool, str]:
    """Condition 4: kill reason is a structural constraint, not a vague feeling."""
    rationale = _section(content, "Rationale") or ""
    killed = _section(content, "What Was Killed") or ""
    blob = (rationale + " " + killed).lower()
    found = [v for v in VAGUE_REASONS if v in blob]
    if found:
        return (
            False,
            f"kill reason may be too vague ({found[0]!r}) — state the structural "
            "constraint, not just 'didn't work'",
        )
    return True, "kill reason specific ✓"


def main() -> None:
    # WHY: recursion guard — avoid loops inside Agent SDK sub-invocations.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    if data.get("tool_name", "") not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path or not _is_decision_md(file_path):
        sys.exit(0)

    content = tool_input.get("content") or tool_input.get("new_string", "")
    if not content:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            sys.exit(0)

    if not _has_reject(content):
        sys.exit(0)

    checks = [
        ("what was killed", _check_what_killed),
        ("what was NOT killed", _check_what_survived),
        ("relaxation map", _check_relaxation_map),
        ("reason specific", _check_reason_specific),
    ]

    results = []
    all_pass = True
    for name, fn in checks:
        try:
            passed, detail = fn(content)
        except Exception as e:  # noqa: BLE001 — a check bug must not break the write
            passed, detail = False, f"check failed: {e}"
        results.append(f"  {'✓' if passed else '✗'} {name}: {detail}")
        if not passed:
            all_pass = False

    if all_pass:
        msg = (
            "[null-gate] ✅ NULL Exploitation Gate passed — this REJECT opens the next step.\n"
            + "\n".join(results)
        )
    else:
        failed = sum(1 for r in results if r.strip().startswith("✗"))
        msg = (
            f"[null-gate] ⚠️  REJECT recorded but {failed}/4 conditions NOT met — "
            "the bonus chain breaks without 'what opens next'.\n"
            + "\n".join(results)
            + "\n\n→ A NULL without constraint-extraction is a dead end, not a fork. "
            "Fill the Kill Analysis before archiving."
        )

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": msg,
                }
            }
        )
    )


if __name__ == "__main__":
    main()
