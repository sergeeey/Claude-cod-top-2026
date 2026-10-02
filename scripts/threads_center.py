#!/usr/bin/env python3
"""Threads center: what is OVERDUE, OPEN or WAITING for an event, and how stale the notes are.

WHY: reminders, audits and "come back when conditions change" notes were scattered over a pearl
registry, per-experiment ledgers, parked/ rows, scheduled tasks, open PRs and Obsidian hubs, with no
single place to look. Measured 2026-10-02 before this script existed: four weekly Claude tasks
fail every run (Task Scheduler result 1, `claude -p` -> `401 API key is invalid`) and nobody
sees it;
14 automated PRs sit open; 5 pearl next_check dates are past, two of them "lapsed, not re-checked"
since 2026-08-04; 169 of 218 `active` vault notes are untouched for >60 days.

DESIGN (from this repo's own measured lessons):
  * Derive, don't ask. Almost everything is read from real artifacts, so the page is full on day 1.
    The only manual layer is a small thread store (`add` / `close`).
  * Deterministic Python, never `claude -p` (that is exactly what is failing with 401).
  * Unknown is not zero: a collector that cannot run is listed as NOT CHECKED, never dropped.
  * Third-party text (PR titles, log lines) is DATA: escaped in HTML and Markdown, secrets masked.
  * Existing vault notes are never rewritten. This script writes only its own two outputs and the
    thread store file. Drift in other notes is REPORTED with the exact claim and the measured value.

Usage:
    python scripts/threads_center.py render                 # collect + write the note and the page
    python scripts/threads_center.py render --dry-run       # collect + print the summary only
    python scripts/threads_center.py summary [--alert]      # 3 lines; --alert exits 1 if overdue
    python scripts/threads_center.py collect --json         # the raw snapshot
    python scripts/threads_center.py add "text" --trigger "date:2026-11-01" --next "what to do"
    python scripts/threads_center.py close T-20261002-01 [--status done|dropped]
    python scripts/threads_center.py list
    python scripts/threads_center.py install-hint           # prints (does NOT run) the schedule

THRESHOLDS are provisional heuristics, chosen for recall, not calibrated: HUB_STALE_DAYS,
PR_STALE_DAYS, DIRTY_WORKTREE_DAYS. Change them here, not in the output.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import html
import importlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

# --- provisional thresholds (heuristics, not calibrated) -----------------------------------------
HUB_STALE_DAYS = 30  # a status/index hub untouched this long is flagged
HEADER_GAP_DAYS = 14  # file touched, but its own "updated" header is older than this
PR_STALE_DAYS = 14  # a human PR open longer than this is overdue
DIRTY_WORKTREE_DAYS = 7  # reserved: unsaved edits are always listed as open; kept for tuning
MAX_CELL = 200
LIST_CAP = 25

OK_TASK_CODES = {0, 267009}  # success, currently running
NEVER_RAN_CODE = 267011  # 0x41303 has not run yet
KNOWN_TASK_CODES = {
    1: "код 1: скрипт завершился ошибкой",
    3221225786: "0xC000013A: прервано (закрыто/Ctrl+C)",
    2147946720: "0x800710E0: оператор/условия задачи отклонили запуск",
}
DEFAULT_TASK_PATTERN = r"^(Claude|Codex)"
VAULT_HUBS = (
    "09 System/Truth/project-status-registry.md",
    "09 System/Truth/github-repos-registry.md",
    "09 System/Truth/system-manifest.md",
    "Dashboard.md",
    "Research Dashboard.md",
    "activeContext.md",
    "_auto/activeContext.md",
    "MEMORY.md",
    "indices/projects.md",
    "pipeline/_dashboard.md",
)
VAULT_HUB_GLOBS = ("mocs/*.md",)
THREADS_NOTE_REL = "09 System/Центр нитей.md"
THREADS_STORE_REL = "09 System/Нити (реестр).md"
ARCHIVE_DIR_REL = "09 System/Центр нитей (архив)"  # one note per ISO week, linked both ways
# ~/.claude/state/<prefix>-<scope>.json: first/last time each row was listed, one per source set
SEEN_FILE_PREFIX = "threads-center-seen"
SEEN_KEEP_DAYS = 120  # a row gone for longer than this is forgotten
STATS_MIN_DAYS = 28  # rows younger than this are not judged yet
STATS_MIN_RENDERS = 4  # fewer distinct render days than this: no verdict
STATS_KEEP_SHARE = 1 / 3  # kill criterion: fewer rows resolved than this -> remove the tool
KIND_COLLECTOR: dict[
    str, tuple[str, ...]
] = {  # a row is judged only if ALL its collectors ran cleanly
    "automation": ("automations",),
    "pearl": ("pearls",),
    "pr": ("prs",),
    "git": ("git",),
    "experiment": ("experiments",),
    "ledger": ("waiting",),
    "parked": ("waiting",),
    "thread": ("threads",),
    "vault": ("vault",),
    "vault_claim": ("vault", "prs"),  # needs gh's PR count too: unknown when gh is down
}
KIND_LEGEND = {
    "automation": "Задача Планировщика Windows: последний результат не «успех» или есть пропущенные запуски. Причина берётся из журнала задачи, если он найден.",  # noqa: E501
    "pearl": "Строка pearl-реестра («проверить позже»): next_check уже прошёл (просрочено) или срок задан событием, а не датой (ждёт).",  # noqa: E501
    "pr": "Открытый Pull Request: красный CI или старше 14 дней. Автоматические PR свёрнуты в одну строку.",  # noqa: E501
    "git": "Рабочее дерево с несохранёнными правками или ветка, чей PR закрыт без мержа: работа может потеряться.",  # noqa: E501
    "experiment": "Папка experiments/ без вердикта и без изменений долгое время («зомби»).",
    "ledger": "Запись ledger.md эксперимента «проверить после…»: ждёт события, не даты.",
    "parked": "Строка parked/INDEX.md: идея отложена до выполнения условия.",
    "thread": "Нить, внесённая вручную командой add в реестр нитей.",
    "vault": "Хаб Obsidian: давно не менялся, своя дата старше файла, или утверждение (число файлов, число PR) расходится с реальностью.",  # noqa: E501
}
CLOSED_WORDS = (
    "reject",
    "done",
    "archive",
    "fixed",
    "closed",
    "implemented",
    "resolved",
    "promoted",
    "withdrawn",
)
KIND_LEGEND["vault_claim"] = (
    "Хаб Obsidian утверждает число (открытых PR), которое расходится с реальным."
)
SECTIONS = ("overdue", "open", "waiting")
SECTION_TITLES = {
    "overdue": "ПРОСРОЧЕНО",
    "open": "ОТКРЫТЫЕ НИТИ",
    "waiting": "ЖДУТ СОБЫТИЯ",
}
KIND_ORDER = {
    "automation": 0,
    "pearl": 1,
    "pr": 2,
    "experiment": 3,
    "vault": 4,
    "vault_claim": 4,
    "git": 5,
    "thread": 6,
    "ledger": 7,
    "parked": 8,
}

Runner = Callable[[list[str], int], tuple[int, str]]


# --- data model ---------------------------------------------------------------------------------
@dataclass(frozen=True)
class Item:
    section: str  # overdue | open | waiting
    kind: str  # automation | pearl | pr | experiment | vault | git | thread | ledger | parked
    title: str
    detail: str = ""
    age_days: int | None = None
    source: str = "auto"  # auto | thread-store
    ref: str = ""  # url / path / id


@dataclass
class Context:
    today: date
    repo: Path | None
    vault: Path
    pearl_registries: list[Path]
    threads_file: Path
    log_dir: Path
    task_pattern: str = DEFAULT_TASK_PATTERN
    runner: Runner | None = None
    is_windows: bool = field(default_factory=lambda: sys.platform == "win32")
    cache: dict[str, Any] = field(default_factory=dict)
    seen_file: Path | None = None
    scope: str | None = None  # identity of the inspected sources (repo, vault, registries)

    def run(self, cmd: list[str], timeout: int = 60) -> tuple[int, str]:
        return (self.runner or default_runner)(cmd, timeout)


class CollectorUnavailable(Exception):
    """A source that cannot be read here (not an error in the data: 'unknown', never 'zero')."""


def default_runner(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace"
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return p.returncode, p.stdout


# --- text safety --------------------------------------------------------------------------------
_SECRET_RES = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)bearer\s*:?\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+@"),  # user:password@host in a URL
    re.compile(r"(?i)\b[A-Z0-9_]*(?:API_?KEY|SECRET|TOKEN|PASSWORD)\b\s*[=:]\s*\S{6,}"),
    re.compile(r'(?i)"(?:password|passwd|secret|token|api_?key)"\s*:\s*"[^"]{4,}"'),
)
# control chars plus zero-width and bidi overrides (they can reorder or hide visible text)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")


def mask_secrets(text: str) -> str:
    for rx in _SECRET_RES:
        text = rx.sub("<masked>", text)
    return text


def clean(text: str, limit: int = MAX_CELL) -> str:
    """Third-party text -> one safe line (control chars out FIRST, then secrets masked, bounded).

    Order matters: a key split by a control char must be rejoined before it is masked.
    """
    text = mask_secrets(_CTRL.sub("", str(text)))
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def md_cell(text: str) -> str:
    """Markdown table cell for foreign text.

    Backslash is doubled BEFORE the pipe is escaped; otherwise text that already ends a cell with a
    backslash-pipe pair gets an even run of backslashes and the pipe turns back into a column
    separator. Square brackets are escaped: Markdown links, IMAGES (`![x](https://…)`, fetched
    when the note is opened), reference links and `[[wikilinks]]` all need them, and a PR title is
    written by whoever opens the PR. `%%` (Obsidian comment: an unpaired one hides the rest of the
    note) and `<` (raw HTML, autolinks) are neutralised too.
    """
    out = clean(text).replace("\\", "\\\\").replace("|", "\\|")
    out = out.replace("[", "\\[").replace("]", "\\]")
    return out.replace("%%", "% %").replace("<", "&lt;")


# --- helpers ------------------------------------------------------------------------------------
_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def parse_date(text: str) -> date | None:
    m = _ISO_DATE.search(text or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def days_between(today: date, then: date | None) -> int | None:
    return None if then is None else (today - then).days


def _split_raw(line: str) -> list[str] | None:
    """Split a markdown table row on UNESCAPED pipes (even run of backslashes before the pipe)."""
    s = line.strip()
    if "|" not in s:
        return None
    cells: list[str] = []
    buf: list[str] = []
    run = 0
    for ch in s:
        if ch == "\\":
            run += 1
            buf.append(ch)
        elif ch == "|" and run % 2 == 0:
            cells.append("".join(buf))
            buf, run = [], 0
        else:
            run = 0
            buf.append(ch)
    cells.append("".join(buf))
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.strip() for c in cells]


def split_row(line: str) -> list[str] | None:
    raw = _split_raw(line)
    return None if raw is None else [c.replace("\\|", "|") for c in raw]


def _local_date(ts: float) -> date:
    lt = time.localtime(ts)
    return date(lt.tm_year, lt.tm_mon, lt.tm_mday)


def _warn(ctx: Context, msg: str) -> None:
    """A collector worked but could not check part of its source: reported, never silent."""
    seen = ctx.cache.setdefault("warnings", [])
    text = clean(msg, 200)
    if text not in seen:
        seen.append(text)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


# --- collector: scheduled tasks (Windows) -------------------------------------------------------
_PS_TASKS = (
    "Get-ScheduledTask | Where-Object { $_.TaskName -match '%s' } | ForEach-Object { "
    "$i = $_ | Get-ScheduledTaskInfo; [pscustomobject]@{ Task=$_.TaskName; State=[string]$_.State; "
    "Last=$(if ($i.LastRunTime) { $i.LastRunTime.ToString('o') } else { '' }); "
    "Result=[int64]$i.LastTaskResult; "
    "Next=$(if ($i.NextRunTime) { $i.NextRunTime.ToString('o') } else { '' }); "
    "Missed=[int]$i.NumberOfMissedRuns } } "
    "| ConvertTo-Json -Compress"
)
_FAIL_SIGNATURES = (
    re.compile(r"(?i)api key is invalid"),
    re.compile(r"(?i)failed to authenticate"),
    re.compile(r"(?i)\b40[13]\b"),
    re.compile(r"FAILED"),
)


def _task_keywords(task: str) -> list[str]:
    words = re.findall(r"[A-Z][a-z]+|[a-z]+", task)
    skip = {
        "claude",
        "codex",
        "weekly",
        "monday",
        "saturday",
        "sunday",
        "daily",
        "biweekly",
        "d",
        "research",
        "audit",
    }
    return [w.lower() for w in words if w.lower() not in skip and len(w) > 2]


def log_hint(task: str, log_dir: Path) -> str:
    """The most telling failure line from the newest log that belongs to this task, or ''."""
    keys = _task_keywords(task)
    if not keys or not log_dir.is_dir():
        return ""
    try:
        logs = [p for p in log_dir.glob("*.log") if any(k in p.name.lower() for k in keys)]
        logs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        if not logs:
            return ""
        lines = logs[0].read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
    except OSError:
        return ""
    for sig in _FAIL_SIGNATURES:
        for line in reversed(lines):
            if sig.search(line):
                return clean(f"{logs[0].name}: {line}", 160)
    return ""


def collect_automations(ctx: Context) -> list[Item]:
    if not ctx.is_windows:
        raise CollectorUnavailable("планировщик задач Windows недоступен на этой ОС")
    rc, out = ctx.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            _PS_TASKS % ctx.task_pattern.replace("'", "''"),
        ],
        90,
    )
    if rc != 0 or not out.strip():
        raise CollectorUnavailable(f"Get-ScheduledTask не вернул данные (код {rc})")
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise CollectorUnavailable(f"не разобрать вывод планировщика: {exc}") from exc
    rows = data if isinstance(data, list) else [data]
    items: list[Item] = []
    for r in rows:
        name = str(r.get("Task", "?"))
        code = int(r.get("Result", 0))
        last = parse_date(str(r.get("Last", "")))
        age = days_between(ctx.today, last) if last and last.year > 2000 else None
        missed = int(r.get("Missed", 0) or 0)
        if str(r.get("State", "")).lower() == "disabled" and code in OK_TASK_CODES:
            items.append(
                Item(
                    "open",
                    "automation",
                    f"задача {name} отключена",
                    f"последний запуск {last or '?'}; отключённая задача молчит, а не падает",
                    age,
                    ref=name,
                )
            )
            continue
        if code in OK_TASK_CODES and missed == 0:
            continue
        if code == NEVER_RAN_CODE:
            items.append(
                Item("open", "automation", f"задача {name} ещё ни разу не запускалась", "", age)
            )
            continue
        meaning = KNOWN_TASK_CODES.get(code, f"код {code} (0x{code & 0xFFFFFFFF:08X})")
        cause = log_hint(name, ctx.log_dir)
        detail = f"{meaning}; последний запуск {last or '?'}"
        if missed:
            detail += f"; пропущено запусков: {missed}"
        if cause:
            detail += f"; причина из журнала: {cause}"
        items.append(Item("overdue", "automation", f"задача {name} падает", detail, age, ref=name))
    return items


# --- collector: pearl registries ----------------------------------------------------------------
def _health_loop() -> Any:
    hooks = str(_repo_root() / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    prev = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # a read-only report must not create hooks/__pycache__
    try:
        return importlib.import_module("research_health_loop")
    finally:
        sys.dont_write_bytecode = prev


# A status counts as closed only by its LEADING word. Substring matching closed rows like
# "pending [REJECTED-AS-DESIGNED ...]" or "... not fixed yet" and hid them from the page.
_CLOSED_LEAD = frozenset(
    {
        "fixed",
        "closed",
        "done",
        "killed",
        "archived",
        "superseded",
        "dropped",
        "merged",
        "implemented",
        "resolved",
        "applied",
        "rejected",
        "withdrawn",
        "promoted",
        "закрыт",
        "закрыто",
        "выполнено",
        "готово",
        "confirmed",  # resolves a row; "partially confirmed" leads with "partially", stays open
    }
)
_LEAD_DATE = re.compile(r"^[\W_]*(\d{4})-(\d{2})-(\d{2})")
_STATUS_TAG = re.compile(r"\[([A-Z][A-Z0-9_-]{3,})\b")


_STATUS_LEAD = re.compile(r"[\s*_`\[(\"']*([^\W\d_]+)(?![\w-])(?!\?)")


def _status_closed(status: str) -> bool:
    """Closed iff the status STARTS with a whole closing word. A strikethrough (`~~FIXED~~`), a
    compound (`done-ish`, `closed-loop`) or a question (`merged? no`) is not a closing word."""
    m = _STATUS_LEAD.match(status)
    return m is not None and m.group(1).lower() in _CLOSED_LEAD


def _leading_date(cell: str) -> tuple[date | None, bool]:
    """(date, malformed). Only a date at the START of the cell is a deadline."""
    m = _LEAD_DATE.match(cell)
    if not m:
        return None, False
    try:
        return date(int(m[1]), int(m[2]), int(m[3])), False
    except ValueError:
        return None, True


_DATE_CELL = re.compile(r"[\s*_`]*\d{4}-\d{2}-\d{2}\b")


def _parse_pearls(reg: Path) -> tuple[list[dict[str, str]], list[tuple[str, int, int, str]]]:
    """Rows by COLUMN NAME, plus each untrustworthy row as (label, cells, expected, reason).

    A row with a different cell count (an unescaped `|` in its text) or without a date in its first
    column is never read positionally and never skipped silently. Header names are normalised
    ("Next Check" and `next_check` are one column); a header that is not recognised raises
    ValueError when data rows exist, instead of reporting "0 rows".
    """
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    bad: list[tuple[str, int, int, str]] = []
    data_lines = 0
    for line in reg.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        if re.match(r"\|\s*\d{4}-\d{2}-\d{2}", line.lstrip()):
            data_lines += 1
        cells = split_row(line)
        if not cells:
            continue
        if header is None:
            low = [re.sub(r"\s+", "_", c.lower()) for c in cells]
            if "next_check" in low and "status" in low:
                header = low
            continue
        if all(re.fullmatch(r"[-: ]*", c) for c in cells):
            continue
        label = clean(cells[1] if len(cells) > 1 else cells[0], 70)
        if not _DATE_CELL.match(cells[0]):
            bad.append(
                (
                    label,
                    len(cells),
                    len(header),
                    "в первой колонке нет даты (разметка или иной формат)",
                )
            )
            continue
        if len(cells) != len(header):
            reason = (
                f"{len(cells)} ячеек вместо {len(header)} (вероятно неэкранированный | в тексте)"
            )
            bad.append((label, len(cells), len(header), reason))
            continue
        rows.append(dict(zip(header, cells, strict=True)))
    if header is None and data_lines:
        raise ValueError(
            f"заголовок с колонками next_check/status не найден, строк данных: {data_lines}"
        )
    return rows, bad


def collect_pearls(ctx: Context) -> list[Item]:
    existing = [p for p in ctx.pearl_registries if p.is_file()]
    if not existing:
        raise CollectorUnavailable("нет ни одного pearl-реестра по заданным путям")
    for missing in (p for p in ctx.pearl_registries if not p.is_file()):
        _warn(ctx, f"pearl-реестр не найден: {missing}")
    items: list[Item] = []
    unreadable = 0
    for reg in existing:
        ref = f"{reg.parent.parent.name}/{reg.parent.name}"
        try:
            rows, bad = _parse_pearls(reg)
        except ValueError as exc:
            unreadable += 1
            _warn(ctx, f"pearl-реестр {ref}: {exc}")
            continue
        for label, _got, _want, reason in bad:
            items.append(
                Item(
                    "open",
                    "pearl",
                    f"строка pearl-реестра разобрана ненадёжно: {label}",
                    f"{reason}: срок и статус неизвестны. Исправить строку в реестре",
                    ref=ref,
                )
            )
        for e in rows:
            status = e.get("status", "")
            if _status_closed(status):
                continue
            label = clean(e.get("observation") or e.get("source") or "pearl", 110)
            nc = e.get("next_check", "").strip()
            due, malformed = _leading_date(nc)
            tag = _STATUS_TAG.search(status)
            tag_note = f"; метка статуса: {tag.group(1)}" if tag else ""
            if malformed:
                items.append(
                    Item(
                        "open",
                        "pearl",
                        label,
                        f"срок не разобран: {clean(nc, 40)}{tag_note}",
                        ref=ref,
                    )
                )
            elif due is not None and due <= ctx.today:
                lapsed = "lapsed" in status.lower()
                detail = f"next_check {due}" + (
                    "; отмечено «lapsed, not re-checked»" if lapsed else ""
                )
                items.append(
                    Item(
                        "overdue",
                        "pearl",
                        label,
                        detail + tag_note,
                        days_between(ctx.today, due),
                        ref=ref,
                    )
                )
            elif due is None:
                items.append(
                    Item(
                        "waiting",
                        "pearl",
                        label,
                        f"триггер без даты: {clean(nc, 90) or '—'}{tag_note}",
                        ref=ref,
                    )
                )
    if unreadable == len(existing):
        raise CollectorUnavailable(
            "ни один pearl-реестр не разобрался (нет заголовка next_check/status)"
        )
    return items


# --- collector: pull requests (gh) ---------------------------------------------------------------
_REMOTE_RE = re.compile(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?/?$")


def _repo_slug(ctx: Context) -> str | None:
    """owner/name of the inspected repo: gh must not answer for the process's current folder."""
    if "repo_slug" not in ctx.cache:
        slug = None
        if ctx.repo is not None:
            rc, out = _git(ctx, ctx.repo, "remote", "get-url", "origin")
            m = _REMOTE_RE.search(out.strip()) if rc == 0 else None
            slug = m.group(1) if m else None
        ctx.cache["repo_slug"] = slug
    found: str | None = ctx.cache["repo_slug"]
    if found is None:  # every collector that calls gh gets its own warning
        _warn(ctx, "gh вызван без -R: репозиторий определяется по текущей папке процесса")
    return found


