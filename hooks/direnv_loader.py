#!/usr/bin/env python3
"""CwdChanged hook: load directory-specific environment on cd.

WHY: Different project directories have different .env files.
Auto-loading prevents working with wrong credentials after cd.
"""

import os
from pathlib import Path

from utils import is_safe_path, parse_env_file_safe, parse_stdin


def main() -> None:
    data = parse_stdin()
    if not data:
        return

    new_cwd = data.get("cwd", data.get("new_cwd", ""))
    if not new_cwd:
        return

    # WHY: prevent path traversal — only load .env from within home directory
    cwd_path = Path(new_cwd)
    if not is_safe_path(cwd_path):
        return

    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if not env_file:
        return

    # WHY: look for .env in the new directory and load it safely
    for env_name in (".env", ".env.local"):
        env_path = cwd_path / env_name
        if env_path.exists():
            exports = parse_env_file_safe(env_path)
            if exports:
                try:
                    with open(env_file, "a", encoding="utf-8") as f:
                        f.write("\n".join(exports) + "\n")
                except OSError:
                    pass
            break  # WHY: first found .env wins, no cascading


if __name__ == "__main__":
    main()
