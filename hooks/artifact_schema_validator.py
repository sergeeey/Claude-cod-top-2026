"""
artifact_schema_validator.py — PostToolUse(Write|Edit) hook.

Validates JSON artifacts written to known experiment/metrics/results directories.
If a companion *.schema.json exists, validates with jsonschema (if installed).
"""

from __future__ import annotations

import json
import os
import sys

# ── Recursion guard ──────────────────────────────────────────────────────────
GUARD_ENV = "CLAUDE_ARTIFACT_SCHEMA_VALIDATOR_RUNNING"
if os.environ.get(GUARD_ENV):
    sys.exit(0)
os.environ[GUARD_ENV] = "1"

# ── Known directories that should contain only valid JSON ────────────────────
WATCHED_DIRS = ("experiments/", "metrics/", "results/")


def _in_watched_dir(path: str) -> bool:
    norm = path.replace("\\", "/")
    return any(d in norm for d in WATCHED_DIRS)


def _validate(path: str, content: str) -> None:
    if not path.endswith(".json"):
        return
    if not _in_watched_dir(path):
        return

    # 1. Basic JSON validity
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        print(
            f"[artifact_schema_validator] WARN: invalid JSON in {path}: {exc}",
            file=sys.stderr,
        )
        return  # warn-only, never block

    # 2. Schema validation (future-ready, optional)
    schema_path = path.replace(".json", ".schema.json")
    if not os.path.isfile(schema_path):
        return  # no schema → ok

    try:
        import jsonschema  # type: ignore[import]
    except ImportError:
        return  # library not installed → skip silently

    with open(schema_path, encoding="utf-8") as fh:
        schema = json.load(fh)

    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as exc:
        print(
            f"[artifact_schema_validator] WARN: {path} fails schema ({schema_path}): {exc.message}",
            file=sys.stderr,
        )


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        return

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return

    tool = event.get("tool_name", "")
    if tool not in ("Write", "Edit"):
        return

    inp = event.get("tool_input", {})

    if tool == "Write":
        path = inp.get("file_path", "")
        content = inp.get("content", "")
        _validate(path, content)

    elif tool == "Edit":
        path = inp.get("file_path", "")
        new_str = inp.get("new_string", "")
        # For Edit we only have a fragment; try to validate it as JSON snippet.
        # If path is JSON and in watched dir, warn that full validation
        # requires reading the file. Attempt lightweight parse of new_string.
        if path.endswith(".json") and _in_watched_dir(path):
            if new_str.strip():
                try:
                    json.loads(new_str)
                except json.JSONDecodeError as exc:
                    print(
                        f"[artifact_schema_validator] WARN: new_string in {path} "
                        f"is not valid JSON (may be a partial edit): {exc}",
                        file=sys.stderr,
                    )


if __name__ == "__main__":
    main()