def _gh(ctx: Context, *args: str, timeout: int = 90) -> tuple[int, str]:
    slug = _repo_slug(ctx)
    return ctx.run(["gh", *args, *(["-R", slug] if slug else [])], timeout)


_AUTOMATED_TITLE = re.compile(r"^\s*chore:\s*focusos\b", re.I)


def _is_automated(pr: dict[str, Any]) -> bool:
    """Machine-made PR, matched by origin: a `focusos/` branch, an `[automated]` tag, or the exact
    `chore: FocusOS ...` title prefix. NOT the bare word: "fix: focusos hook bug" is human work."""
    title = str(pr.get("title", ""))
    head = str(pr.get("headRefName", "")).lower()
    return (
        "[automated]" in title.lower()
        or head.startswith("focusos/")
        or _AUTOMATED_TITLE.match(title) is not None
    )


_CI_RED = {"FAILURE", "TIMED_OUT", "CANCELLED", "ERROR", "STARTUP_FAILURE", "ACTION_REQUIRED"}


def _ci_state(pr: dict[str, Any]) -> str:
    rollup = pr.get("statusCheckRollup") or []
    concl: set[str] = set()
    for c in rollup:
        v = str(c.get("conclusion") or c.get("state") or "").upper()
        status = str(c.get("status") or "").upper()
        if not v and status and status != "COMPLETED":
            v = status  # IN_PROGRESS / QUEUED: not green yet
        concl.add(v)
    if concl & _CI_RED:
        return "red"
    if rollup and concl <= {"SUCCESS", "SKIPPED", "NEUTRAL"}:
        return "green"
    return "unknown"


