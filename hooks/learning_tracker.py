#!/usr/bin/env python3
"""PostToolUse(Bash) hook: learning tracker — yellow tips after each commit.

WHY: Every git commit is a learning moment. This hook detects what was
just committed, selects the next relevant Claude Code tip the user
hasn't seen yet, and prints it in bright yellow to the terminal.
Also logs to ~/.claude/memory/learning_log.md and injects a context
nudge into Claude via emit_hook_result().
"""

import sys
import textwrap
from datetime import datetime
from pathlib import Path

# WHY: run from hooks/ directory — add parent to path only if needed
sys.path.insert(0, str(Path(__file__).parent))

from learning_tips import LEARNING_LOG_PATH, select_tip
from utils import emit_hook_result, parse_stdin

# ── ANSI colours (bright yellow + reset) ─────────────────────────────────────
YELLOW = "\033[93m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# Box width (fits 80-column terminals)
BOX_W = 68

# ── Commit detection ──────────────────────────────────────────────────────────

_FAIL_SIGNALS = (
    "nothing to commit",
    "no changes added",
    "fatal:",
    "error:",
    "pre-commit hook",
    "aborting commit",
)


def _is_commit_command(command: str) -> bool:
    return "git commit" in command or "git merge" in command


def _is_failed(stdout: str, stderr: str, returncode: int) -> bool:
    if returncode != 0:
        return True
    combined = (stdout + stderr).lower()
    return any(sig in combined for sig in _FAIL_SIGNALS)


def detect_commit_context(data: dict) -> dict | None:
    """Return commit metadata dict or None if not a successful commit."""
    tool_input = data.get("tool_input", {}) or {}
    tool_response = data.get("tool_response", {}) or {}

    command = tool_input.get("command", "") or ""
    stdout = tool_response.get("stdout", "") or ""
    stderr = tool_response.get("stderr", "") or ""
    retcode = tool_response.get("returncode", tool_response.get("exit_code", 0)) or 0

    if not _is_commit_command(command):
        return None
    if _is_failed(stdout, stderr, int(retcode)):
        return None

    # Extract commit hash from stdout  e.g. "[main 9986fcf] feat: ..."
    commit_hash = ""
    commit_msg = ""
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("["):
            parts = line.split("]", 1)
            if len(parts) == 2:
                branch_hash = parts[0].lstrip("[").split()
                if len(branch_hash) >= 2:
                    commit_hash = branch_hash[-1]
                commit_msg = parts[1].strip()
                break

    # Count files changed
    files_changed = 0
    for line in stdout.splitlines():
        if "file" in line and "changed" in line:
            try:
                files_changed = int(line.strip().split()[0])
            except (ValueError, IndexError):
                pass
            break

    return {
        "hash": commit_hash or "unknown",
        "msg": commit_msg or command,
        "files_changed": files_changed,
    }


def classify_commit(commit_msg: str) -> str:
    """Return conventional commit type: feat/fix/refactor/test/chore/docs/other."""
    msg_lower = commit_msg.lower()
    for ctype in ("feat", "fix", "refactor", "test", "chore", "docs"):
        if msg_lower.startswith(ctype) or f" {ctype}:" in msg_lower:
            return ctype
    return "other"


# ── Yellow box renderer ───────────────────────────────────────────────────────


def _box_line(content: str = "", width: int = BOX_W) -> str:
    """Pad a content line to fit inside box borders."""
    inner = width - 4  # 2 for '│ ' + 2 for ' │'
    return f"│ {content:<{inner}} │"


def render_yellow_box(tip: dict) -> str:
    """Render a bright-yellow bordered box with the tip."""
    inner = BOX_W - 4
    lines: list[str] = []

    # Top border
    lines.append("┌" + "─" * (BOX_W - 2) + "┐")

    # Header
    header = f"💡 CLAUDE CODE TIP  [Level {tip['level']} · {tip['tag']}]"
    lines.append(_box_line(header))
    lines.append(_box_line("─" * (BOX_W - 6)))

    # Tip text (wrap each paragraph)
    for paragraph in tip["text"].split("\n"):
        for wrapped_line in textwrap.wrap(paragraph, inner) or [""]:
            lines.append(_box_line(wrapped_line))

    lines.append(_box_line())  # blank

    # Next try
    lines.append(_box_line("▶ Попробуй:"))
    for wrapped_line in textwrap.wrap(tip["next_try"], inner):
        lines.append(_box_line(f"  {wrapped_line}"))

    # Bottom border
    lines.append("└" + "─" * (BOX_W - 2) + "┘")

    body = "\n".join(lines)
    return f"{YELLOW}{BOLD}{body}{RESET}"


