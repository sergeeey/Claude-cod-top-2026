#!/usr/bin/env python3
"""Check a triangle-audit claim-evidence record file (boyko-triangle-audit v1.1).

WHY: the audit must tie each vertex's evidence to ONE claim. Two rules are mechanical:
  1. source_span must be an exact substring of the cited artifact (verbatim, Kalaris
     ara-rigor-reviewer Critical Rule 1, read 2026-11-01). A paraphrase is not evidence.
  2. the "Независимая проверка" vertex must use a method_id different from the
     "Вычисления" vertex for the same claim. The same pipeline under another name is a
     repeat, not an independent check.

Input: JSON list of records:
  {"claim_id": "C1", "vertex": "Вычисления", "artifact": "relative/or/absolute/path",
   "source_span": "exact text", "method_id": "m-…", "supports": "the conclusion it backs"}

Usage: python check_spans.py records.json [--root <dir>]
Exit code: 0 if all records pass, 1 if any finding, 2 on usage or input error.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = ("claim_id", "vertex", "artifact", "source_span", "method_id", "supports")
COMPUTE = "Вычисления"
INDEPENDENT = "Независимая проверка"


def check(records: list[dict], root: Path) -> list[str]:
    findings: list[str] = []
    methods: dict[tuple[str, str], str] = {}

    for i, rec in enumerate(records, 1):
        if not isinstance(rec, dict):
            findings.append(f"record {i}: must be an object")
            continue
        missing = [k for k in REQUIRED if not str(rec.get(k, "")).strip()]
        if missing:
            findings.append(f"record {i}: missing or empty {', '.join(missing)}")
            continue

        claim = rec["claim_id"]
        path = Path(rec["artifact"])
        if not path.is_absolute():
            path = root / path
        if not path.is_file():
            findings.append(f"{claim}/{rec['vertex']}: artifact not found: {rec['artifact']}")
        else:
            text = path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")
            span = rec["source_span"].replace("\r\n", "\n")
            if span not in text:
                findings.append(
                    f"{claim}/{rec['vertex']}: source_span is not a verbatim substring of "
                    f"{rec['artifact']}"
                )

        methods[(claim, rec["vertex"])] = rec["method_id"]

    claims = {c for c, _ in methods}
    for claim in sorted(claims):
        compute_m = methods.get((claim, COMPUTE))
        indep_m = methods.get((claim, INDEPENDENT))
        if compute_m is not None and indep_m is not None and compute_m == indep_m:
            findings.append(
                f"{claim}: '{INDEPENDENT}' uses the same method_id as '{COMPUTE}' "
                f"({compute_m}): a repeat, not an independent check"
            )
    return findings


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        print("Usage: python check_spans.py records.json [--root <dir>]")
        return 2
    root = Path.cwd()
    if "--root" in args:
        idx = args.index("--root")
        if idx + 1 >= len(args):
            print("ERROR: --root needs a directory")
            return 2
        root = Path(args[idx + 1])
    try:
        records = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read records: {exc}")
        return 2
    if not isinstance(records, list):
        print("ERROR: records must be a JSON list")
        return 2

    findings = check(records, root)
    print(f"=== check_spans: {len(records)} record(s) ===")
    if findings:
        print(f"FINDINGS ({len(findings)}):")
        for f in findings:
            print(f"  - {f}")
        return 1
    print("OK. all spans verbatim, methods independent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
