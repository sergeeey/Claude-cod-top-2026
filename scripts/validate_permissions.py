#!/usr/bin/env python3
"""Validate hooks/settings.json permission patterns against a typed schema.

Borrowed concept from OpenCode's PermissionV1.Ruleset — structured validation
of allow/deny patterns catches typos before they silently disable security guards.

Usage:
    python scripts/validate_permissions.py [path/to/settings.json]
    python scripts/validate_permissions.py --json   # machine-readable output

Exits 0 on success, 1 on validation errors.
Can also be imported for use in tests.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent.parent

# ── Schema ────────────────────────────────────────────────────────────────────

# Known Claude Code tool names that appear in permission patterns.
KNOWN_TOOLS: frozenset[str] = frozenset(
    {
        "Bash",
        "Read",
        "Write",
        "Edit",
        "Grep",
        "Glob",
        "Task",
        "TaskCreate",
        "TaskUpdate",
        "TaskGet",
        "TaskList",
        "TaskStop",
        "TaskOutput",
        "WebFetch",
        "WebSearch",
        "Skill",
        "NotebookEdit",
        "Agent",
        "Artifact",
        "AskUserQuestion",
        "ScheduleWakeup",
        "SendMessage",
        "EnterPlanMode",
        "ExitPlanMode",
        "EnterWorktree",
        "ExitWorktree",
        "Workflow",
    }
)

# ToolName(glob) — tool can be mcp__server__method or a known name
_PATTERN_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)(\(.*\))?$")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _validate_single_pattern(pattern: str, section: str) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for one allow/deny pattern string."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(pattern, str):
        errors.append(f"{section}: non-string entry {pattern!r}")
        return errors, warnings

    # MCP tool patterns: mcp__server__method — no parentheses needed
    if pattern.startswith("mcp__"):
        parts = pattern.split("__")
        if len(parts) < 3:
            warnings.append(f"{section}: mcp pattern has fewer than 3 parts: {pattern!r}")
        return errors, warnings

    # Standard tool pattern: ToolName(glob)
    m = _PATTERN_RE.match(pattern)
    if not m:
        errors.append(f"{section}: malformed pattern (expected ToolName(glob)): {pattern!r}")
        return errors, warnings

    tool_name = m.group(1)
    glob_part = m.group(2)  # includes parentheses, e.g. "(*.py)"

    if glob_part is None:
        # Pattern like "Bash" without parens — valid as a bare tool match
        pass
    else:
        inner = glob_part[1:-1]  # strip outer parentheses
        if not inner:
            errors.append(f"{section}: empty glob in pattern: {pattern!r}")

    if tool_name not in KNOWN_TOOLS:
        warnings.append(
            f"{section}: unrecognized tool name {tool_name!r} in {pattern!r} — "
            "may be intentional for future tools"
        )

    return errors, warnings


def validate_settings(settings: dict) -> ValidationResult:
    """Validate the permissions block of a parsed settings.json."""
    result = ValidationResult()
    permissions = settings.get("permissions", {})

    if not isinstance(permissions, dict):
        result.errors.append("permissions must be a dict, got " + type(permissions).__name__)
        return result

    allow_patterns = permissions.get("allow", [])
    deny_patterns = permissions.get("deny", [])

    if not isinstance(allow_patterns, list):
        result.errors.append("permissions.allow must be a list")
    else:
        for p in allow_patterns:
            errs, warns = _validate_single_pattern(p, "permissions.allow")
            result.errors.extend(errs)
            result.warnings.extend(warns)

    if not isinstance(deny_patterns, list):
        result.errors.append("permissions.deny must be a list")
    else:
        for p in deny_patterns:
            errs, warns = _validate_single_pattern(p, "permissions.deny")
            result.errors.extend(errs)
            result.warnings.extend(warns)

    # Contradiction check: same pattern in both allow and deny
    if isinstance(allow_patterns, list) and isinstance(deny_patterns, list):
        contradictions = sorted(set(allow_patterns) & set(deny_patterns))
        for c in contradictions:
            result.errors.append(
                f"contradiction: {c!r} appears in both permissions.allow and permissions.deny"
            )

    return result


def validate_file(path: Path) -> ValidationResult:
    """Load and validate a settings.json file."""
    result = ValidationResult()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        result.errors.append(f"cannot read {path}: {e}")
        return result

    try:
        settings = json.loads(text)
    except json.JSONDecodeError as e:
        result.errors.append(f"invalid JSON in {path}: {e}")
        return result

    return validate_settings(settings)


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Claude Code settings.json permissions")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(ROOT / "hooks" / "settings.json"),
        help="Path to settings.json (default: hooks/settings.json)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    settings_path = Path(args.path)
    result = validate_file(settings_path)

    if args.json_output:
        print(json.dumps({"ok": result.ok, "errors": result.errors, "warnings": result.warnings}))
        return 0 if result.ok else 1

    if result.ok and not result.warnings:
        print(f"✓ {settings_path}: permissions valid ({0} errors, {0} warnings)")
        return 0

    if result.warnings:
        for w in result.warnings:
            print(f"  ⚠  {w}", file=sys.stderr)

    if result.errors:
        print(f"✗ {settings_path}: {len(result.errors)} error(s)", file=sys.stderr)
        for e in result.errors:
            print(f"  ✗  {e}", file=sys.stderr)
        return 1

    print(f"✓ {settings_path}: permissions valid ({len(result.warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