# ── Learning log ──────────────────────────────────────────────────────────────

_MACHINE_SECTION = "## Machine Log"
_TABLE_HEADER = (
    "| Date             | Commit  | Type     | Tip ID  | Files |\n"
    "|------------------|---------|----------|---------|-------|"
)


def _ensure_machine_section(log_path: Path) -> str:
    """Return current log content; create file/section if missing."""
    if not log_path.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
        initial = (
            "# Learning Log\n\n"
            "Твой прогресс в освоении Claude Code.\n\n"
            f"{_MACHINE_SECTION}\n"
            "<!-- Auto-written by learning_tracker.py. Do not edit manually. -->\n\n"
            f"{_TABLE_HEADER}\n"
        )
        log_path.write_text(initial, encoding="utf-8")
        return initial

    content = log_path.read_text(encoding="utf-8")
    if _MACHINE_SECTION not in content:
        content += (
            f"\n\n{_MACHINE_SECTION}\n"
            "<!-- Auto-written by learning_tracker.py. Do not edit manually. -->\n\n"
            f"{_TABLE_HEADER}\n"
        )
        log_path.write_text(content, encoding="utf-8")
    return content


def append_to_learning_log(
    commit_hash: str,
    commit_msg: str,
    commit_type: str,
    tip_id: str,
    files_changed: int,
) -> None:
    """Append one row to the Machine Log table."""
    try:
        content = _ensure_machine_section(LEARNING_LOG_PATH)
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        row = (
            f"| {now:<16} | {commit_hash:<7} | {commit_type:<8} "
            f"| {tip_id:<7} | {files_changed:<5} |"
        )
        log_path = LEARNING_LOG_PATH
        log_path.write_text(content.rstrip() + "\n" + row + "\n", encoding="utf-8")
    except OSError:
        pass  # WHY: never crash on log write failure


# ── Claude context ────────────────────────────────────────────────────────────


def build_claude_context(commit_hash: str, commit_msg: str, tip: dict) -> str:
    return (
        f"[learning-tracker] Коммит {commit_hash} обнаружен.\n\n"
        f"Коммит: {commit_msg}\n\n"
        f"ПОДСКАЗКА ДЛЯ ПОЛЬЗОВАТЕЛЯ [Level {tip['level']} · {tip['tag']}]:\n"
        f"{tip['text'].replace(chr(10), ' ')}\n\n"
        f"Следующий шаг: {tip['next_try']}\n"
        f"(Tip ID: {tip['id']} — записан в learning_log.md)"
    )


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    data = parse_stdin()
    if data is None:
        return

    ctx = detect_commit_context(data)
    if ctx is None:
        return

    commit_hash = ctx["hash"]
    commit_msg = ctx["msg"]
    files_changed = ctx["files_changed"]
    commit_type = classify_commit(commit_msg)

    # Read log to pick unseen tip
    log_content = ""
    try:
        if LEARNING_LOG_PATH.exists():
            log_content = LEARNING_LOG_PATH.read_text(encoding="utf-8")
    except OSError:
        pass

    tip = select_tip(log_content, commit_type)

    # ① Print yellow box to stderr — visible in terminal, ignored by Claude JSON parser
    try:
        print(render_yellow_box(tip), file=sys.stderr)
    except (UnicodeEncodeError, OSError):
        # Fallback for terminals without UTF-8 / box-drawing support
        print(f"{YELLOW}💡 CLAUDE CODE TIP [{tip['id']}]: {tip['text']}{RESET}", file=sys.stderr)

    # ② Persist to learning_log.md
    append_to_learning_log(commit_hash, commit_msg, commit_type, tip["id"], files_changed)

    # ③ Inject context into Claude
    emit_hook_result("PostToolUse", build_claude_context(commit_hash, commit_msg, tip))


if __name__ == "__main__":
    main()