def collect_prs(ctx: Context) -> list[Item]:
    if ctx.repo is None:
        raise CollectorUnavailable("репозиторий не задан")
    rc, out = _gh(
        ctx,
        "pr",
        "list",
        "--state",
        "open",
        "--limit",
        "100",
        "--json",
        "number,title,createdAt,headRefName,url,statusCheckRollup,isDraft",
    )
    if rc != 0:
        raise CollectorUnavailable(f"gh pr list не вернул данные (код {rc})")
    try:
        prs = json.loads(out)
    except json.JSONDecodeError as exc:
        raise CollectorUnavailable(f"не разобрать вывод gh: {exc}") from exc
    ctx.cache["open_pr_count"] = len(prs)
    if len(prs) >= 100:
        _warn(ctx, "открытых PR не меньше 100: список усечён")
    items: list[Item] = []
    automated = [p for p in prs if _is_automated(p)]
    for p in prs:
        if _is_automated(p):
            continue
        age = days_between(ctx.today, parse_date(str(p.get("createdAt", ""))))
        title = f"PR #{p.get('number')}: {clean(p.get('title', ''), 90)}"
        ci = _ci_state(p)
        if ci == "red":
            items.append(Item("overdue", "pr", title, "CI красный", age, ref=str(p.get("url", ""))))
        elif age is not None and age > PR_STALE_DAYS:
            items.append(
                Item(
                    "overdue",
                    "pr",
                    title,
                    f"открыт {age} дн. (порог {PR_STALE_DAYS})",
                    age,
                    ref=str(p.get("url", "")),
                )
            )
        else:
            items.append(Item("open", "pr", title, f"CI: {ci}", age, ref=str(p.get("url", ""))))
    if automated:
        ages = [
            a
            for a in (
                days_between(ctx.today, parse_date(str(p.get("createdAt", "")))) for p in automated
            )
            if a is not None
        ]
        oldest = max(ages) if ages else None
        items.append(
            Item(
                "overdue",
                "pr",
                f"{len(automated)} автоматических PR (FocusOS и т.п.) не рассмотрены",
                "ни один не смержен и не закрыт; каждый добавляет файл в .claude/memory/raw",
                oldest,
            )
        )
    return items


# --- collector: git worktrees / branches ---------------------------------------------------------
_JUNK_PREFIXES = ("tests/eval/results/", "tmp/")
_NO_PR_BRANCHES = frozenset({"main", "master", "detached HEAD"})  # never asked about on GitHub


def _git(ctx: Context, repo: Path, *args: str) -> tuple[int, str]:
    # --no-optional-locks: a background reader must not take index.lock, or it can make a concurrent
    # `git add`/`git commit` in another session fail with "index.lock exists".
    return ctx.run(["git", "--no-optional-locks", "-C", str(repo), *args], 60)


def collect_git(ctx: Context) -> list[Item]:
    if ctx.repo is None or not ctx.repo.is_dir():
        raise CollectorUnavailable("репозиторий не задан или не найден")
    rc, out = _git(ctx, ctx.repo, "worktree", "list", "--porcelain")
    if rc != 0:
        raise CollectorUnavailable(f"git worktree list не сработал (код {rc})")
    trees: list[tuple[Path, str]] = []
    path: Path | None = None
    for line in out.splitlines():
        if line.startswith("worktree "):
            path = Path(line[len("worktree ") :].strip())
        elif line.startswith("branch ") and path is not None:
            trees.append((path, line[len("branch ") :].strip().removeprefix("refs/heads/")))
            path = None
        elif line.strip() == "detached" and path is not None:
            trees.append((path, "detached HEAD"))  # the place where work gets lost most often
            path = None
    # One query PER BRANCH, not one repo-wide `--limit 200`: a long-lived repo has far more
    # historical PRs than that, and an old worktree branch would silently fall out of the window.
    closed_unmerged: set[str] = set()
    for branch in sorted({b for _, b in trees if b not in _NO_PR_BRANCHES}):
        rc2, out2 = _gh(
            ctx, "pr", "list", "--state", "all", "--head", branch, "--limit", "10",
            "--json", "headRefName,state",
        )  # fmt: skip
        if rc2 != 0:
            _warn(ctx, f"gh pr list --head не сработал (код {rc2}): проверка закрытых PR пропущена")
            continue
        try:
            answer = json.loads(out2)
            if not isinstance(answer, list):  # gh returns a list; anything else is not "no PRs"
                raise TypeError("not a list")
            states = {str(p.get("state")) for p in answer if p.get("headRefName") == branch}
        except (json.JSONDecodeError, AttributeError, TypeError):
            _warn(ctx, "gh pr list --head: вывод не разобран, проверка закрытых PR пропущена")
            continue
        if "CLOSED" in states and not states & {"OPEN", "MERGED"}:
            closed_unmerged.add(branch)
    items: list[Item] = []
    for wt, branch in trees:
        rc3, st = _git(ctx, wt, "status", "--porcelain")
        if rc3 != 0:
            _warn(
                ctx, f"git status не сработал в {wt.name} (код {rc3}): чистота worktree неизвестна"
            )
            dirty: list[str] = []
        else:
            dirty = [ln for ln in st.splitlines() if not any(j in ln for j in _JUNK_PREFIXES)]
        label = f"{wt.name} ({branch})"
        if dirty:
            items.append(
                Item(
                    "open",
                    "git",
                    f"несохранённые правки в worktree {label}",
                    f"{len(dirty)} файл(ов)",
                    ref=str(wt),
                )
            )
        if branch in closed_unmerged:
            items.append(
                Item(
                    "open",
                    "git",
                    f"PR ветки {branch} закрыт без мержа",
                    f"worktree {wt.name}: работа может быть несмерженной",
                    ref=str(wt),
                )
            )
    return items


