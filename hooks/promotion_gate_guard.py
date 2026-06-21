#!/usr/bin/env python3
"""PostToolUse(Write|Edit) hook: enforce Perelman promotion conditions on decision.md.

WHY: The FL Full-Ladder defines 5 promotion conditions (perelman-audit.md).
Without automated checking, engineers write "PROMOTE" in decision.md without
verifying that claim_entropy=0, controls exist, or real evidence is present.
This hook catches it before the decision is persisted.

Fires on: Write|Edit to any **/experiments/**/decision.md
Checks 5 conditions when PROMOTE verdict is detected:
  1. claim_entropy = 0          (claim.md Total row must be 0)
  2. controls.md exists         (positive + negative controls documented)
  3. no-collapse tests          (controls.md has ## No-Collapse Tests section)
  4. result_summary.md          (metrics captured before deciding)
  5. external reconstruction    ([VERIFIED-REAL] present in result_summary.md — not
                                  just anywhere in the dir; Perelman condition 5)
"""

import json
import os
import re
import sys
from pathlib import Path


def _is_decision_md(file_path: str) -> bool:
    """Return True if the path is a decision.md inside an experiments/ directory."""
    p = Path(file_path)
    return p.name == "decision.md" and "experiments" in {part for part in p.parts}


def _has_promote(content: str) -> bool:
    """Return True if decision.md marks PROMOTE as the chosen verdict.

    Only counts [x] PROMOTE, not commented-out or mentioned alternatives.
    """
    return bool(re.search(r"\[x\]\s*PROMOTE", content, re.IGNORECASE))


def _get_experiment_dir(file_path: str) -> Path:
    """Return the directory containing this decision.md."""
    return Path(file_path).parent


def _check_claim_entropy(exp_dir: Path) -> tuple[bool, str]:
    """Condition 1: claim_entropy in claim.md must be 0."""
    claim_md = exp_dir / "claim.md"
    if not claim_md.exists():
        return False, "claim.md missing — cannot verify entropy"

    content = claim_md.read_text(encoding="utf-8")
    # Look for: | **Total claim_entropy** | 0 |
    match = re.search(r"\|\s*\*\*Total claim_entropy\*\*\s*\|\s*(\d+)\s*\|", content)
    if not match:
        # Also try the claim_entropy_tracker state file
        state_file = exp_dir / ".claim_entropy_state.json"
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
                current = state.get("current", -1)
                if current == 0:
                    return True, "claim_entropy=0 (from state file)"
                return False, f"claim_entropy={current} (must be 0)"
            except (json.JSONDecodeError, KeyError):
                pass
        return False, "Total claim_entropy row not found in claim.md"

    entropy_val = int(match.group(1))
    if entropy_val == 0:
        return True, "claim_entropy=0 ✓"
    return False, f"claim_entropy={entropy_val} (must reach 0 before PROMOTE)"


def _check_controls(exp_dir: Path) -> tuple[bool, str]:
    """Condition 2: controls.md exists."""
    controls = exp_dir / "controls.md"
    if controls.exists():
        return True, "controls.md exists ✓"
    return False, "controls.md missing — add positive+negative controls first"


def _check_no_collapse(exp_dir: Path) -> tuple[bool, str]:
    """Condition 3: controls.md has ## No-Collapse Tests section."""
    controls = exp_dir / "controls.md"
    if not controls.exists():
        return False, "controls.md missing (checked in condition 2)"
    content = controls.read_text(encoding="utf-8")
    if "## No-Collapse Tests" in content or "No-Collapse" in content:
        return True, "No-Collapse Tests section present ✓"
    return False, "controls.md lacks ## No-Collapse Tests section (Perelman stability check)"


def _check_result_summary(exp_dir: Path) -> tuple[bool, str]:
    """Condition 4: result_summary.md or metrics/run.json exists."""
    if (exp_dir / "result_summary.md").exists():
        return True, "result_summary.md exists ✓"
    if (exp_dir / "metrics" / "run.json").exists():
        return True, "metrics/run.json exists ✓"
    return (
        False,
        "result_summary.md (or metrics/run.json) missing — capture results before deciding",
    )


def _check_external_reconstruction(exp_dir: Path) -> tuple[bool, str]:
    """Condition 5: [VERIFIED-REAL] must appear in result_summary.md.

    WHY: Perelman condition 5 requires external reconstruction — an independent
    party reproduced the result. The canonical place to document this is
    result_summary.md, not scattered across the experiment dir. Requiring it
    there forces the author to explicitly acknowledge the external source.
    """
    result_md = exp_dir / "result_summary.md"
    if not result_md.exists():
        return (
            False,
            "result_summary.md missing — external reconstruction cannot be verified",
        )
    content = result_md.read_text(encoding="utf-8")
    if "[VERIFIED-REAL]" in content:
        return True, "[VERIFIED-REAL] in result_summary.md — external reconstruction confirmed ✓"
    return (
        False,
        "result_summary.md exists but lacks [VERIFIED-REAL] — add external source citation",
    )


# WHY: keep old name as alias so existing callers / manual tests don't break
_check_verified_real = _check_external_reconstruction


def main() -> None:
    # WHY: recursion guard
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path or not _is_decision_md(file_path):
        sys.exit(0)

    # Read content — for Write it's in tool_input.content; for Edit it's new_string
    content = tool_input.get("content") or tool_input.get("new_string", "")
    if not content:
        # Try reading the actual file (PostToolUse — file is already written)
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            sys.exit(0)

    if not _has_promote(content):
        sys.exit(0)

    exp_dir = _get_experiment_dir(file_path)

    checks = [
        ("claim_entropy=0", _check_claim_entropy),
        ("controls.md", _check_controls),
        ("no-collapse tests", _check_no_collapse),
        ("result_summary.md", _check_result_summary),
        ("external reconstruction", _check_external_reconstruction),
    ]

    results = []
    all_pass = True
    for name, fn in checks:
        try:
            passed, detail = fn(exp_dir)
        except Exception as e:
            passed, detail = False, f"check failed: {e}"
        symbol = "✓" if passed else "✗"
        results.append(f"  {symbol} {name}: {detail}")
        if not passed:
            all_pass = False

    if all_pass:
        msg = "[promotion-gate] ✅ All 5 Perelman promotion conditions satisfied.\n" + "\n".join(
            results
        )
    else:
        failed_count = sum(1 for r in results if r.strip().startswith("✗"))
        msg = (
            f"[promotion-gate] ⚠️  PROMOTE requested but {failed_count}/5 conditions NOT met.\n"
            + "\n".join(results)
            + "\n\n→ Fix failing conditions before marking PROMOTE."
            " Partial PROMOTE = REPEAT (need more data), not failure."
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
