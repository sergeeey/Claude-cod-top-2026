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

# Matches data rows in the Claim Entropy table (skips header, separator, Total)
# Example: | Unsupported HIGH claims | 3 |
_ROW_RE = re.compile(
    r"^\|\s*(?!\*\*Total|\-\-\-|Component|\s*$)(.+?)\s*\|\s*(\d*)\s*\|",
    re.MULTILINE,
)

# Matches the explicit Total row: | **Total claim_entropy** | 7 |
_TOTAL_RE = re.compile(
    r"^\|\s*\*\*Total claim_entropy\*\*\s*\|\s*(\d+)\s*\|",
    re.MULTILINE,
)


def is_claim_md(file_path: str) -> bool:
    """Return True if file_path is experiments/**/claim.md."""
    p = Path(file_path)
    return p.name == "claim.md" and "experiments" in p.parts


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

    # Sum component rows
    rows = _ROW_RE.findall(section)
    if not rows:
        return None
    has_value = False
    total = 0
    for _, count_str in rows:
        count_str = count_str.strip()
        if count_str:
            total += int(count_str)
            has_value = True
    return total if has_value else None


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

    state_path = Path(file_path).parent / STATE_FILE_NAME
    state = load_state(state_path)
    prev = state.get("entropy")

    save_state(state_path, {"entropy": current})

    if current == 0:
        emit_hook_result(
            "PostToolUse",
            "[claim-entropy] claim_entropy=0 — all fields resolved. "
            "Check 5-condition promotion gate in perelman-audit.md before advancing.",
        )
    elif prev is None:
        emit_hook_result(
            "PostToolUse",
            f"[claim-entropy] Baseline set: entropy={current}. "
            "Every subsequent step must decrease this number.",
        )
    elif current < prev:
        pass  # Valid step — silent
    else:
        direction = "unchanged" if current == prev else f"increased from {prev}"
        emit_hook_result(
            "PostToolUse",
            f"[claim-entropy] ⚠ Perelman invariant violated: "
            f"entropy[t+1]={current} ≥ entropy[t]={prev} ({direction}). "
            "Step not counted. Resolve at least one open field before advancing.",
        )


if __name__ == "__main__":
    main()