# --- collector: experiments / ledgers / parked ----------------------------------------------------
def collect_experiments(ctx: Context) -> list[Item]:
    if ctx.repo is None or not (ctx.repo / "experiments").is_dir():
        raise CollectorUnavailable("нет каталога experiments/")
    try:
        rhl = _health_loop()
    except Exception as exc:
        raise CollectorUnavailable(f"парсер экспериментов не загрузился: {exc}") from exc
    items: list[Item] = []
    for z in rhl._find_zombies(ctx.repo, ctx.today):
        m = re.search(r"\((\d+)d idle\)", z)
        items.append(
            Item(
                "overdue",
                "experiment",
                clean(f"эксперимент без вердикта: {z}", 120),
                "",
                int(m.group(1)) if m else None,
            )
        )
    return items


def collect_waiting(ctx: Context) -> list[Item]:
    """Ledger entries and parked rows wait for an EVENT: listed, never 'overdue'."""
    if ctx.repo is None:
        raise CollectorUnavailable("репозиторий не задан")
    if not (ctx.repo / "experiments").is_dir() and not (ctx.repo / "parked" / "INDEX.md").is_file():
        raise CollectorUnavailable(
            "нет ни experiments/, ни parked/INDEX.md: ждущих условий не найти"
        )
    items: list[Item] = []
    for led in sorted(ctx.repo.glob("experiments/*/ledger.md")):
        text = led.read_text(encoding="utf-8", errors="replace")
        for chunk in re.split(r"(?m)^## Entry", text)[1:]:
            title = clean(chunk.splitlines()[0].strip(" —-:"), 90) if chunk.strip() else "entry"
            m = re.search(r"\*\*Check after:\*\*\s*(.+)", chunk)
            items.append(
                Item(
                    "waiting",
                    "ledger",
                    f"{led.parent.name}: {title}",
                    clean(m.group(1), 120) if m else "условие не указано",
                    ref=str(led),
                )
            )
    parked = ctx.repo / "parked" / "INDEX.md"
    if parked.is_file():
        for line in parked.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.startswith("| 20"):
                continue
            cells = split_row(line) or []
            if len(cells) >= 4:
                items.append(
                    Item(
                        "waiting",
                        "parked",
                        clean(cells[2], 70),
                        clean(cells[3], 150),
                        ref=str(parked),
                    )
                )
    return items


# --- thread store (the only manual layer) ---------------------------------------------------------
STORE_HEADER = "| id | opened | thread | source | next | trigger | status |"
STORE_SEP = "|---|---|---|---|---|---|---|"
_STORE_KEYS = ("id", "opened", "thread", "source", "next", "trigger", "status")
LOCK_WAIT_S = 5.0  # how long `add`/`close` wait for another process holding the store
_TID = re.compile(r"T-(\d{8})-(\d+)$")
_STRICT_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _write_text(path: Path, text: str, newline: str = "\n", bom: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(text.replace("\n", newline).encode("utf-8-sig" if bom else "utf-8"))
    os.replace(tmp, path)


def _read_store_text(path: Path) -> tuple[str, str, bool]:
    """(text with \\n newlines, original newline, had BOM). Refuses a file that is not UTF-8:
    decoding with replacement and rewriting would destroy bytes outside the row being edited."""
    data = path.read_bytes()
    bom = data.startswith(b"\xef\xbb\xbf")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"реестр нитей не в UTF-8 ({exc.reason}): править вручную, автозапись отключена"
        ) from exc
    newline = "\r\n" if "\r\n" in text else "\n"
    return text.replace("\r\n", "\n"), newline, bom


def _store_esc(s: str, limit: int = 400) -> str:
    """Backslash first, then pipe: the pair of operations is reversible by `_store_unesc`."""
    return clean(s, limit).replace("\\", "\\\\").replace("|", "\\|")


def _store_unesc(s: str) -> str:
    # `split_row` already turned an escaped pipe back into `|`; what is left is doubled backslashes
    return s.replace("\\\\", "\\")


def _strict_date(text: str) -> date | None:
    m = _STRICT_DATE.fullmatch(text.strip())
    if not m:
        return None
    try:
        return date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None


def _check_trigger(trigger: str) -> str:
    t = clean(trigger, 120)
    if not t:
        return ""
    low = t.lower()
    if low.startswith("date:"):
        d = _strict_date(t[5:])
        if d is None:
            raise ValueError("trigger date: ожидает YYYY-MM-DD (существующая дата)")
        return f"date:{d.isoformat()}"
    if low.startswith("event:"):
        if not t[6:].strip():
            raise ValueError("trigger event: не может быть пустым")
        return t
    raise ValueError("trigger: date:YYYY-MM-DD или event:<текст>")


def _parse_store(text: str) -> tuple[list[dict[str, str]], list[tuple[str, int]]]:
    """(recognised rows, malformed rows). A row that is not exactly 7 cells is never guessed."""
    rows: list[dict[str, str]] = []
    malformed: list[tuple[str, int]] = []
    for line in text.splitlines():
        cells = split_row(line)
        if not cells or cells[0].lower() == "id":
            continue
        if all(re.fullmatch(r"[-: ]+", c) for c in cells):
            continue
        if len(cells) == len(_STORE_KEYS):
            r = dict(zip(_STORE_KEYS, cells, strict=True))
            for k in ("thread", "source", "next", "trigger"):
                r[k] = _store_unesc(r[k])
            rows.append(r)
        elif cells[0].startswith("T-"):
            malformed.append((cells[0], len(cells)))
    return rows, malformed


def _read_store_full(path: Path) -> tuple[list[dict[str, str]], list[tuple[str, int]]]:
    if not path.is_file():
        return [], []
    return _parse_store(_read_store_text(path)[0])


def _read_store(path: Path) -> list[dict[str, str]]:
    return _read_store_full(path)[0]


def _new_store_lines() -> list[str]:
    return [
        "---",
        "type: thread-store",
        "generated-by: scripts/threads_center.py add|close",
        "---",
        "",
        "# Нити (реестр)",
        "",
        "Ручной слой Центра нитей. Команды `add` / `close` меняют только свою строку;",
        "остальной текст файла они не трогают.",
        "`trigger`: `date:YYYY-MM-DD` (станет просроченным) или `event:…` (ждёт события).",
        "Спецсимволы в ячейке: `|` пишется как `\\|`, обратная косая как `\\\\`.",
        "",
        STORE_HEADER,
        STORE_SEP,
    ]


