#!/usr/bin/env python3
"""SessionStart hook: show the last Threads-center snapshot in at most four lines.

WHY: a note and a page only help if somebody opens them. This puts the one-line answer to "what is
overdue?" where you already are, at the start of every session.

It runs NO collectors (Task Scheduler, gh and git take 10+ seconds): it reads the small JSON that
`scripts/threads_center.py render` writes next to its HTML page
(`~/.claude/state/threads-center-last.json`).

Its second job is to notice a dead schedule. The failure the Threads center exists to catch is a
weekly job that stops without anyone noticing (four weekly tasks failed for weeks), so a snapshot
older than STALE_DAYS is reported as stale instead of being shown as if it were current.

  * no file            -> silent: the tool has never rendered, there is nothing to compare;
  * unreadable file    -> one line saying so: unknown is not "all clear";
  * fresh, all clear   -> one line;
  * overdue / unchecked / stale -> the headline, up to two overdue labels and a footer.

The context this hook writes is injected into the session, so it never copies free text from the
file: the headline is rebuilt from the numbers, labels lose control characters and are bounded
(the renderer already replaces a pull-request title, which a stranger can write, by "PR #N").

Fail-open: any error exits 0, SessionStart is never blocked.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from lib.runtime import emit_hook_result, parse_stdin

_LAST_FILE = Path.home() / ".claude" / "state" / "threads-center-last.json"
STALE_DAYS = 8  # a weekly render plus one day of grace
MAX_LABEL = 120
SHOWN_ROWS = 2
_CTRL = re.compile(r"[\x00-\x1f\x7f​-‏‪-‮⁦-⁩﻿]")
_HINT = "запустите `python scripts/threads_center.py render`"


def _line(text: object, limit: int = MAX_LABEL) -> str:
    t = re.sub(r"\s+", " ", _CTRL.sub(" ", str(text))).strip()
    return t if len(t) <= limit else t[: limit - 1] + "…"


def _num(value: object) -> int | None:
    """An int, or None when the file does not hold one (shown as '?', never as 0)."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _show(n: int | None) -> str:
    return "?" if n is None else str(n)


def _day(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def build_message(path: Path, today: date) -> str | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"[threads] файл снимка не читается ({type(exc).__name__}): {_HINT}"
    counts = data.get("counts") if isinstance(data, dict) else None
    snap_day = _day(data.get("today")) if isinstance(data, dict) else None
    if not isinstance(counts, dict) or snap_day is None:
        return f"[threads] файл снимка неожиданного формата: {_HINT}"

    overdue, opened, waiting = (_num(counts.get(k)) for k in ("overdue", "open", "waiting"))
    unchecked, partial = _num(data.get("unchecked")), _num(data.get("partial"))
    head = f"ПРОСРОЧЕНО {_show(overdue)} · ОТКРЫТО {_show(opened)} · ЖДУТ СОБЫТИЙ {_show(waiting)}"
    if unchecked != 0:
        head += f" · НЕ ПРОВЕРЕНО источников: {_show(unchecked)}"
    if partial != 0:
        head += f" · ЧАСТИЧНО: {_show(partial)}"
    if data.get("status") != "OK":
        head += " · СТАТУС СНИМКА НЕ OK"

    age = max(0, (today - snap_day).days)
    stale = age > STALE_DAYS
    clean = overdue == 0 and unchecked == 0 and partial == 0 and data.get("status") == "OK"
    if stale:
        lines = [
            f"[threads] СНИМОК УСТАРЕЛ: {age} дн. назад, недельный запуск не отработал? "
            f"Тогда было: {head}"
        ]
    else:
        lines = [f"[threads] {head}"]
    if clean and not stale:
        return lines[0]

    top = data.get("top_overdue")
    for row in (top if isinstance(top, list) else [])[:SHOWN_ROWS]:
        if isinstance(row, dict) and row.get("label"):
            lines.append(f"  • {_line(row['label'])}")
    more = (overdue - SHOWN_ROWS) if overdue is not None and overdue > SHOWN_ROWS else 0
    when = "сегодня" if age == 0 else f"{age} дн. назад"
    lines.append(f"  {f'… ещё {more}; ' if more else ''}снимок: {when} ({snap_day})")
    return "\n".join(lines)


def main() -> None:
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)
    parse_stdin()
    today = datetime.now(UTC).astimezone().date()
    message = build_message(_LAST_FILE, today)
    if message:
        emit_hook_result("SessionStart", message)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[threads-center-session] fatal: {e}", file=sys.stderr)
        sys.exit(0)
