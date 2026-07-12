#!/usr/bin/env python3
"""Drive the REAL validation_theater_guard.py hook against 3 scenarios.

This is not a mock. It builds the exact PostToolUse JSON payload Claude Code
sends, pipes it into hooks/validation_theater_guard.py as a subprocess, and
reports the real exit code (1 = flagged -- a strong post-hoc signal, not a
preventive block; PostToolUse fires after the Bash call already ran -- 0 =
allowed) plus the hook's stderr.

WHY a subprocess against the real hook: a demo that simulated the guard would
itself be validation theater. This runs the shipped guard, unmodified.

Run it: `python run_trap.py`  (no arguments, no dependencies beyond stdlib)
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
HOOKS = HERE.parent.parent / "hooks"
GUARD = HOOKS / "validation_theater_guard.py"


def run_guard(output: str) -> tuple[int, str]:
    """Feed a Bash PostToolUse payload to the real guard. Return (exit_code, stderr)."""
    payload = {"tool_name": "Bash", "tool_response": {"output": output}}
    env = dict(os.environ)
    # WHY: the guard skips (exit 0) when CLAUDE_INVOKED_BY is set, to avoid
    # recursion inside subagents. We must UNSET it so the guard actually runs.
    env.pop("CLAUDE_INVOKED_BY", None)
    # WHY: the guard does `from utils import ...` — utils lives in hooks/.
    env["PYTHONPATH"] = str(HOOKS) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, (proc.stderr or "").strip()


# WHY: three scenarios chosen to show the guard flags THEATER, not perfection.
SCENARIOS = [
    (
        "1. THEATER",
        "Agent claims success on synthetic data",
        "Classifier eval on synthetic_cases: 6 cases\n"
        "F1=1.000  precision=1.000  recall=1.000\n"
        "All 6 cases passed. [VERIFIED-SYNTHETIC]",
        1,  # expected: flagged (exit 1)
    ),
    (
        "2. HONEST (real data)",
        "Same classifier, re-run on real reviews — messy score, real source",
        "Evaluated on 2000 real reviews from https://example-dataset.org/reviews.csv\n"
        "F1=0.831  precision=0.847  recall=0.816  [VERIFIED-REAL]",
        0,  # expected: allowed
    ),
    (
        "3. NUANCE (perfect BUT real)",
        "Even F1=1.000 passes IF the source is real — guard targets theater, not perfection",
        "Evaluated on external benchmark https://benchmark.org/gold.csv\n"
        "F1=1.000 on 50 held-out real samples. [VERIFIED-REAL]",
        0,  # expected: allowed
    ),
]


def main() -> int:
    if not GUARD.exists():
        print(f"ERROR: guard not found at {GUARD}", file=sys.stderr)
        return 2

    print("=" * 70)
    print("Validation Theater Trap — driving the REAL guard")
    print(f"Guard: {GUARD}")
    print("=" * 70)

    all_ok = True
    for name, desc, output, expected_code in SCENARIOS:
        code, stderr = run_guard(output)
        verdict = "FLAGGED" if code == 1 else "allowed"
        ok = code == expected_code
        all_ok = all_ok and ok
        mark = "OK" if ok else "MISMATCH"
        print(f"\n[{name}] {desc}")
        print(f"  exit={code} -> {verdict}   (expected {expected_code}) [{mark}]")
        if stderr:
            for line in stderr.splitlines():
                print(f"    | {line}")

    print("\n" + "=" * 70)
    if all_ok:
        print("RESULT: guard behaved as expected on all 3 scenarios.")
        print("Theater FLAGGED. Honest claims (real source) allowed — even at F1=1.000.")
    else:
        print("RESULT: at least one scenario did not match. The guard may have changed.")
    print("=" * 70)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
