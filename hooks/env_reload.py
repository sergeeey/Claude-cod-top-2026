#!/usr/bin/env python3
"""FileChanged hook: reload environment when .env/.envrc changes.

WHY: Environment variables in .env change during development (DB URLs, API keys).
Auto-reloading prevents stale env causing mysterious failures.
"""

import os
from pathlib import Path

from utils import is_safe_path, parse_env_file_safe, parse_stdin


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    file_path = data.get("file_path", "")
    if not file_path:
        return

    env_path = Path(file_path)
    basename = env_path.name.lower()
    # WHY: only react to env-related files, not every file change
    if basename not in (".env", ".envrc", ".env.local", ".env.development"):
        return

    # WHY: prevent path traversal — only load .env from within home directory
    if not is_safe_path(env_path):
        return

    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if not env_file:
        return

    if not env_path.exists():
        return

    # WHY: use safe parser that validates KEY=VALUE and quotes values
    exports = parse_env_file_safe(env_path)
    if exports:
        try:
            with open(env_file, "a", encoding="utf-8") as f:
                f.write("\n".join(exports) + "\n")
        except OSError:
            pass


if __name__ == "__main__":
    main()
