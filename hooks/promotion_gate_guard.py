#!/usr/bin/env python3
"""Enforce Perelman promotion conditions on decision.md.

WHY: The FL Full-Ladder defines 5 promotion conditions (perelman-audit.md).
Without automated checking, engineers write "PROMOTE" in decision.md without
verifying that claim_entropy=0, controls exist, or real evidence is present.

Two enforcement legs (2026-07-07, cross-model audit finding
`promotion_gate_guard.py:198` -- "a [x] PROMOTE with failed conditions is
still persisted, hook only prints additionalContext after the write" --
closed per explicit user decision, same call as iteration_guard.py's cap=3:
"block, not just warn"):

  1. PostToolUse(Write|Edit): unchanged from before -- checks the
     already-written file and emits an additionalContext warning. Kept as a
     safety net for cases the PreToolUse reconstruction below can't cover
     (e.g. an old_string that can't be located in the current file).
  2. PreToolUse(Write|Edit): the actual gate. Reconstructs what decision.md
     WOULD contain after this specific tool call -- the full content for
     Write, or the current on-disk content with old_string->new_string
     applied for Edit (same reconstruction technique as syntax_guard.py's
     _reconstruct_edit_result, for the same reason: validating a fragment in
     isolation misses whether the FULL resulting file would say [x] PROMOTE).
     If the reconstructed content marks PROMOTE and any of the 5 conditions
     fail, denies the write outright (permissionDecision: deny).

Fires on: PreToolUse(Write|Edit), PostToolUse(Write|Edit) to any
**/experiments/**/decision.md. Checks 5 conditions when PROMOTE verdict is
detected:
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

sys.path.insert(0, str(Path(__file__).parent))

from claim_entropy_tracker import entropy_mismatch, parse_entropy  # noqa: E402


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
    """Condition 1: claim_entropy in claim.md must be 0, and internally consistent.

    WHY reuse claim_entropy_tracker's parse_entropy/entropy_mismatch instead of
    a separate ad hoc regex: this function previously re-implemented its own
    Total-row regex, which (like the original bug in claim_entropy_tracker.py)
    trusted a hand-edited Total row without cross-checking it against the
    component rows — a claim could pass PROMOTE with claim_entropy=0 by
    editing only the Total line while components stayed unresolved.
    """
    claim_md = exp_dir / "claim.md"
    if not claim_md.exists():
        return False, "claim.md missing — cannot verify entropy"

    content = claim_md.read_text(encoding="utf-8")

    mismatch_sum = entropy_mismatch(content)
    if mismatch_sum is not None:
        return (
            False,
            f"Total claim_entropy row disagrees with component rows "
            f"(components sum to {mismatch_sum}) — fix before PROMOTE",
        )

    entropy_val = parse_entropy(content)
    if entropy_val is None:
        # Also try the claim_entropy_tracker state file.
        # WHY "entropy" key, not "current": claim_entropy_tracker.save_state()
        # writes {"entropy": current} -- reading "current" here always missed,
        # silently defaulting to -1 and failing this check even when the
        # tracked state was genuinely 0.
        state_file = exp_dir / ".claim_entropy_state.json"
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
                current = state.get("entropy", -1)
                if current == 0:
                    return True, "claim_entropy=0 (from state file)"
                return False, f"claim_entropy={current} (must be 0)"
            except (json.JSONDecodeError, KeyError):
                pass
        return False, "Total claim_entropy row not found in claim.md"

    if entropy_val == 0:
        return True, "claim_entropy=0 ✓"
    return False, f"claim_entropy={entropy_val} (must reach 0 before PROMOTE)"


_RESULT_CHECKED_RE = re.compile(r"\*\*Result:\*\*\s*\[x\]", re.IGNORECASE)
_NOCOLLAPSE_ROW_CHECKED_RE = re.compile(r"\[x\]\s*(PASS|FAIL)", re.IGNORECASE)
_MIN_NOCOLLAPSE_TESTS = 3  # Standard-Ladder minimum per experiments/_template/controls.md


def _section(content: str, heading: str) -> str | None:
    """Return the body of a ## heading section (up to the next ## heading), or None."""
    idx = content.find(heading)
    if idx == -1:
        return None
    rest = content[idx + len(heading) :]
    next_heading = rest.find("\n## ")
    return rest[:next_heading] if next_heading != -1 else rest


