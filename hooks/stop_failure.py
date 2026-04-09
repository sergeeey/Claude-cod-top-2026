#!/usr/bin/env python3
"""StopFailure hook: handle API errors gracefully.

WHY: Rate limits and auth failures need specific recovery actions.
"""

import json
import sys
from pathlib import Path


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)
    error_type = str(data.get("error_type", ""))
    error_msg = str(data.get("error", ""))
    log_path = Path.home() / ".claude" / "logs" / "api_errors.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"type": error_type, "error": error_msg[:300]}) + "\n")
    except OSError:
        pass
    if "rate" in error_type.lower() or "429" in error_msg:
        print("[stop-failure] Rate limit hit. Wait 30-60s. Consider /effort low.", file=sys.stderr)
    elif "auth" in error_type.lower() or "401" in error_msg:
        print("[stop-failure] Auth error. Run: claude auth status", file=sys.stderr)
    else:
        print(f"[stop-failure] API error ({error_type}). Logged.", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