def _row_line(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


@contextlib.contextmanager
def _store_lock(path: Path) -> Iterator[None]:
    """Cross-process lock (O_EXCL lock file): two simultaneous `add` calls must not share an id."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    deadline = time.monotonic() + LOCK_WAIT_S
    while True:
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            with contextlib.suppress(OSError):
                if time.time() - lock.stat().st_mtime > 30:  # a crashed holder
                    lock.unlink()
                    continue
            if time.monotonic() > deadline:
                raise OSError(f"реестр нитей занят другим процессом: {lock}") from None
            time.sleep(0.05)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            lock.unlink()


def add_thread(
    path: Path, text: str, today: date, *, source: str = "chat", nxt: str = "", trigger: str = ""
) -> str:
    text = clean(text, 400)
    if not text:
        raise ValueError("пустой текст нити")
    trig = _check_trigger(trigger)
    with _store_lock(path):
        if path.is_file():
            body, newline, bom = _read_store_text(path)
            lines = body.splitlines()
        else:
            lines, newline, bom = _new_store_lines(), "\n", False
        rows, malformed = _parse_store("\n".join(lines))
        prefix = f"T-{today:%Y%m%d}-"
        nums = [
            int(m[2])
            for tid in [r["id"] for r in rows] + [t for t, _ in malformed]
            if tid.startswith(prefix) and (m := _TID.match(tid))
        ]
        tid = f"{prefix}{max(nums, default=0) + 1:02d}"
        new = _row_line(
            [
                tid,
                today.isoformat(),
                _store_esc(text),
                _store_esc(source, 40),
                _store_esc(nxt, 200),
                _store_esc(trig, 120),
                "open",
            ]
        )
        hdr = next(
            (i for i, ln in enumerate(lines) if (c := split_row(ln)) and c[:2] == ["id", "opened"]),
            None,
        )
        if hdr is None:
            lines += ["", STORE_HEADER, STORE_SEP, new]
        else:
            j = hdr + 1
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            lines.insert(j, new)
        _write_text(path, "\n".join(lines) + "\n", newline, bom)
    return tid


def close_thread(path: Path, tid: str, status: str = "done") -> None:
    if status not in ("done", "dropped"):
        raise ValueError("status должен быть done или dropped")
    if not path.is_file():
        raise KeyError(f"нить {tid} не найдена")
    with _store_lock(path):
        body, newline, bom = _read_store_text(path)
        lines = body.splitlines()
        hits = [i for i, ln in enumerate(lines) if (c := split_row(ln)) and c[0] == tid]
        if not hits:
            raise KeyError(f"нить {tid} не найдена")
        if len(hits) > 1:
            raise ValueError(f"id {tid} встречается {len(hits)} раза: поправьте реестр вручную")
        raw = _split_raw(lines[hits[0]]) or []
        if len(raw) != len(_STORE_KEYS):
            raise ValueError(
                f"строка {tid}: {len(raw)} ячеек вместо {len(_STORE_KEYS)}, "
                "автоматически закрыть нельзя"
            )
        raw[6] = status
        lines[hits[0]] = _row_line(raw)  # only this row changes; every other byte stays
        _write_text(path, "\n".join(lines) + "\n", newline, bom)


def collect_threads(ctx: Context) -> list[Item]:
    if (
        not ctx.threads_file.is_file()
        and not ctx.vault.is_dir()
        and not ctx.threads_file.parent.is_dir()
    ):
        raise CollectorUnavailable(
            f"нет ни vault, ни папки реестра нитей: {ctx.threads_file.parent}"
        )
    rows, malformed = _read_store_full(ctx.threads_file)
    items: list[Item] = [
        Item(
            "open",
            "thread",
            f"строка нити {tid} в реестре не разобрана",
            f"{n} ячеек вместо {len(_STORE_KEYS)} (вероятно неэкранированный |): править вручную",
            None,
            "thread-store",
            tid,
        )
        for tid, n in malformed
    ]
    for r in rows:
        if r["status"].lower() in ("done", "dropped"):
            continue
        age = days_between(ctx.today, parse_date(r["opened"]))
        trig = r["trigger"].strip()
        low = trig.lower()
        title = clean(r["thread"], 130)
        detail = clean(f"след. шаг: {r['next']}" if r["next"] else "", 130)
        if low.startswith("date:"):
            due = _strict_date(trig[5:])
            if due is None:
                bad = f"триггер не разобран: {clean(trig, 40)}. {detail}".strip()
                items.append(Item("open", "thread", title, bad, age, "thread-store", r["id"]))
                continue
            if due <= ctx.today:
                items.append(
                    Item(
                        "overdue",
                        "thread",
                        title,
                        f"срок {due}. {detail}".strip(),
                        days_between(ctx.today, due),
                        "thread-store",
                        r["id"],
                    )
                )
                continue
        elif low.startswith("event:"):
            items.append(
                Item(
                    "waiting",
                    "thread",
                    title,
                    clean(f"{trig[6:].strip()}. {detail}", 160),
                    age,
                    "thread-store",
                    r["id"],
                )
            )
            continue
        elif trig:
            bad = f"триггер не разобран: {clean(trig, 40)}. {detail}".strip()
            items.append(Item("open", "thread", title, bad, age, "thread-store", r["id"]))
            continue
        items.append(Item("open", "thread", title, detail, age, "thread-store", r["id"]))
    return items


# --- collector: vault freshness -------------------------------------------------------------------
_WIKILINK = re.compile(r"(?<!!)\[\[([^\]\n]+?)\]\]")
_NON_MD_EXT = re.compile(r"\.(png|jpe?g|gif|svg|pdf|webp|mp4|csv|json|html|txt)$", re.I)
_HEADER_DATE_RES = (
    re.compile(r"(?im)^updated:\s*(\d{4}-\d{2}-\d{2})"),
    re.compile(r"(?i)last updated:?\s*(\d{4}-\d{2}-\d{2})"),
    re.compile(r"(?i)(?:обновлено|обновл[её]н)\s*:?\s*(\d{4}-\d{2}-\d{2})"),
    re.compile(r"(?i)\(проверено\s+(\d{4}-\d{2}-\d{2})"),
)
_FILECOUNT_CLAIM = re.compile(
    r"(\d{1,3}(?:[ \u00a0,]\d{3})+|\d+)\s*(?:markdown\s+файл|\.md files?)", re.I
)
_FENCE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_MD_LINK = re.compile(r"\]\((?!https?:)[^)\s]+?\.md(?:#[^)]*)?\)")


def _strip_code(text: str) -> str:
    """Links inside code fences or inline code are examples, not links."""
    return _INLINE_CODE.sub("", _FENCE.sub("", text))


def _vault_index(vault: Path) -> tuple[set[str], set[str], int]:
    rel: set[str] = set()
    base: set[str] = set()
    count = 0
    for p in vault.rglob("*.md"):
        count += 1
        r = p.relative_to(vault).as_posix().lower()
        rel.add(r.removesuffix(".md"))
        base.add(p.stem.lower())
    return rel, base, count


def broken_links(text: str, rel: set[str], base: set[str]) -> int:
    broken = 0
    for m in _WIKILINK.finditer(_strip_code(text)):
        # `[[note\|alias]]` is the mandatory alias form inside a table cell
        target = re.split(r"\\?\|", m.group(1), maxsplit=1)[0].split("#", 1)[0].strip()
        if (
            not target
            or target.lower().startswith(("http:", "https:"))
            or _NON_MD_EXT.search(target)
        ):
            continue
        t = target.replace("\\", "/").lower().removesuffix(".md")
        if "/" in t:
            if t not in rel:
                broken += 1
        elif t not in base and t not in rel:
            broken += 1
    return broken


def header_date(text: str) -> date | None:
    head = "\n".join(text.splitlines()[:60])
    for rx in _HEADER_DATE_RES:
        m = rx.search(head)
        if m:
            return parse_date(m.group(1))
    return None


def collect_vault(ctx: Context) -> list[Item]:
    if not ctx.vault.is_dir():
        raise CollectorUnavailable(f"vault не найден: {ctx.vault}")
    rel, base, md_count = _vault_index(ctx.vault)
    ctx.cache["vault_md_count"] = md_count
    hubs = [ctx.vault / h for h in VAULT_HUBS]
    for g in VAULT_HUB_GLOBS:
        hubs.extend(sorted(ctx.vault.glob(g)))
    rows: list[dict[str, Any]] = []
    for hub in hubs:
        if not hub.is_file():
            continue
        name = hub.relative_to(ctx.vault).as_posix()
        text = hub.read_text(encoding="utf-8", errors="replace")
        mtime = _local_date(hub.stat().st_mtime)
        age = days_between(ctx.today, mtime) or 0
        hdate = header_date(text)
        gap = (mtime - hdate).days if hdate else None
        body = _strip_code(text)
        links = len(_WIKILINK.findall(body)) + len(_MD_LINK.findall(body))
        bad = broken_links(text, rel, base)
        notes: list[str] = []
        if age > HUB_STALE_DAYS:
            notes.append(f"не менялся {age} дн.")
        if gap is not None and gap > HEADER_GAP_DAYS:
            notes.append(f"mtime свежий, но своя дата «{hdate}» на {gap} дн. старше")
        claim = _FILECOUNT_CLAIM.search(text)
        if claim:
            claimed = int(re.sub(r"\D", "", claim.group(1)) or 0)
            if claimed and abs(claimed - md_count) / md_count > 0.10:
                notes.append(f"утверждает {claimed} .md-файлов, сейчас {md_count}")
        rows.append(
            {
                "hub": name,
                "age_days": age,
                "header_date": hdate.isoformat() if hdate else "",
                "header_gap": gap,
                "wikilinks": links,
                "broken": bad,
                "notes": "; ".join(notes),
            }
        )
    stale = sorted((r for r in rows if r["notes"]), key=lambda r: -r["age_days"])
    isolated = [r for r in rows if r["wikilinks"] == 0 and not r["notes"]]
    items: list[Item] = []
    if stale:
        worst = ", ".join(f"{r['hub']} ({r['age_days']} дн.)" for r in stale[:3])
        items.append(
            Item(
                "overdue",
                "vault",
                f"Obsidian: {len(stale)} из {len(rows)} хабов устарели",
                f"самые старые: {worst}. Подробности и причины: таблица хабов ниже",
                stale[0]["age_days"],
                ref="vault hubs",
            )
        )
    if isolated:
        items.append(
            Item(
                "open",
                "vault",
                f"Obsidian: {len(isolated)} хабов без единой wikilink",
                ", ".join(r["hub"] for r in isolated[:4]),
                ref="vault hubs",
            )
        )
    broken = sorted((r for r in rows if r["broken"]), key=lambda r: -r["broken"])
    if broken:  # a fresh, linked hub can still point at notes that do not exist
        items.append(
            Item(
                "open",
                "vault",
                f"Obsidian: {len(broken)} хабов с битыми wikilinks "
                f"(всего {sum(r['broken'] for r in broken)})",
                ", ".join(f"{r['hub']} ({r['broken']})" for r in broken[:4]),
                ref="vault hubs",
            )
        )
    ctx.cache["vault_hubs"] = rows
    return items


COLLECTORS: tuple[tuple[str, Callable[[Context], list[Item]]], ...] = (
    ("automations", collect_automations),
    ("pearls", collect_pearls),
    ("prs", collect_prs),
    ("git", collect_git),
    ("experiments", collect_experiments),
    ("waiting", collect_waiting),
    ("threads", collect_threads),
    ("vault", collect_vault),
)
NOT_COVERED = (
    "облачные routines claude.ai (FocusOS и др.): только через RemoteTrigger, не из скрипта",
    "задачи Claude Desktop (scheduled-tasks): читаются только через MCP, не из скрипта",
)


def build_snapshot(
    ctx: Context,
    collectors: tuple[tuple[str, Callable[[Context], list[Item]]], ...] | None = None,
) -> dict[str, Any]:
    items: list[Item] = []
    ran: dict[str, int] = {}
    errors: list[str] = []
    for name, fn in COLLECTORS if collectors is None else collectors:
        ctx.cache.pop("warnings", None)
        try:
            got = fn(ctx)
        except CollectorUnavailable as exc:
            errors.append(f"{name}: НЕ ПРОВЕРЕНО — {clean(str(exc), 160)}")
            got = None
        except Exception as exc:  # a broken collector must never hide the others
            errors.append(f"{name}: СБОЙ СБОРЩИКА — {type(exc).__name__}: {clean(str(exc), 140)}")
            got = None
        errors.extend(f"{name}: ЧАСТИЧНО — {w}" for w in ctx.cache.pop("warnings", []))
        if got is None:
            continue
        ran[name] = len(got)
        items.extend(got)
    items = _drift_pr_claims(ctx, items)
    counts = {s: sum(1 for i in items if i.section == s) for s in SECTIONS}
    status = "INSUFFICIENT_DATA" if not ran else "OK"
    snap_items = [asdict(i) for i in sorted(items, key=_sort_key)]
    tracked = ctx.seen_file is not None
    if ctx.seen_file is not None:
        seen, problem = _load_seen(ctx.seen_file)
        if problem is None and ctx.scope is not None and seen.get("scope") not in (None, ctx.scope):
            problem = (
                "история относится к другому набору источников (репо/vault/реестры): "
                "«в списке N дн.» не показано"
            )
        if problem:
            errors.append(f"история: ЧАСТИЧНО — {problem}")
            tracked = False
        else:
            for d in snap_items:
                e = seen["items"].get(_item_key(d["kind"], d["ref"], d["title"]))
                first = (
                    parse_date(str(e.get("first_seen", "")))
                    if isinstance(e, dict) and not e.get("gone")
                    else None
                )
                d["first_seen"] = (first or ctx.today).isoformat()
                d["listed_days"] = (ctx.today - (first or ctx.today)).days
    return {
        "status": status,
        "seen_tracked": tracked,
        "history": archive_history(ctx.vault, ctx.today),
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "today": ctx.today.isoformat(),
        "counts": counts,
        "collectors_ran": ran,
        "collector_errors": errors,
        "not_covered": list(NOT_COVERED),
        "items": snap_items,
        "vault_hubs": ctx.cache.get("vault_hubs", []),
        "vault_md_count": ctx.cache.get("vault_md_count"),
        "open_pr_count": ctx.cache.get("open_pr_count"),
    }


def _drift_pr_claims(ctx: Context, items: list[Item]) -> list[Item]:
    """Hubs that state an open-PR count different from gh's count (only when both are known)."""
    real = ctx.cache.get("open_pr_count")
    if real is None or not ctx.vault.is_dir():
        return items
    rx = re.compile(r"(\d+)\s+(?:open PRs?|открыт\w*\s+PR)", re.I)
    out = list(items)
    for name in VAULT_HUBS:
        hub = ctx.vault / name
        if not hub.is_file():
            continue
        m = rx.search(hub.read_text(encoding="utf-8", errors="replace"))
        if m and int(m.group(1)) != real:
            out.append(
                Item(
                    "overdue",
                    "vault_claim",
                    f"хаб устарел: {name}",
                    f"утверждает {m.group(1)} открытых PR, сейчас {real}",
                    ref=name,
                )
            )
    return out


def _sort_key(i: Item) -> tuple[int, int, int]:
    return (SECTIONS.index(i.section), KIND_ORDER.get(i.kind, 99), -(i.age_days or 0))


# --- history: first listed, weekly archive, kill-criterion stats ------------------------------
def _item_key(kind: str, ref: str, title: str) -> str:
    """Stable identity of a row across weeks. Counters inside titles (`14 PRs`, `17 of 18 hubs`,
    `(123d idle)`) change without the row being a different thing, so they are neutralised."""
    t = re.sub(r"\(\d+d idle\)", "(#d idle)", title)
    if kind == "vault":
        t = re.sub(r"\d+", "#", t)
    elif kind == "pr" and not t.startswith("PR #"):
        t = re.sub(r"^\d+", "#", t)
    raw = f"{kind}|{ref if kind in ('automation', 'thread') else ''}|{t}"
    if kind == "pr" and ref:
        # A pull request is its URL: editing the title must not turn it into "gone + new", which
        # would count a live PR as resolved and reset its overdue age.
        raw = f"pr|{ref}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _scope_id(repo: Path | None, vault: Path, registries: list[Path], store: Path) -> str:
    """Identity of WHAT was inspected. History from one source set must never judge another."""
    parts = [str(repo.resolve()) if repo else "", str(vault.resolve()), str(store.resolve())]
    parts += sorted(str(p.resolve()) for p in registries)
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]


