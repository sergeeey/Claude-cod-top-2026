"""
Configuration for NotebookLM Skill
Centralizes constants, selectors, and paths
"""

import os
from pathlib import Path

# Paths
SKILL_DIR = Path(__file__).parent.parent

# WHY: storing data/ inside SKILL_DIR is a leak surface — if a developer runs
# the skill from inside a git clone of this repo, then `git add -A` would stage
# Google auth cookies and browser state. Default to a per-user location
# (~/.claude/data/notebooklm/) that lives outside any repo tree.
# Overrides:
#   NOTEBOOKLM_DATA_DIR  — explicit path (highest priority)
#   CLAUDE_HOME          — base for ~/.claude resolution
# Back-compat: if legacy SKILL_DIR/data/ already exists from an earlier run,
# keep using it so existing notebooks don't lose their library.
_user_data_root = (
    Path(os.environ.get("CLAUDE_HOME", str(Path.home() / ".claude"))) / "data" / "notebooklm"
)
_legacy_data_dir = SKILL_DIR / "data"
DATA_DIR = Path(
    os.environ.get(
        "NOTEBOOKLM_DATA_DIR",
        str(_legacy_data_dir if _legacy_data_dir.exists() else _user_data_root),
    )
)

BROWSER_STATE_DIR = DATA_DIR / "browser_state"
BROWSER_PROFILE_DIR = BROWSER_STATE_DIR / "browser_profile"
STATE_FILE = BROWSER_STATE_DIR / "state.json"
AUTH_INFO_FILE = DATA_DIR / "auth_info.json"
LIBRARY_FILE = DATA_DIR / "library.json"

# NotebookLM Selectors
QUERY_INPUT_SELECTORS = [
    "textarea.query-box-input",  # Primary
    'textarea[aria-label="Feld für Anfragen"]',  # Fallback German
    'textarea[aria-label="Input for queries"]',  # Fallback English
]

RESPONSE_SELECTORS = [
    ".to-user-container .message-text-content",  # Primary
    "[data-message-author='bot']",
    "[data-message-author='assistant']",
]

# Browser Configuration
BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",  # Patches navigator.webdriver
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--no-first-run",
    "--no-default-browser-check",
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Timeouts
LOGIN_TIMEOUT_MINUTES = 10
QUERY_TIMEOUT_SECONDS = 120
PAGE_LOAD_TIMEOUT = 30000
