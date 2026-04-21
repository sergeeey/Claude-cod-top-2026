#!/usr/bin/env python3
"""SessionStart hook: detect first run and offer installation options.

WHY: New users who clone the repo and run `claude` without installing
get no guidance. This hook detects an unconfigured environment and
emits a friendly onboarding message with 3 install paths.
"""

import os
import sys
from pathlib import Path

from utils import emit_hook_result, hook_main, parse_stdin

CLAUDE_HOME = Path.home() / ".claude"
SENTINEL = CLAUDE_HOME / ".first_run_done"

# Signs the config is already installed
INSTALLED_MARKERS = [
    CLAUDE_HOME / "CLAUDE.md",
    CLAUDE_HOME / "hooks" / "utils.py",
    CLAUDE_HOME / "rules" / "integrity.md",
]


def _is_fresh_install() -> bool:
    """Return True if none of the installed markers exist."""
    return not any(m.exists() for m in INSTALLED_MARKERS)


def main() -> None:
    parse_stdin()

    # WHY: recursion guard — don't trigger inside subagent sessions
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    # Already seen this message before
    if SENTINEL.exists():
        sys.exit(0)

    if not _is_fresh_install():
        # Config is installed — write sentinel so hook exits fast next time
        try:
            SENTINEL.touch()
        except OSError:
            pass
        sys.exit(0)

    msg = """👋 Привет! Похоже, это первый запуск без конфига.

Этот репо содержит production-grade Claude Code конфиг:
  • 49 хуков (Evidence Policy, InputGuard, PII protection)
  • 39+ скилов (github-scout, research-scout, TDD, agent teams)
  • Persistent memory + wiki pipeline

─────────────────────────────────────────
🚀 Выбери способ установки:

[1] БЫСТРО — одна команда (Mac/Linux/WSL):
    git clone https://github.com/sergeeey/Claude-cod-top-2026.git \
    && cd Claude-cod-top-2026 && bash install.sh --profile=standard --non-interactive

[2] С СИМЛИНКАМИ — auto-update через git pull:
    git clone https://github.com/sergeeey/Claude-cod-top-2026.git \
    && cd Claude-cod-top-2026 && bash install.sh --link full

[3] ВЫБОРОЧНО — интерактивный выбор профиля:
    git clone https://github.com/sergeeey/Claude-cod-top-2026.git \
    && cd Claude-cod-top-2026 && bash install.sh

─────────────────────────────────────────
После установки перезапусти Claude (/clear или новая сессия).
Документация: https://github.com/sergeeey/Claude-cod-top-2026"""

    emit_hook_result("SessionStart", msg)


if __name__ == "__main__":
    hook_main(main)