def _empty_seen() -> dict[str, Any]:
    return {"version": 1, "items": {}, "renders": []}


def _load_seen(path: Path) -> tuple[dict[str, Any], str | None]:
    """(store, problem). A missing file is an honest 'no history yet'; a damaged one is reported."""
    if not path.is_file():
        return _empty_seen(), None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return (
            _empty_seen(),
            f"файл истории повреждён ({type(exc).__name__}): «в списке N дн.» не показано",
        )
    if not isinstance(data, dict) or not isinstance(data.get("items"), dict):
        return _empty_seen(), "файл истории неожиданного формата: «в списке N дн.» не показано"
    data.setdefault("renders", [])
    return data, None


def iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


_WEEK_NOTE = re.compile(r"\d{4}-W\d{2}$")


def archive_history(vault: Path, today: date, limit: int = 8) -> list[str]:
    """Wikilink targets of earlier weekly notes (newest first, current week excluded)."""
    folder = vault / ARCHIVE_DIR_REL
    if not folder.is_dir():
        return []
    cur = iso_week(today)
    names = sorted(
        (p.stem for p in folder.glob("*.md") if _WEEK_NOTE.match(p.stem) and p.stem != cur),
        reverse=True,
    )
    return [f"{ARCHIVE_DIR_REL}/{n}" for n in names[:limit]]