def _check_controls(exp_dir: Path) -> tuple[bool, str]:
    """Condition 2: controls.md exists with an actually-run positive AND negative control.

    WHY not just file existence: an empty or freshly-templated controls.md
    (Input/Expected output blank, Result checkboxes unmarked) previously
    satisfied this condition, per experiments/_template/controls.md's own
    "Result: [ ] PASS [ ] FAIL" placeholder.
    """
    controls = exp_dir / "controls.md"
    if not controls.exists():
        return False, "controls.md missing — add positive+negative controls first"

    content = controls.read_text(encoding="utf-8")
    positive = _section(content, "## Positive Control")
    negative = _section(content, "## Negative Control")

    missing = []
    if positive is None:
        missing.append("## Positive Control section missing")
    elif not _RESULT_CHECKED_RE.search(positive):
        missing.append("Positive Control not marked as run (Result: [x] ...)")
    if negative is None:
        missing.append("## Negative Control section missing")
    elif not _RESULT_CHECKED_RE.search(negative):
        missing.append("Negative Control not marked as run (Result: [x] ...)")

    if missing:
        return False, "controls.md incomplete — " + "; ".join(missing)
    return True, "controls.md has positive+negative controls actually run ✓"


def _check_no_collapse(exp_dir: Path) -> tuple[bool, str]:
    """Condition 3: controls.md has a real (not placeholder) No-Collapse Tests section.

    WHY not a bare substring check: "TODO: No-Collapse Tests" previously
    satisfied this condition by containing the word "No-Collapse" with zero
    actual tests run. Require at least Standard-Ladder minimum (3) rows
    marked [x] PASS/FAIL in the table.
    """
    controls = exp_dir / "controls.md"
    if not controls.exists():
        return False, "controls.md missing (checked in condition 2)"
    content = controls.read_text(encoding="utf-8")
    section = _section(content, "## No-Collapse Tests")
    if section is None:
        return False, "controls.md lacks ## No-Collapse Tests section (Perelman stability check)"

    checked = _NOCOLLAPSE_ROW_CHECKED_RE.findall(section)
    if len(checked) < _MIN_NOCOLLAPSE_TESTS:
        return (
            False,
            f"## No-Collapse Tests present but only {len(checked)}/{_MIN_NOCOLLAPSE_TESTS} "
            "minimum tests marked run",
        )
    return True, f"No-Collapse Tests: {len(checked)} tests marked run ✓"


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


# WHY require citation SHAPE, not just marker presence (F-04, external audit
# 2026-07-15): the TODO/placeholder exclusion below already closed the
# literal "TODO: add [VERIFIED-REAL] later" bypass, but a line like
# "[VERIFIED-REAL] source: trust me" is neither TODO nor a real citation --
# no URL, no file reference, no commit hash. That line is not a placeholder,
# so it previously satisfied this condition with zero actual evidence trail
# a reviewer could check. Each alternative below is a distinct citation
# shape: a URL, a commit-hash-looking hex token (7-40 chars, all in [0-9a-f]
# -- vanishingly unlikely to occur as an ordinary English word by chance),
# or a file-path-like reference (dir/file.ext).
_CITATION_SHAPE_PATTERN = re.compile(
    r"https?://\S+" r"|\b[0-9a-f]{7,40}\b" r"|\S+/\S+\.\w+",
)


def _check_external_reconstruction(exp_dir: Path) -> tuple[bool, str]:
    """Condition 5: [VERIFIED-REAL] must appear in result_summary.md, on a
    line that carries an actual citation (URL / commit hash / file path).

    WHY: Perelman condition 5 requires external reconstruction — an independent
    party reproduced the result. The canonical place to document this is
    result_summary.md, not scattered across the experiment dir. Requiring it
    there forces the author to explicitly acknowledge the external source —
    and requiring a real citation shape (not just the marker string) forces
    that acknowledgment to point at something a reviewer can actually check.
    """
    result_md = exp_dir / "result_summary.md"
    if not result_md.exists():
        return (
            False,
            "result_summary.md missing — external reconstruction cannot be verified",
        )
    content = result_md.read_text(encoding="utf-8")

    # WHY check the surrounding line, not just marker presence: a TODO/
    # template line containing the marker string ("TODO: add [VERIFIED-REAL]
    # later") previously satisfied this condition with zero real evidence.
    found_todo_only = False
    found_uncited = False
    for match in re.finditer(re.escape("[VERIFIED-REAL]"), content):
        line_start = content.rfind("\n", 0, match.start()) + 1
        line_end = content.find("\n", match.end())
        line = content[line_start : line_end if line_end != -1 else len(content)]
        if re.search(r"\bTODO\b|\bTBD\b|\bplaceholder\b", line, re.IGNORECASE):
            found_todo_only = True
            continue
        if not _CITATION_SHAPE_PATTERN.search(line):
            found_uncited = True
            continue  # marker present, not a placeholder, but no real citation on this line
        return True, "[VERIFIED-REAL] in result_summary.md — external reconstruction confirmed ✓"

    if found_uncited:
        return (
            False,
            "result_summary.md has [VERIFIED-REAL] but no real citation (URL, commit hash, or "
            "file path) on that line — add an actual external source reference, not just the "
            "marker string",
        )
    if found_todo_only:
        return (
            False,
            "result_summary.md has [VERIFIED-REAL] only in a TODO/placeholder line — "
            "add a real external source citation",
        )
    return (
        False,
        "result_summary.md exists but lacks [VERIFIED-REAL] — add external source citation",
    )


