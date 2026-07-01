#!/usr/bin/env python3
"""SessionStart hook: weekly research-health audit.

WHY: Research experiments drift silently —
  - zombie experiments stay open past 30 days with no decision
  - pearl_registry entries lose their next_check anchor and decay
  - null_results accumulate without being applied to live claims

This hook fires once per week on SessionStart and surfaces the top
issues so the user can decide: close zombie / re-anchor pearl / retroscan.

Timer lives in ~/.claude/state/last_research_health.txt.
Fail-open: any error exits 0 so SessionStart is never blocked.
"""

from __future__ import annotations

import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from utils import emit_hook_result, find_file_upward, parse_stdin

_STATE_DIR = Path.home() / ".claude" / "state"
_LAST_HEALTH_FILE = _STATE_DIR / "last_research_health.txt"
_REVIEW_INTERVAL_DAYS = 7
_ZOMBIE_DAYS = 30

# Verdict keywords that mark an experiment as CLOSED
_CLOSED_VERDICTS = re.compile(
    r"\b(PROMOTE|REJECT|ARCHIVE|PROMOTED|REJECTED|ARCHIVED|HARD[-_]KILLED|KILLED)\b",
    re.IGNORECASE,
)

# Pearl registry table row — pipe-delimited, ≥7 columns
# | date | source | observation | falsifiable_prediction | trigger_condition | next_check | status |
_PEARL_ROW = re.compile(r"^\|(.+)\|(.+)\|(.+)\|(.+)\|(.+)\|(.+)\|(.+)\|")


# ── Timer helpers ─────────────────────────────────────────────────────────────


def _last_health_date() -> date | None:
    """Parse stored YYYY-MM-DD, or None if absent / corrupt."""
    if not _LAST_HEALTH_FILE.exists():
        return None
    try:
        text = _LAST_HEALTH_FILE.read_text(encoding="utf-8").strip()
        return datetime.fromisoformat(text[:10]).date()
    except (OSError, ValueError):
        return None


def _record_health_now(today: date) -> None:
    """Persist today's local date so the next 6 sessions skip the review."""
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _LAST_HEALTH_FILE.write_text(today.isoformat(), encoding="utf-8")
    except OSError as e:
        print(f"[research-health] state write failed: {e}", file=sys.stderr)


def _is_due(today: date) -> bool:
    last = _last_health_date()
    return last is None or (today - last) >= timedelta(days=_REVIEW_INTERVAL_DAYS)


# ── Project root discovery ────────────────────────────────────────────────────


def _find_project_root() -> Path | None:
    """Return project root (directory containing CLAUDE.md), or None."""
    claude_md = find_file_upward("CLAUDE.md")
    if claude_md is None:
        return None
    return claude_md.parent


# ── Zombie experiment detection ───────────────────────────────────────────────


def _experiment_is_closed(exp_dir: Path) -> bool:
    """True if decision.md contains a closed verdict."""
    decision = exp_dir / "decision.md"
    if not decision.exists():
        return False
    try:
        text = decision.read_text(encoding="utf-8", errors="ignore")
        return bool(_CLOSED_VERDICTS.search(text))
    except OSError:
        return False


def _last_modified_days(exp_dir: Path, today: date) -> float:
    """Days since the most recently modified file in exp_dir."""
    latest = 0.0
    try:
        for f in exp_dir.rglob("*"):
            try:
                if f.is_file():
                    mtime = f.stat().st_mtime
                    if mtime > latest:
                        latest = mtime
            except OSError:
                continue  # broken symlink or permission error — skip file, not the whole dir
    except OSError:
        return 0.0
    if latest == 0.0:
        return float("inf")
    delta = today - datetime.fromtimestamp(latest, tz=UTC).date()
    return delta.days


