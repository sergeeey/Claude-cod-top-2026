#!/usr/bin/env python3
"""Generate hooks/hooks.json (the plugin-format hook manifest) from
hooks/settings.json (the classic-installer format) -- filesystem-authoritative,
never hand-edited.

WHY this exists (P0-C, external audit 2026-07-24): the plugin manifest schema
requires hooks at `hooks/hooks.json` (bare `{"hooks": {...}}`), a different
shape from `hooks/settings.json` (a full Claude Code settings file with
permissions/hooks/spinnerTips/etc, and `__PYTHON_CMD__`/`__CLAUDE_HOME__`
placeholders substituted by install.sh at install time -- placeholders that
mean nothing to a plugin install, which has no install.sh step). Before this,
`/plugin install` almost certainly didn't wire any of the 95 hooks at all
(main audit finding, packaging scored 2.5/10) -- confirmed live this session
via `claude plugin marketplace add` + `claude plugin install`: the generated
hooks.json copies into the plugin cache and 128 skills alongside it.

WHY a generator, not a hand-maintained second file: hooks/settings.json and
hooks/hooks.json would otherwise be two independent sources of truth for the
same 95 hooks across 24 events -- exactly the class of drift this repo's own
sync_doc_counts.py exists to prevent for hook/agent/skill COUNTS. This script
applies the same discipline to hook CONTENT: hooks.json is always regenerated
from settings.json, never edited by hand.

Placeholder substitution:
  __PYTHON_CMD__  -> "python3" (a plugin has no install-time interpreter
                      resolution step; python3 is the portable default)
  __CLAUDE_HOME__ -> "${CLAUDE_PLUGIN_ROOT}" (Claude Code's native plugin-root
                      substitution, resolved at hook-invocation time)

Usage:
    python scripts/sync_plugin_hooks.py            # regenerate hooks/hooks.json
    python scripts/sync_plugin_hooks.py --check     # report drift, write nothing (exit 1 if drift)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
SETTINGS = REPO / "hooks" / "settings.json"
OUT = REPO / "hooks" / "hooks.json"


def _substitute(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _substitute(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute(v) for v in obj]
    if isinstance(obj, str):
        return obj.replace("__PYTHON_CMD__", "python3").replace(
            "__CLAUDE_HOME__", '"${CLAUDE_PLUGIN_ROOT}"'
        )
    return obj


def generate() -> str:
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    transformed = _substitute(data["hooks"])
    # WHY newline="\n" explicit, not write_text default (same lesson as
    # sync_doc_counts.py, 2026-07-19 CRLF incident): keep LF endings on Windows.
    return json.dumps({"hooks": transformed}, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    check_only = "--check" in sys.argv
    generated = generate()

    # WHY Path.open(...).read() instead of Path.read_text(newline=""): the
    # `newline` kwarg on read_text() only exists since Python 3.13 -- this
    # repo's CI matrix runs 3.11/3.12, where passing it raises TypeError at
    # runtime (same fix already applied in sync_doc_counts.py, 2026-07-19).
    if OUT.exists():
        with OUT.open(encoding="utf-8", newline="") as f:
            current = f.read()
    else:
        current = None

    if current == generated:
        print("[sync-plugin-hooks] hooks/hooks.json already matches settings.json — nothing to do.")
        return 0

    if check_only:
        print("[sync-plugin-hooks] DRIFT: hooks/hooks.json does not match settings.json.")
        print("[sync-plugin-hooks] Run: python scripts/sync_plugin_hooks.py")
        return 1

    OUT.write_text(generated, encoding="utf-8", newline="")
    print(f"[sync-plugin-hooks] regenerated {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
