#!/usr/bin/env python3
"""PostToolUse hook: enforce Perelman monotone invariant on claim_entropy.

WHY: claim_entropy must strictly decrease with each valid step (Perelman's
W-functional principle, integrated in perelman-audit.md). Without automated
tracking, this invariant is checked "by feel" — meaning it's not checked.
This hook enforces monotonicity at write-time:
  • entropy decreased → silent pass (valid step)
  • entropy unchanged/increased → context nudge (step not counted)
  • entropy = 0, all fields filled → promotion-ready notification

Triggers on: PostToolUse(Write|Edit) matching **/experiments/**/claim.md
"""

import json
import os
import re
import sys
from pathlib import Path

from utils import emit_hook_result, parse_stdin

HOOK_NAME = "claim_entropy_tracker"
ENTROPY_SECTION = "## Claim Entropy"
STATE_FILE_NAME = ".claim_entropy_state.json"

# Matches any 2-cell markdown table row: | label | count |
_CELL_RE = re.compile(r"^\|\s*(.+?)\s*\|\s*(\d*)\s*\|\s*$")

# Matches the explicit Total row: | **Total claim_entropy** | 7 |
_TOTAL_RE = re.compile(
    r"^\|\s*\*\*Total claim_entropy\*\*\s*\|\s*(\d+)\s*\|",
    re.MULTILINE,
)


def _iter_component_rows(section: str):
    """Yield (label, count_str) for each genuine data row in a Claim Entropy table.

    Skips the header row, the separator row, and the explicit Total row.

    WHY line-based, not a single regex with a negative-lookahead exclusion:
    a shared `\\s*` right before a lookahead can backtrack to zero characters
    whenever that lets the lookahead pass (regex engines backtrack greedy
    quantifiers to make the overall match succeed) — this let a
    leading-space variant of "**Total"/"Component" slip through the old
    `_ROW_RE` and get counted as a data row, silently doubling the computed
    total by counting the Total row as its own component. Checking each
    line's label text directly, after the table structure is already
    parsed out, avoids that whole class of lookahead/backtracking bug.
    """
    for line in section.splitlines():
        match = _CELL_RE.match(line.strip())
        if not match:
            continue
        label = match.group(1).strip()
        if label.lower() == "component" or label.startswith("**Total") or set(label) <= {"-"}:
            continue
        yield label, match.group(2).strip()


def is_claim_md(file_path: str) -> bool:
    """Return True if file_path is experiments/**/claim.md."""
    p = Path(file_path)
    return p.name == "claim.md" and "experiments" in p.parts


def _component_sum(section: str) -> int | None:
    """Sum only the component rows of an already-sliced Claim Entropy section.

    Returns None if there are no rows, or none of them have a value filled in.
    """
    rows = list(_iter_component_rows(section))
    if not rows:
        return None
    has_value = False
    total = 0
    for _, count_str in rows:
        if count_str:
            total += int(count_str)
            has_value = True
    return total if has_value else None


def parse_entropy(content: str) -> int | None:
    """Extract claim_entropy total from ## Claim Entropy table.

    Prefers the explicit Total row; falls back to summing component rows.
    Returns None if the section is absent or no values have been filled in.
    """
    idx = content.find(ENTROPY_SECTION)
    if idx == -1:
        return None
    section = content[idx:]

    # Explicit total takes precedence
    total_match = _TOTAL_RE.search(section)
    if total_match:
        return int(total_match.group(1))

    return _component_sum(section)


def entropy_mismatch(content: str) -> int | None:
    """Return the component-row sum if it disagrees with an explicit Total row.

    Returns None when there is nothing to cross-check (no Total row, or no
    component rows to sum) — in that case parse_entropy()'s value stands as-is.

    WHY: an explicit "| **Total claim_entropy** | 0 |" row can be hand-edited
    independently of the component rows it's supposed to summarize — a claim
    can keep unresolved nonzero component rows while the Total row alone is
    set to 0, and parse_entropy() would previously trust the Total row
    unconditionally. This lets the caller detect and reject that case instead
    of accepting a hollow claim_entropy=0.
    """
    idx = content.find(ENTROPY_SECTION)
    if idx == -1:
        return None
    section = content[idx:]

    total_match = _TOTAL_RE.search(section)
    if not total_match:
        return None

    component_sum = _component_sum(section)
    if component_sum is None:
        return None

    total_value = int(total_match.group(1))
    return component_sum if component_sum != total_value else None


def load_state(path: Path) -> dict:
    """Load previous entropy state. Returns {} if file missing or corrupt."""
    try:
        result: dict = json.loads(path.read_text(encoding="utf-8"))
        return result
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_state(path: Path, state: dict) -> None:
    """Atomically write entropy state JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True)


def main() -> None:
    # Recursion guard: skip if running inside Claude agent invocation
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    data = parse_stdin()
    if not data:
        sys.exit(0)

    if data.get("tool_name") not in ("Write", "Edit"):
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path or not is_claim_md(file_path):
        sys.exit(0)

    try:
        content = Path(file_path).read_text(encoding="utf-8")
    except OSError:
        sys.exit(0)

    current = parse_entropy(content)
    if current is None:
        sys.exit(0)  # Section not filled yet — nothing to enforce

    mismatch_sum = entropy_mismatch(content)
    if mismatch_sum is not None:
        # WHY: don't persist state on a mismatched read — a hand-edited Total
        # row that disagrees with the components is untrustworthy either way,
        # so the last genuinely valid checkpoint should survive it.
        emit_hook_result(
            "PostToolUse",
            f"[claim-entropy] ⚠ Total claim_entropy row disagrees with the sum "
            f"of component rows (components sum to {mismatch_sum}). Fix the "
            "Total row or resolve the listed components — not counted as a step.",
        )
        return

    state_path = Path(file_path).parent / STATE_FILE_NAME
    state = load_state(state_path)
    prev = state.get("entropy")

    if current == 0:
        save_state(state_path, {"entropy": current})
        emit_hook_result(
            "PostToolUse",
            "[claim-entropy] claim_entropy=0 — all fields resolved. "
            "Check 5-condition promotion gate in perelman-audit.md before advancing.",
        )
    elif prev is None:
        save_state(state_path, {"entropy": current})
        emit_hook_result(
            "PostToolUse",
            f"[claim-entropy] Baseline set: entropy={current}. "
            "Every subsequent step must decrease this number.",
        )
    elif current < prev:
        save_state(state_path, {"entropy": current})  # Valid step — persist and stay silent
    else:
        # WHY no save_state here: persisting a non-decreasing value would let
        # a later step "decrease" from this already-invalid number instead of
        # the last genuinely valid checkpoint — silently defeating the gate.
        direction = "unchanged" if current == prev else f"increased from {prev}"
        emit_hook_result(
            "PostToolUse",
            f"[claim-entropy] ⚠ Perelman invariant violated: "
            f"entropy[t+1]={current} ≥ entropy[t]={prev} ({direction}). "
            "Step not counted. Resolve at least one open field before advancing.",
        )


if __name__ == "__main__":
    main()