# WHY: keep old name as alias so existing callers / manual tests don't break
_check_verified_real = _check_external_reconstruction

_CHECKS = [
    ("claim_entropy=0", _check_claim_entropy),
    ("controls.md", _check_controls),
    ("no-collapse tests", _check_no_collapse),
    ("result_summary.md", _check_result_summary),
    ("external reconstruction", _check_external_reconstruction),
]


def _run_checks(exp_dir: Path) -> tuple[list[str], bool]:
    """Run all 5 Perelman conditions, return (formatted lines, all_pass)."""
    results = []
    all_pass = True
    for name, fn in _CHECKS:
        try:
            passed, detail = fn(exp_dir)
        except Exception as e:
            passed, detail = False, f"check failed: {e}"
        symbol = "✓" if passed else "✗"
        results.append(f"  {symbol} {name}: {detail}")
        if not passed:
            all_pass = False
    return results, all_pass


def _reconstruct_content(file_path: str, tool_input: dict) -> str:
    """Best-effort reconstruction of decision.md's content AFTER this tool
    call -- for the PreToolUse leg, where the write hasn't happened yet.

    WHY (mirrors syntax_guard.py's _reconstruct_edit_result, same reasoning):
    validating just old_string/new_string in isolation misses whether the
    FULL resulting file would actually say [x] PROMOTE -- e.g. an edit to an
    unrelated section of a decision.md that ALREADY has PROMOTE set must
    still be checked against the reconstructed whole file, not just the
    edited fragment.
    """
    if "content" in tool_input:  # Write — content IS the full proposed file
        return str(tool_input.get("content", ""))

    # Edit — apply the same old_string -> new_string replacement Edit itself
    # will perform, against the CURRENT on-disk content (write hasn't
    # happened yet at PreToolUse time).
    # WHY str() (mypy CI failure, 2026-07-07): tool_input is an untyped dict,
    # so .get() returns Any -- str() narrows it to match this function's
    # declared -> str return type without weakening tool_input's own type.
    old_string = str(tool_input.get("old_string", ""))
    new_string = str(tool_input.get("new_string", ""))
    try:
        current = Path(file_path).read_text(encoding="utf-8")
    except OSError:
        return new_string  # file doesn't exist yet -- best available guess

    # WHY `old_string and ...` (P2, reviewer-agent pass): this is a
    # deliberate divergence from syntax_guard.py's _reconstruct_edit_result,
    # which checks `if old_string not in current: return None` -- for
    # old_string="", that's False (empty string is a substring of
    # everything), so syntax_guard proceeds to insert new_string. Here,
    # old_string="" falls through to "return current" (unmodified) instead.
    # Not exploitable in practice: Claude Code's real Edit contract requires
    # a non-empty, verbatim-matching old_string, so this shouldn't occur
    # from a genuine tool call -- and if it somehow did, this is the SAFER
    # failure direction (silently skip gating) versus the alternative
    # (silently insert new_string everywhere).
    if old_string and old_string in current:
        replace_all = bool(tool_input.get("replace_all", False))
        count = -1 if replace_all else 1
        return current.replace(old_string, new_string, count)
    # old_string not found -- Edit itself would fail for the same reason,
    # not this hook's job to catch. Fall back to current on-disk content.
    return current


def _handle_pre_tool_use(data: dict) -> None:
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path or not _is_decision_md(file_path):
        sys.exit(0)

    content = _reconstruct_content(file_path, tool_input)
    if not _has_promote(content):
        sys.exit(0)  # this write doesn't result in PROMOTE — nothing to gate

    exp_dir = _get_experiment_dir(file_path)
    results, all_pass = _run_checks(exp_dir)

    if all_pass:
        sys.exit(0)  # all 5 Perelman conditions met — allow

    failed_count = sum(1 for r in results if r.strip().startswith("✗"))
    reason = (
        f"[promotion-gate] PROMOTE requested but {failed_count}/5 Perelman conditions "
        "NOT met — write blocked.\n"
        + "\n".join(results)
        + "\n\n→ Fix failing conditions before marking PROMOTE."
        " Partial PROMOTE = REPEAT (need more data), not failure."
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def _handle_post_tool_use(data: dict) -> None:
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
    results, all_pass = _run_checks(exp_dir)

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

    # WHY this discriminator: PostToolUse payloads carry tool_response;
    # PreToolUse payloads never do. Cross-checked (reviewer-agent pass,
    # 2026-07-07): weakened_test_guard.py and commit_test_gate.py already use
    # this identical "tool_response" in data check for the same Pre/Post-
    # in-one-file pattern; no PreToolUse-only hook in this repo constructs a
    # tool_response key.
    is_post = "tool_response" in data
    if is_post:
        _handle_post_tool_use(data)
    else:
        _handle_pre_tool_use(data)


if __name__ == "__main__":
    main()
