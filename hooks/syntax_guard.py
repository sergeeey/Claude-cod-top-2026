#!/usr/bin/env python3
"""PreToolUse hook: validate Python/JS syntax before Write/Edit.

WHY: Claude generates code → writes to disk → runs → SyntaxError → rewrites.
This cycle wastes tokens and breaks flow. Catching syntax errors BEFORE disk
write eliminates it entirely. Python ast.parse() takes ~0.3ms on 500 lines.

Coverage:
  .py  → stdlib ast.parse() (zero dependencies)
  .js  → node --check (skipped if node not in PATH)
  .ts  → skipped (requires tsc, too heavy for a hook)
"""

import ast
import subprocess
import sys
import tempfile
from pathlib import Path

from utils import get_tool_input, hook_main, parse_stdin


def _validate_python(content: str) -> str | None:
    """Return error description or None if syntax is valid."""
    try:
        ast.parse(content)
        return None
    except SyntaxError as e:
        loc = f"line {e.lineno}" if e.lineno else "unknown line"
        return f"{loc}: {e.msg}"


def _validate_js(content: str) -> str | None:
    """Validate JS syntax via `node --check <tmpfile>` -- a PARSE-ONLY check.

    WHY not `node --input-type=module` + stdin (HIGH, cross-model audit): that
    approach actually EXECUTES the submitted code as a real module -- a
    top-level side-effecting statement (e.g. a malicious `require('child_
    process').execSync(...)`) would run on the user's machine merely by
    ATTEMPTING to write the file, even if the write itself is later blocked.
    `--check` parses without ever executing the module body. Writing to a
    real temp file (not stdin) is required because `--check` needs a file
    argument; the `.mjs` suffix preserves ESM parsing (the old --input-type=
    module forced ESM too). Fails silently if node is not installed
    (fail-open).
    """
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mjs", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        result = subprocess.run(
            ["node", "--check", tmp_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 and result.stderr:
            # WHY: node stderr has full path noise — strip to first error line
            first_error = result.stderr.strip().splitlines()[0]
            return first_error[:200]
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # WHY: node not available or too slow → fail-open, do not block write
        return None
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink()
            except OSError:
                pass


def _reconstruct_edit_result(
    file_path: str, old_string: str, new_string: str, replace_all: bool
) -> str | None:
    """Reconstruct the FULL file content after this Edit is applied, by
    reading its current on-disk content and performing the same old_string
    -> new_string replacement the Edit tool itself will do.

    WHY (HIGH, cross-model audit): validating `new_string` in isolation has
    two failure modes at once -- (1) a syntactically valid standalone
    fragment (e.g. a correctly-indented method body) can be falsely flagged,
    since it isn't valid top-level Python on its own; (2) a fragment that
    parses fine alone can still produce a syntax error once actually spliced
    into the surrounding file (e.g. an edit that closes a bracket the
    fragment itself never opened). Only checking the RECONSTRUCTED full file
    catches both correctly.

    Returns None if the file can't be read or old_string isn't found in it
    (Edit itself would fail for the same reason -- not this hook's job to
    catch) -- callers should fall back to fragment-only validation.
    """
    try:
        current = Path(file_path).read_text(encoding="utf-8")
    except OSError:
        return None
    if old_string not in current:
        return None
    count = -1 if replace_all else 1
    return current.replace(old_string, new_string, count)


def main() -> None:
    data = parse_stdin()
    tool_name: str = data.get("tool_name", "")

    if tool_name not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)

    tool_input = get_tool_input(data)
    file_path: str = tool_input.get("file_path", "")

    if tool_name == "Write":
        # WHY "content", not "new_content" (HIGH, cross-model audit / self-
        # discovered while fixing it): every other hook in this repo reads
        # Write's field as "content" (the real Write tool schema) -- this
        # hook read "new_content", a field that never appears in a real
        # Write event. Write syntax validation had silently never engaged in
        # production; the encoded test fixture used the same wrong field
        # name, so it "passed" while validating a fictional schema.
        content: str = tool_input.get("content", "")
    elif tool_name == "Edit":
        old_string = tool_input.get("old_string", "")
        new_string = tool_input.get("new_string", "")
        replace_all = bool(tool_input.get("replace_all", False))
        reconstructed = _reconstruct_edit_result(file_path, old_string, new_string, replace_all)
        content = reconstructed if reconstructed is not None else new_string
    else:  # MultiEdit — apply each {old_string, new_string} pair in sequence
        current = None
        try:
            current = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            pass
        edits = tool_input.get("edits", [])
        if current is not None:
            for edit in edits:
                old_string = edit.get("old_string", "")
                new_string = edit.get("new_string", "")
                if old_string not in current:
                    current = None
                    break
                count = -1 if edit.get("replace_all") else 1
                current = current.replace(old_string, new_string, count)
        if current is not None:
            content = current
        else:
            # WHY fall back to the last edit's new_string, not empty: can't
            # reconstruct the full file (new file or old_string mismatch),
            # but a fragment-level check is still better than skipping
            # validation entirely.
            content = edits[-1].get("new_string", "") if edits else ""

    if not content or not file_path:
        sys.exit(0)

    suffix = Path(file_path).suffix.lower()
    error: str | None = None

    if suffix == ".py":
        error = _validate_python(content)
    elif suffix in (".js", ".mjs", ".cjs"):
        error = _validate_js(content)
    # .ts/.tsx: skip — tsc is too heavy for inline hook

    if error:
        import json

        reason = (
            f"SyntaxError in {Path(file_path).name}: {error}. Fix the syntax error before writing."
        )
        print(json.dumps({"decision": "block", "reason": reason}))
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    hook_main(main)