def _find_zombies(project_root: Path, today: date) -> list[str]:
    """Return names of experiments open >ZOMBIE_DAYS with no closed verdict."""
    exp_dir = project_root / "experiments"
    if not exp_dir.is_dir():
        return []
    zombies = []
    for child in sorted(exp_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("_"):  # skip _template etc.
            continue
        if _experiment_is_closed(child):
            continue
        days = _last_modified_days(child, today)
        if days > _ZOMBIE_DAYS:
            zombies.append(f"{child.name} ({int(days)}d idle)")
    return zombies


# ── Pearl registry checks ─────────────────────────────────────────────────────


def _parse_pearl_registry(registry_path: Path) -> list[dict[str, str]]:
    """Extract row dicts from pearl_registry/INDEX.md table."""
    entries = []
    try:
        lines = registry_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []

    # Find header row to determine column positions
    # Expected columns: date | source | observation | prediction | trigger | next_check | status
    for line in lines:
        m = _PEARL_ROW.match(line.strip())
        if not m:
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 7:
            continue
        # Skip separator rows (contain only dashes)
        if all(re.match(r"^[-: ]+$", c) for c in cols):
            continue
        # Skip header row
        if cols[0].lower() in ("date", "---"):
            continue
        entries.append(
            {
                "date": cols[0],
                "source": cols[1],
                "observation": cols[2],
                "next_check": cols[5] if len(cols) > 5 else "",
                "status": cols[6] if len(cols) > 6 else "",
            }
        )
    return entries


def _check_pearls(project_root: Path, today: date) -> tuple[list[str], list[str]]:
    """Return (overdue_pearls, unanchored_pearls)."""
    registry = project_root / "pearl_registry" / "INDEX.md"
    if not registry.exists():
        return [], []

    entries = _parse_pearl_registry(registry)
    overdue, unanchored = [], []

    for entry in entries:
        status = entry["status"].lower()
        if "reject" in status or "done" in status or "archive" in status:
            continue  # closed pearl, skip

        next_check = entry["next_check"].strip()
        label = entry["observation"][:50] if entry["observation"] else entry["source"]

        # Unanchored: missing or placeholder next_check
        if not next_check or next_check in ("-", "–", "—", "TBD", "tbd", "?"):
            unanchored.append(label)
            continue

        # Try to parse a date from next_check
        try:
            # Accept YYYY-MM-DD, YYYY-Q[1-4], or just YYYY
            date_str = next_check[:10]
            check_date = datetime.fromisoformat(date_str[:10]).date()
            if check_date <= today:
                overdue.append(f"{label} (due {check_date})")
        except ValueError:
            # Quarter format like "2026-Q3" — check if past Q1 of that year
            m = re.match(r"(\d{4})-Q([1-4])", next_check)
            if m:
                year, quarter = int(m.group(1)), int(m.group(2))
                quarter_start = datetime(year, (quarter - 1) * 3 + 1, 1, tzinfo=UTC).date()
                if quarter_start <= today:
                    overdue.append(f"{label} (Q{quarter} {year})")

    return overdue, unanchored


# ── Message formatting ────────────────────────────────────────────────────────


def _format_message(
    zombies: list[str],
    overdue_pearls: list[str],
    unanchored_pearls: list[str],
    project_name: str,
) -> str | None:
    """Return message string if any issues, else None (all healthy)."""
    if not zombies and not overdue_pearls and not unanchored_pearls:
        return None  # nothing to report — stay silent

    lines = [
        f"[research-health] Weekly audit — {project_name}",
    ]

    if zombies:
        lines.append(
            f"\n  🧟 ZOMBIE experiments ({len(zombies)}) — open >{_ZOMBIE_DAYS}d, no verdict:"
        )
        for z in zombies[:5]:
            lines.append(f"    • {z}")
        if len(zombies) > 5:
            lines.append(f"    … and {len(zombies) - 5} more")
        lines.append("  → Run /research-audit or add decision.md with PROMOTE/REJECT/ARCHIVE")

    if overdue_pearls:
        lines.append(f"\n  ⏰ OVERDUE pearls ({len(overdue_pearls)}) — next_check passed:")
        for p in overdue_pearls[:5]:
            lines.append(f"    • {p}")
        if len(overdue_pearls) > 5:
            lines.append(f"    … and {len(overdue_pearls) - 5} more")
        lines.append(
            "  → Open pearl_registry/INDEX.md, decide: promote / archive / update next_check"
        )

    if unanchored_pearls:
        lines.append(
            f"\n  ⚓ UNANCHORED pearls ({len(unanchored_pearls)}) — no next_check (decay: 2 weeks):"
        )
        for p in unanchored_pearls[:3]:
            lines.append(f"    • {p}")
        if len(unanchored_pearls) > 3:
            lines.append(f"    … and {len(unanchored_pearls) - 3} more")
        lines.append("  → Add next_check date to each pearl or mark status=archived")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parse_stdin()

    today = datetime.now(UTC).astimezone().date()
    if not _is_due(today):
        sys.exit(0)

    project_root = _find_project_root()
    if project_root is None:
        sys.exit(0)

    project_name = project_root.name

    zombies = _find_zombies(project_root, today)
    overdue_pearls, unanchored_pearls = _check_pearls(project_root, today)

    message = _format_message(zombies, overdue_pearls, unanchored_pearls, project_name)
    if message:
        emit_hook_result("SessionStart", message)

    _record_health_now(today)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"[research-health] fatal: {e}", file=sys.stderr)
        sys.exit(0)
