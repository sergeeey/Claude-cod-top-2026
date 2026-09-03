#!/usr/bin/env python3
"""Mutation runner — inject errors, check if oracle catches them, compute MDR.

Usage:
    python scripts/run_mutations.py <experiment_dir> [--dry-run] [--mutation-id M-001]

    <experiment_dir>  path to an experiments/<id>/ folder with mutation_suite.yaml
    --dry-run         print planned mutations without applying them
    --mutation-id     run only a specific mutation (repeatable)

What it does:
  For each mutation in mutation_suite.yaml:
    1. Apply target_pattern → mutated_form in target_file (temporary edit)
    2. Run verification_command; capture exit code and stdout
    3. Detect: exit code != 0 OR output matches output_detection_pattern
    4. Restore target_file from git (git checkout -- <file>)
    5. Record result in mutation_suite.yaml results: section

MDR is then computed by mutation_tracker.py (PostToolUse hook) when
mutation_suite.yaml is written.

Safety:
  - Restoration uses `git checkout -- <file>` so the file is always reverted.
  - On any error during restore, an explicit warning is printed and the process
    exits non-zero to prevent a corrupted state from going unnoticed.
  - Only files inside the repo root are mutated (checked against git root).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("Not inside a git repository")
    return Path(result.stdout.strip())


def _load_suite(suite_path: Path) -> dict:
    """Minimal YAML parser for mutation_suite.yaml structure."""
    content = suite_path.read_text(encoding="utf-8")

    def _field(name: str) -> str | None:
        m = re.search(rf"^{re.escape(name)}:\s*(.+)$", content, re.MULTILINE)
        return m.group(1).strip() if m else None

    verification_command = _field("verification_command")
    output_pattern_raw = _field("output_detection_pattern")
    output_pattern = (
        output_pattern_raw.strip("\"'")
        if output_pattern_raw and output_pattern_raw.lower() not in ("null", "~", "")
        else None
    )

    # Parse mutations list
    mutations: list[dict] = []
    mut_block = re.search(r"^mutations:\s*\n((?:(?:  |\t).*\n?)*)", content, re.MULTILINE)
    if mut_block:
        block = mut_block.group(1)
        cur: dict = {}
        for line in block.splitlines():
            id_m = re.match(r"\s+-\s+id:\s+(\S+)", line)
            if id_m:
                if cur:
                    mutations.append(cur)
                cur = {"id": id_m.group(1)}
                continue
            for key in ("type", "description", "target_file", "target_pattern", "mutated_form"):
                km = re.match(rf"\s+{re.escape(key)}:\s+(.*)", line)
                if km and cur is not None:
                    cur[key] = km.group(1).strip().strip("\"'")
            de_m = re.match(r"\s+detection_expected:\s+(true|false)", line, re.IGNORECASE)
            if de_m and cur is not None:
                cur["detection_expected"] = de_m.group(1).lower() == "true"
        if cur:
            mutations.append(cur)

    return {
        "verification_command": verification_command,
        "output_pattern": output_pattern,
        "mutations": mutations,
    }


def _apply_mutation(target: Path, pattern: str, replacement: str) -> bool:
    """Replace first occurrence of pattern in target. Returns True on success."""
    original = target.read_text(encoding="utf-8")
    if pattern not in original:
        print(f"  ⚠️  Pattern not found in {target}: {pattern!r}", file=sys.stderr)
        return False
    mutated = original.replace(pattern, replacement, 1)
    target.write_text(mutated, encoding="utf-8")
    return True


def _restore(target: Path, root: Path) -> None:
    """Restore target from git. Exits non-zero on failure."""
    rel = target.relative_to(root)
    result = subprocess.run(
        ["git", "checkout", "--", str(rel)],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"\n⛔  FAILED TO RESTORE {target}.\n"
            "The file is in a mutated state. Run:\n"
            f"  git checkout -- {rel}\n"
            "manually before continuing.",
            file=sys.stderr,
        )
        sys.exit(3)


def _run_oracle(command: str, cwd: Path, output_pattern: str | None) -> tuple[bool, int, str]:
    """Run verification_command. Return (detected, exit_code, stdout)."""
    result = subprocess.run(
        command,
        shell=True,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=120,
    )
    stdout = result.stdout + result.stderr
    detected_by_exit = result.returncode != 0
    detected_by_pattern = False
    if output_pattern:
        detected_by_pattern = bool(re.search(output_pattern, stdout))
    detected = detected_by_exit or detected_by_pattern
    return detected, result.returncode, stdout[:1000]  # truncate for YAML safety


def _update_results(suite_path: Path, new_results: list[dict]) -> None:
    """Write results back to mutation_suite.yaml results: section."""
    content = suite_path.read_text(encoding="utf-8")

    lines = ["results:"]
    for r in new_results:
        lines.append(f"  - id: {r['id']}")
        lines.append(f"    injected: {str(r.get('injected', True)).lower()}")
        detected = r.get("detected")
        lines.append(f"    detected: {str(detected).lower() if detected is not None else 'null'}")
        lines.append(f"    exit_code: {r.get('exit_code', 'null')}")
        notes = str(r.get("notes", "")).replace('"', "'")[:200]
        lines.append(f'    notes: "{notes}"')
    new_results_block = "\n".join(lines)

    updated = re.sub(
        r"^results:.*$(?:\n(?:  .*)?)*",
        new_results_block,
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if updated == content:
        updated = content.rstrip() + "\n\n" + new_results_block + "\n"
    suite_path.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run mutation tests for an experiment.")
    parser.add_argument("experiment_dir", help="Path to experiments/<id>/ folder")
    parser.add_argument("--dry-run", action="store_true", help="Print plan, no edits")
    parser.add_argument(
        "--mutation-id",
        action="append",
        dest="mutation_ids",
        metavar="ID",
        help="Run only this mutation ID (repeatable)",
    )
    args = parser.parse_args()

    exp_dir = Path(args.experiment_dir).resolve()
    suite_path = exp_dir / "mutation_suite.yaml"
    if not suite_path.exists():
        print(f"❌ mutation_suite.yaml not found in {exp_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        root = _repo_root()
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)

    suite = _load_suite(suite_path)
    command = suite.get("verification_command", "")
    if not command or "<paste exact command" in command:
        print("❌ verification_command not set in mutation_suite.yaml", file=sys.stderr)
        sys.exit(1)

    mutations = suite["mutations"]
    if args.mutation_ids:
        mutations = [m for m in mutations if m.get("id") in args.mutation_ids]
    if not mutations:
        print("No mutations to run.")
        sys.exit(0)

    print(f"Oracle command: {command}")
    print(f"Mutations to run: {len(mutations)}")

    if args.dry_run:
        for m in mutations:
            print(f"  [{m.get('id')}] {m.get('type')}: {m.get('description')}")
            print(f"    target: {m.get('target_file')} :: {m.get('target_pattern')!r}")
            print(f"    → {m.get('mutated_form')!r}")
            print(f"    detection_expected: {m.get('detection_expected')}")
        print("(dry-run — no files modified)")
        sys.exit(0)

    results: list[dict] = []
    for m in mutations:
        mid = m.get("id", "?")
        tfile_rel = m.get("target_file", "")
        target = (root / tfile_rel).resolve()

        # Safety: must be inside repo
        try:
            target.relative_to(root)
        except ValueError:
            print(f"  ❌ [{mid}] target outside repo: {target}", file=sys.stderr)
            results.append(
                {
                    "id": mid,
                    "injected": False,
                    "detected": None,
                    "exit_code": None,
                    "notes": "target outside repo",
                }
            )
            continue

        print(f"\n[{mid}] {m.get('type')}: {m.get('description')}")
        applied = _apply_mutation(
            target,
            m.get("target_pattern", ""),
            m.get("mutated_form", ""),
        )
        if not applied:
            results.append(
                {
                    "id": mid,
                    "injected": False,
                    "detected": None,
                    "exit_code": None,
                    "notes": "pattern not found",
                }
            )
            continue

        print("  Mutation applied → running oracle…")
        try:
            detected, exit_code, stdout_preview = _run_oracle(
                command, root, suite.get("output_pattern")
            )
        except subprocess.TimeoutExpired:
            detected, exit_code, stdout_preview = False, -1, "TIMEOUT"
        finally:
            _restore(target, root)

        # WHY default False, not True: same decision as hooks/mutation_tracker.py's
        # _is_counted() -- a mutation entry missing/unparseable detection_expected
        # is not "flagged true" (falsification-pilot 20260824 / sci-code-audit
        # 2026-08-26 follow-up, which found this exact site still had the old
        # default after the first fix only touched hooks/mutation_tracker.py).
        expected = m.get("detection_expected", False)
        status = (
            "✓ CAUGHT" if detected else ("✗ MISSED (expected)" if expected else "– not expected")
        )
        print(f"  exit={exit_code}  detected={detected}  {status}")

        results.append(
            {
                "id": mid,
                "injected": True,
                "detected": detected,
                "exit_code": exit_code,
                "notes": stdout_preview.splitlines()[0] if stdout_preview else "",
            }
        )

    _update_results(suite_path, results)
    total = len(results)
    caught = sum(1 for r in results if r.get("detected"))
    print(f"\n✅ Done: {caught}/{total} mutations detected. mutation_suite.yaml updated.")
    print("   MDR will be computed by mutation_tracker.py hook on next Write.")


if __name__ == "__main__":
    main()
