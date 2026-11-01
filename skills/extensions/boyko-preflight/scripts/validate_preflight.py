#!/usr/bin/env python3
"""Validate a boyko-preflight report (JSON) against the status contract.

WHY: a self-report from the model can only prove VISIBLE. This validator refuses
the stronger claims unless they carry evidence an independent log can confirm:
  - visible   needs a quoted line or file name;
  - executed  needs an event_id, and that id must appear in the events log if given;
  - followed  needs a behavioural test (a self-report never counts as FOLLOWED);
  - installed needs a file path (that is all it proves).
An overall "pass" is only accepted when the computed overall is also "pass".

Usage: python validate_preflight.py report.json [--events events.jsonl]
Exit code: 0 if the report is consistent, 1 otherwise. Always prints findings.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

STATUSES = {"installed", "visible", "executed", "followed", "unknown", "not_visible", "broken"}
PASSING = {"visible", "executed", "followed"}
NEEDS_REASON = {"unknown", "not_visible", "broken"}


def load_event_ids(path: Path) -> set[str]:
    """Event ids from a JSONL log. Lines that are not JSON objects are skipped."""
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and "event_id" in record:
            ids.add(str(record["event_id"]))
    return ids


def check_item(item: dict, event_ids: set[str] | None) -> tuple[list[str], str]:
    """Return (errors, effective_status) for one check."""
    errors: list[str] = []
    name = item.get("name", "<no name>")
    status = item.get("status")

    if status not in STATUSES:
        errors.append(f"{name}: unknown status {status!r}")
        return errors, "unknown"

    if status in NEEDS_REASON and not str(item.get("reason", "")).strip():
        errors.append(f"{name}: status {status} requires a non-empty 'reason'")

    evidence = item.get("evidence")
    if status == "installed" and not str(evidence or "").strip():
        errors.append(f"{name}: installed requires a file path in 'evidence'")
    if status == "visible" and not str(evidence or "").strip():
        errors.append(f"{name}: visible requires a quoted line or file name in 'evidence'")

    if status == "executed":
        event_id = evidence.get("event_id") if isinstance(evidence, dict) else None
        if not str(event_id or "").strip():
            errors.append(f"{name}: executed requires evidence.event_id (hook event)")
        elif event_ids is not None and str(event_id) not in event_ids:
            errors.append(f"{name}: event_id {event_id!r} not found in the events log")

    if status == "followed" and not str(item.get("behavioral_test", "")).strip():
        errors.append(
            f"{name}: followed requires 'behavioral_test'; a self-report gives at most visible"
        )

    return errors, status


def computed_overall(statuses: list[str]) -> str:
    if any(s in {"broken", "not_visible"} for s in statuses):
        return "fail"
    if any(s not in PASSING for s in statuses):
        return "partial"
    return "pass"


def validate(report: dict, event_ids: set[str] | None) -> list[str]:
    errors: list[str] = []
    if not str(report.get("session_id", "")).strip():
        errors.append("report: session_id is required")

    checks = report.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("report: 'checks' must be a non-empty list")
        return errors

    statuses: list[str] = []
    for item in checks:
        if not isinstance(item, dict):
            errors.append("report: every check must be an object")
            statuses.append("unknown")
            continue
        item_errors, status = check_item(item, event_ids)
        errors.extend(item_errors)
        statuses.append(status)

    expected = computed_overall(statuses)
    reported = report.get("overall")
    if reported != expected:
        errors.append(f"report: overall is {reported!r}, but the checks give {expected!r}")
    return errors


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        print("Usage: python validate_preflight.py report.json [--events events.jsonl]")
        return 1

    report_path = Path(args[0])
    event_ids: set[str] | None = None
    if "--events" in args:
        idx = args.index("--events")
        if idx + 1 >= len(args):
            print("ERROR: --events needs a path")
            return 1
        event_ids = load_event_ids(Path(args[idx + 1]))

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read report {report_path}: {exc}")
        return 1
    if not isinstance(report, dict):
        print("ERROR: report must be a JSON object")
        return 1

    errors = validate(report, event_ids)
    print(f"=== boyko-preflight validator: {report_path} ===")
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for err in errors:
            print(f"  - {err}")
        return 1
    print(f"OK. overall = {report.get('overall')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