def update_seen(
    path: Path, snap: dict[str, Any], today: date, scope: str | None = None
) -> str | None:
    """Record this render; returns a note when something unusual happened (damaged file set aside).

    A row is marked GONE only when ALL its collectors ran cleanly: an unreadable source says nothing
    about whether its rows were resolved (unknown != resolved). History from a different source set
    (another repo, vault or registries) is refused, never merged: it would mark every row gone."""
    note: str | None = None
    data, problem = _load_seen(path)
    if problem and path.is_file():
        aside = path.with_name(f"{path.name}.corrupt-{today.isoformat()}")
        os.replace(path, aside)  # keep the bytes; start a new history instead of silently wiping
        note = f"история была повреждена, сохранена как {aside.name}; начата новая"
        data = _empty_seen()
    if scope is not None:
        if data.get("scope") not in (None, scope):
            raise ValueError(
                "история относится к другому набору источников (репо/vault/реестры): "
                "укажите отдельный --seen-file"
            )
        data["scope"] = scope
    items: dict[str, Any] = data["items"]
    ran = set(snap["collectors_ran"])
    partial = {e.split(":", 1)[0] for e in snap["collector_errors"] if "ЧАСТИЧНО" in e}
    trusted = {
        k for k, cs in KIND_COLLECTOR.items() if all(c in ran and c not in partial for c in cs)
    }
    now = today.isoformat()
    current: set[str] = set()
    for i in snap["items"]:
        key = _item_key(i["kind"], i["ref"], i["title"])
        current.add(key)
        e = items.get(key)
        if not isinstance(e, dict) or e.get("gone"):
            items[key] = {
                "first_seen": now,
                "last_seen": now,
                "overdue_since": now if i["section"] == "overdue" else None,
                "kind": i["kind"],
                "section": i["section"],
                "title": clean(i["title"], 100),
            }
        else:
            e["last_seen"] = now
            e["section"] = i["section"]
            if i["section"] == "overdue" and not e.get("overdue_since"):
                e["overdue_since"] = now
    for key, e in list(items.items()):
        if not isinstance(e, dict):
            del items[key]
            continue
        if key not in current and not e.get("gone") and e.get("kind") in trusted:
            e["gone"] = now
        gone = parse_date(str(e.get("gone", "")))
        if gone is not None and (today - gone).days > SEEN_KEEP_DAYS:
            del items[key]
    renders = [r for r in data["renders"] if isinstance(r, str)]
    if now not in renders:
        renders.append(now)
    data["renders"] = renders[-60:]
    _write_text(path, json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    return note


def seen_stats(path: Path, today: date) -> dict[str, Any]:
    """The kill criterion, computed instead of eyeballed.

    Only rows that were OVERDUE for STATS_MIN_DAYS+ days are judged. Routine rows (a fresh PR,
    a dirty worktree) close through normal work whether or not anyone reads the page; counting
    them would let the criterion pass with nothing acted on because of the tool. Descriptive:
    'gone from the list' means resolved OR dropped OR fixed elsewhere, not 'closed by this tool'."""
    data, problem = _load_seen(path)
    renders = sorted({r for r in data["renders"] if parse_date(r)})
    first = parse_date(renders[0]) if renders else None
    span = (today - first).days if first else 0
    old = [
        e
        for e in data["items"].values()
        if isinstance(e, dict)
        and (d := parse_date(str(e.get("overdue_since") or ""))) is not None
        and (today - d).days >= STATS_MIN_DAYS
    ]
    closed = sum(1 for e in old if e.get("gone"))
    share = closed / len(old) if old else None
    if problem:
        verdict = f"НЕТ ДАННЫХ: {problem}"
    elif len(renders) < STATS_MIN_RENDERS or span < STATS_MIN_DAYS - 7:
        verdict = (
            f"НЕДОСТАТОЧНО ИСТОРИИ: запусков {len(renders)} из {STATS_MIN_RENDERS} нужных, "
            f"период {span} дн."
        )
    elif share is None:
        verdict = f"НЕТ СТРОК, просроченных {STATS_MIN_DAYS}+ дн., оценивать нечего"
    elif share >= STATS_KEEP_SHARE:
        verdict = "ОСТАВИТЬ: доля ушедших из списка не ниже 1/3 (описательно)"
    else:
        verdict = "КРИТЕРИЙ ОТМЕНЫ: ушло из списка меньше 1/3 строк, инструмент провизорный, убрать"
    return {
        "renders": len(renders),
        "span_days": span,
        "judged": len(old),
        "gone": closed,
        "share": share,
        "verdict": verdict,
    }


# --- rendering ------------------------------------------------------------------------------------
def _by_section(snap: dict[str, Any], section: str) -> list[dict[str, Any]]:
    return [i for i in snap["items"] if i["section"] == section]


def _age(i: dict[str, Any]) -> str:
    return f"{i['age_days']} дн." if i.get("age_days") is not None else "—"


def _listed(i: dict[str, Any]) -> str:
    n = i.get("listed_days")
    if n is None:
        return "—"
    return "новое" if n == 0 else f"{n} дн."


def _unchecked(snap: dict[str, Any]) -> int:
    """Sources that could not be read at all (a PARTIAL warning is counted separately)."""
    return sum(1 for e in snap["collector_errors"] if "ЧАСТИЧНО" not in e)


def _headline(snap: dict[str, Any]) -> str:
    c = snap["counts"]
    unchecked = _unchecked(snap)
    partial = len(snap["collector_errors"]) - unchecked
    tail = f" · НЕ ПРОВЕРЕНО источников: {unchecked}" if unchecked else ""
    tail += f" · ЧАСТИЧНО: {partial}" if partial else ""
    return f"ПРОСРОЧЕНО {c['overdue']} · ОТКРЫТО {c['open']} · ЖДУТ СОБЫТИЯ {c['waiting']}{tail}"


def render_markdown(snap: dict[str, Any], hub_links: bool = True, week: str | None = None) -> str:
    c = snap["counts"]
    L: list[str] = [
        "---",
        "type: dashboard-snapshot" if week else "type: dashboard",
        *([f"week: {week}"] if week else []),
        "tool: scripts/threads_center.py",
        f"generated: {snap['generated']}",
        *(
            [f"overdue: {c['overdue']}", f"open: {c['open']}", f"waiting: {c['waiting']}"]
            if week
            else []
        ),
        "auto-generated: true",
        "---",
        "",
        f"# Центр нитей — неделя {week}" if week else "# Центр нитей",
        "",
        "> АВТОГЕНЕРАЦИЯ. Не править: файл перезаписывается. "
        "Источники и пороги: `docs/threads-center.md`.",
        "",
        f"**{_headline(snap)}** · обновлено {snap['generated']}",
        "",
    ]
    if week:
        L += [f"Живая версия: [[{THREADS_NOTE_REL.removesuffix('.md')}]]", ""]
    if snap.get("history"):
        L += ["Предыдущие недели: " + " · ".join(f"[[{h}]]" for h in snap["history"]), ""]
    for sec in SECTIONS:
        rows = _by_section(snap, sec)
        L += [f"## {SECTION_TITLES[sec]} ({len(rows)})", ""]
        if not rows:
            L += ["_пусто_", ""]
            continue
        tracked = bool(snap.get("seen_tracked"))
        if tracked:
            L += ["| что | подробности | возраст | в списке | источник |", "|---|---|---|---|---|"]
        else:
            L += ["| что | подробности | возраст | источник |", "|---|---|---|---|"]
        for i in rows[:LIST_CAP]:
            mid = f"{_age(i)} | {_listed(i)}" if tracked else _age(i)
            L.append(
                f"| {md_cell(i['title'])} | {md_cell(i['detail'])} | {mid} | {md_cell(i['kind'])} |"
            )
        if len(rows) > LIST_CAP:
            L.append(f"| … и ещё {len(rows) - LIST_CAP} |{' |' * (4 if tracked else 3)}")
        L.append("")
    L += ["## OBSIDIAN: свежесть хабов", ""]
    hubs = snap.get("vault_hubs") or []
    if hubs:
        L += [
            "| хаб | возраст | своя дата | wikilinks | битых | проблема |",
            "|---|---|---|---|---|---|",
        ]
        for h in sorted(hubs, key=lambda x: -x["age_days"]):
            name = h["hub"]
            link = f"[[{name.removesuffix('.md')}]]" if hub_links else md_cell(name)
            L.append(
                f"| {link} | {h['age_days']} дн. | {h['header_date'] or '—'} | "
                f"{h['wikilinks']} | {h['broken']} | {md_cell(h['notes'])} |"
            )
        L.append("")
    else:
        L += ["_не проверено_", ""]
    L += ["## ПОКРЫТИЕ", ""]
    for name, n in snap["collectors_ran"].items():
        L.append(f"- {name}: проверено, найдено {n}")
    for err in snap["collector_errors"]:
        L.append(f"- **{md_cell(err)}**")
    for nc in snap["not_covered"]:
        L.append(f"- не охвачено: {md_cell(nc)}")
    L.append("")
    kinds = sorted({i["kind"] for i in snap["items"]}, key=lambda k: KIND_ORDER.get(k, 99))
    L += ["## ЧТО ЭТО ЗА СТРОКИ", ""]
    L += [f"- **{k}**: {KIND_LEGEND[k]}" for k in kinds if k in KIND_LEGEND]
    if snap.get("seen_tracked"):
        L.append(
            "- **в списке**: сколько дней строка попадает в отчёт с первого запуска `render` на "
            "этой машине. «новое» значит «замечено впервые», а не «возникло сегодня»: "
            "раньше истории нет."
        )
    L.append("")
    return "\n".join(L)


_CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--card:#f6f6f7;--line:#e2e2e5;--red:#b42318;--amb:#b54708;--blu:#175cd3}
@media(prefers-color-scheme:dark){:root{--bg:#141416;--fg:#ececee;--mut:#9a9aa2;--card:#1d1d21;--line:#2c2c32;
--red:#f97066;--amb:#fdb022;--blu:#84adff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.45 system-ui,Segoe UI,Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:0 0 4px}.sub{color:var(--mut);font-size:13px;margin-bottom:14px}
.strip{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}
.pill{flex:1 1 150px;background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:10px 14px}
.pill b{display:block;font-size:26px;line-height:1.1}.pill span{color:var(--mut);font-size:12px}
.pill.overdue b{color:var(--red)}.pill.open b{color:var(--blu)}.pill.waiting b{color:var(--amb)}
section{margin:0 0 18px}h2{font-size:15px;margin:0 0 8px}
ul{list-style:none;margin:0;padding:0}li{background:var(--card);border:1px solid var(--line);
border-radius:8px;padding:8px 12px;margin:0 0 6px}li small{display:block;color:var(--mut)}
.tag{float:right;color:var(--mut);font-size:12px;margin-left:8px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:5px 8px;
border-bottom:1px solid var(--line)}th{color:var(--mut);font-weight:600}
details>summary{cursor:pointer;color:var(--mut);margin:4px 0}.err{color:var(--red)}
"""


def render_html(snap: dict[str, Any]) -> str:
    e = html.escape
    c = snap["counts"]

    def pill(cls: str, n: int, label: str) -> str:
        return f'<div class="pill {cls}"><b>{n}</b><span>{e(label)}</span></div>'

    out = [
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        "<title>Центр нитей</title><style>" + _CSS + "</style></head><body><main>",
        "<h1>Центр нитей</h1>",
        f'<div class="sub">обновлено {e(snap["generated"])} · автогенерация, не править</div>',
        '<div class="strip">',
        pill("overdue", c["overdue"], "просрочено"),
        pill("open", c["open"], "открытых нитей"),
        pill("waiting", c["waiting"], "ждут события"),
        pill("", _unchecked(snap), "источников не проверено"),
        "</div>",
    ]
    for sec in SECTIONS:
        rows = _by_section(snap, sec)
        out.append(f"<section><h2>{e(SECTION_TITLES[sec])} ({len(rows)})</h2>")
        if not rows:
            out.append('<div class="sub">пусто</div></section>')
            continue

        def li(i: dict[str, Any]) -> str:
            ref = f" <small>{e(clean(i['ref'], 90))}</small>" if i.get("ref") else ""
            det = f"<small>{e(clean(i['detail'], 240))}</small>" if i["detail"] else ""
            seen = f" · в списке {e(_listed(i))}" if snap.get("seen_tracked") else ""
            return (
                f'<li><span class="tag">{e(i["kind"])} · {e(_age(i))}{seen}</span>'
                f"{e(clean(i['title'], 160))}{det}{ref}</li>"
            )

        head, tail = rows[:8], rows[8:LIST_CAP]
        out.append("<ul>" + "".join(li(i) for i in head) + "</ul>")
        if tail:
            out.append(
                f"<details><summary>ещё {len(rows) - len(head)}</summary><ul>"
                + "".join(li(i) for i in tail)
                + (
                    f"<li>… и ещё {len(rows) - LIST_CAP} не показано "
                    "(полный список: заметка Obsidian или collect --json)</li>"
                    if len(rows) > LIST_CAP
                    else ""
                )
                + "</ul></details>"
            )
        out.append("</section>")
    out.append("<section><h2>OBSIDIAN: свежесть хабов</h2>")
    hubs = snap.get("vault_hubs") or []
    if hubs:
        out.append(
            "<table><tr><th>хаб</th><th>возраст</th><th>своя дата</th>"
            "<th>wikilinks</th><th>битых</th><th>проблема</th></tr>"
        )
        for h in sorted(hubs, key=lambda x: -x["age_days"]):
            out.append(
                f"<tr><td>{e(clean(h['hub'], 80))}</td><td>{h['age_days']} дн.</td>"
                f"<td>{e(h['header_date'] or '—')}</td><td>{h['wikilinks']}</td>"
                f"<td>{h['broken']}</td><td>{e(clean(h['notes'], 160))}</td></tr>"
            )
        out.append("</table>")
    else:
        out.append('<div class="sub">не проверено</div>')
    out.append("</section><section><h2>ПОКРЫТИЕ</h2><ul>")
    for name, n in snap["collectors_ran"].items():
        out.append(f"<li>{e(name)}: проверено, найдено {n}</li>")
    for err in snap["collector_errors"]:
        out.append(f'<li class="err">{e(err)}</li>')
    for nc in snap["not_covered"]:
        out.append(f"<li>не охвачено: {e(nc)}</li>")
    out.append("</ul></section>")
    kinds = sorted({i["kind"] for i in snap["items"]}, key=lambda k: KIND_ORDER.get(k, 99))
    if kinds:
        out.append("<section><h2>ЧТО ЭТО ЗА СТРОКИ</h2><ul>")
        out += [f"<li><b>{e(k)}</b>: {e(KIND_LEGEND[k])}</li>" for k in kinds if k in KIND_LEGEND]
        out.append("</ul></section>")
    out.append("</main></body></html>")
    return "".join(out)


LAST_FILE_NAME = "threads-center-last.json"  # next to the HTML page; read by the SessionStart hook
_PR_NUMBER = re.compile(r"PR #\d+")
# Kinds whose free text comes from the user's own machine. A `pr` title is written by whoever opens
# the PR (the repo is public), and this file is shown in every session's context: never copy it.
_LOCAL_TEXT_KINDS = frozenset(
    {
        "automation",
        "pearl",
        "vault",
        "vault_claim",
        "thread",
        "git",
        "experiment",
        "ledger",
        "parked",
    }
)


def _safe_label(i: dict[str, Any]) -> str:
    if i["kind"] == "pr":
        m = _PR_NUMBER.match(i["title"])
        return (
            f"{m.group(0)} (открыт {i['age_days']} дн.)"
            if m and i.get("age_days")
            else (m.group(0) if m else "PR")
        )
    if i["kind"] in _LOCAL_TEXT_KINDS:
        return clean(i["title"], 90)
    return str(i["kind"])


def last_summary(snap: dict[str, Any], note: Path, page: Path, scope: str | None) -> dict[str, Any]:
    """The small file the SessionStart hook reads instead of running the collectors (10+ seconds).
    Contains no third-party free text, only counts and labels of rows from local sources."""
    unchecked = _unchecked(snap)
    return {
        "version": 1,
        "generated": snap["generated"],
        "today": snap["today"],
        "status": snap["status"],
        "counts": snap["counts"],
        "unchecked": unchecked,
        "partial": len(snap["collector_errors"]) - unchecked,
        "headline": _headline(snap),
        "top_overdue": [
            {"kind": i["kind"], "label": _safe_label(i)} for i in _by_section(snap, "overdue")[:3]
        ],
        "note": str(note),
        "page": str(page),
        "scope": scope,
    }


def summary_lines(snap: dict[str, Any]) -> list[str]:
    c = snap["counts"]
    lines = [f"[threads] {_headline(snap)}"]
    for i in _by_section(snap, "overdue")[:3]:
        lines.append(
            f"  • {clean(i['title'], 100)}"
            + (f" — {clean(i['detail'], 80)}" if i["detail"] else "")
        )
    if c["overdue"] > 3:
        lines.append(f"  … ещё {c['overdue'] - 3} просроченных")
    return lines


# --- context + CLI --------------------------------------------------------------------------------
def make_context(args: argparse.Namespace) -> Context:
    home = Path.home()
    vault = Path(args.vault) if args.vault else home / ".claude" / "memory"
    repo = Path(args.repo) if args.repo else _repo_root()
    registries = [Path(p) for p in (args.pearl_registry or [])] or [
        repo / "pearl_registry" / "INDEX.md",
        home / ".claude" / "rules" / "pearl_registry" / "INDEX.md",
    ]
    store = Path(args.threads_file) if args.threads_file else vault / THREADS_STORE_REL
    scope = _scope_id(repo, vault, registries, store)
    seen = (
        Path(args.seen_file)
        if args.seen_file
        else home / ".claude" / "state" / f"{SEEN_FILE_PREFIX}-{scope}.json"
    )
    return Context(
        today=_local_date(time.time()),
        repo=repo,
        vault=vault,
        pearl_registries=registries,
        threads_file=store,
        log_dir=Path(args.log_dir) if args.log_dir else home / ".claude" / "logs",
        task_pattern=args.task_pattern,
        seen_file=seen,
        scope=scope,
    )


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--vault", help="Obsidian vault root (default ~/.claude/memory)")
    p.add_argument("--repo", help="repository to inspect (default: this repo)")
    p.add_argument("--pearl-registry", action="append", help="pearl INDEX.md (repeatable)")
    p.add_argument("--threads-file", help="thread store note (default <vault>/09 System/…)")
    p.add_argument("--log-dir", help="task log directory (default ~/.claude/logs)")
    p.add_argument(
        "--seen-file", help="history store (default ~/.claude/state/threads-center-seen.json)"
    )
    p.add_argument(
        "--task-pattern", default=DEFAULT_TASK_PATTERN, help="regex of Task Scheduler names"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    _add_common(r)
    r.add_argument("--out-md", help=f"note path (default <vault>/{THREADS_NOTE_REL})")
    r.add_argument("--out-html", help="page path (default ~/.claude/state/threads-center.html)")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument(
        "--no-archive", action="store_true", help="do not write this week's archive note"
    )
    s = sub.add_parser("summary")
    _add_common(s)
    s.add_argument(
        "--alert",
        action="store_true",
        help="exit 1 if anything is overdue, 2 if a source could not be checked",
    )
    c = sub.add_parser("collect")
    _add_common(c)
    c.add_argument("--json", action="store_true")
    a = sub.add_parser("add")
    _add_common(a)
    a.add_argument("text")
    a.add_argument("--source", default="chat")
    a.add_argument("--next", dest="nxt", default="")
    a.add_argument("--trigger", default="")
    cl = sub.add_parser("close")
    _add_common(cl)
    cl.add_argument("tid")
    cl.add_argument("--status", default="done")
    ls = sub.add_parser("list")
    _add_common(ls)
    st = sub.add_parser("stats", help="kill criterion: share of listed rows that left the list")
    _add_common(st)
    sub.add_parser("install-hint")
    args = ap.parse_args(argv)

    if args.cmd == "install-hint":
        script = Path(__file__).resolve()
        print(
            "Не выполняется автоматически. Недельная задача без claude -p "
            "(из PowerShell, от вашего пользователя):\n"
            f'  $a = New-ScheduledTaskAction -Execute "{sys.executable}" -Argument '
            f'"{script} render" -WorkingDirectory "{script.parent.parent}"\n'
            "  $t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 07:30\n"
            "  $s = New-ScheduledTaskSettingsSet -StartWhenAvailable\n"
            '  Register-ScheduledTask -TaskName "Claude-ThreadsCenter-Weekly" '
            "-Action $a -Trigger $t -Settings $s\n"
            "-StartWhenAvailable: если в понедельник 07:30 ноутбук был выключен, запуск "
            "догонится при включении."
        )
        return 0

    ctx = make_context(args)
    if args.cmd == "stats":
        st_ = seen_stats(ctx.seen_file or Path(f"{SEEN_FILE_PREFIX}.json"), ctx.today)
        share = "—" if st_["share"] is None else f"{st_['share']:.0%}"
        print(
            f"запусков render: {st_['renders']}, период {st_['span_days']} дн.\n"
            f"строк, просроченных {STATS_MIN_DAYS}+ дн.: {st_['judged']}, из них ушло из списка: "
            f"{st_['gone']} ({share})\n{st_['verdict']}"
        )
        return 0
    try:
        if args.cmd == "add":
            tid = add_thread(
                ctx.threads_file,
                args.text,
                ctx.today,
                source=args.source,
                nxt=args.nxt,
                trigger=args.trigger,
            )
            print(f"записал: {tid}")
            return 0
        if args.cmd == "close":
            close_thread(ctx.threads_file, args.tid, args.status)
            print(f"закрыл: {args.tid} ({args.status})")
            return 0
        if args.cmd == "list":
            for row in _read_store(ctx.threads_file):
                print(f"{row['id']}  {row['status']:8} {row['opened']}  {row['thread']}")
            return 0
    except (ValueError, KeyError, OSError) as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 2

    snap = build_snapshot(ctx)
    if snap["status"] == "INSUFFICIENT_DATA":
        print("status: INSUFFICIENT_DATA\n" + "\n".join(snap["collector_errors"]))
        return 2  # "nothing could be checked" must never look like success
    if args.cmd == "collect":
        print(
            json.dumps(snap, ensure_ascii=False, indent=2)
            if args.json
            else "\n".join(summary_lines(snap))
        )
        return 0
    if args.cmd == "summary":
        print("\n".join(summary_lines(snap)))
        if args.alert and snap["counts"]["overdue"]:
            return 1
        return 2 if args.alert and snap["collector_errors"] else 0
    # render
    if args.dry_run:
        print("\n".join(summary_lines(snap)))
        return 0
    out_md = Path(args.out_md) if args.out_md else ctx.vault / THREADS_NOTE_REL
    out_html = (
        Path(args.out_html)
        if args.out_html
        else Path.home() / ".claude" / "state" / "threads-center.html"
    )
    _write_text(out_md, render_markdown(snap))
    _write_text(out_html, render_html(snap))
    _write_text(
        out_html.with_name(LAST_FILE_NAME),
        json.dumps(last_summary(snap, out_md, out_html, ctx.scope), ensure_ascii=False, indent=1)
        + "\n",
    )
    print("\n".join(summary_lines(snap)))
    print(f"note: {out_md}\npage: {out_html}")
    failed = False
    if not args.no_archive:
        week = iso_week(ctx.today)
        arch = ctx.vault / ARCHIVE_DIR_REL / f"{week}.md"
        try:
            _write_text(arch, render_markdown(snap, week=week))
            print(f"archive: {arch}")
        except OSError as exc:
            print(f"ошибка архива: {exc}", file=sys.stderr)
            failed = True
    if ctx.seen_file is not None:
        try:
            note = update_seen(ctx.seen_file, snap, ctx.today, ctx.scope)
            if note:
                print(note, file=sys.stderr)
        except (OSError, ValueError) as exc:
            print(f"ошибка истории: {exc}", file=sys.stderr)
            failed = True
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
