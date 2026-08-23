#!/usr/bin/env python3
"""PostToolUse hook: compute Mutation Detection Rate (MDR) from mutation_suite.yaml.

WHY: MDR closes the ELAI axis A (Adversarial Robustness) gap. No-collapse tests
in controls.md describe *what* to test; mutation_suite.yaml records *whether the
oracle actually caught injected errors*. Without MDR the oracle's discriminative
power is unknown — a verification that accepts mutated code is validation theater.

Fires on: PostToolUse(Write|Edit) matching **/experiments/**/mutation_suite.yaml

MDR = actually_detected / expected_detected
  where expected_detected = mutations with detection_expected: true

Thresholds:
  PASS  (≥ 0.80) — oracle is discriminating; proceed
  WARN  (0.50–0.79) — partial discrimination; document blind spots before PROMOTE
  FAIL  (< 0.50) — oracle cannot distinguish correct from mutated; do NOT promote

Enforcement: soft nudge (additionalContext). Failure is recorded in mdr.verdict
and read by promotion_gate_guard as a future integration point.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib.runtime import emit_hook_result

_MSG_HOOK = "mutation-tracker"
_MDR_PASS = 0.80
_MDR_WARN = 0.50


# ---------------------------------------------------------------------------
# Pure parsing / computation (testable without I/O)
# ---------------------------------------------------------------------------


def _parse_results(content: str) -> tuple[list[dict], list[dict]]:
    """Extract mutations and results from YAML content.

    WHY minimal parser instead of PyYAML: hooks must work without installed
    packages. The YAML produced by run_mutations.py follows a predictable
    flat structure that regex can handle reliably.

    Returns:
        mutations: list of {id, detection_expected}
        results:   list of {id, detected}
    """
    mutations: list[dict] = []
    results: list[dict] = []

    # Parse mutations block — id + detection_expected fields
    mut_block_m = re.search(r"^mutations:\s*\n((?:(?:  |\t).*\n?)*)", content, re.MULTILINE)
    if mut_block_m:
        block = mut_block_m.group(1)
        current: dict = {}
        for line in block.splitlines():
            id_m = re.match(r"\s+-\s+id:\s+(\S+)", line)
            if id_m:
                if current:
                    mutations.append(current)
                current = {"id": id_m.group(1)}
                continue
            de_m = re.match(r"\s+detection_expected:\s+(true|false)", line, re.IGNORECASE)
            if de_m and current:
                current["detection_expected"] = de_m.group(1).lower() == "true"
        if current:
            mutations.append(current)

    # Parse results block — id + detected fields
    res_block_m = re.search(r"^results:\s*\n((?:(?:  |\t).*\n?)*)", content, re.MULTILINE)
    if res_block_m:
        block = res_block_m.group(1)
        current = {}
        for line in block.splitlines():
            id_m = re.match(r"\s+-\s+id:\s+(\S+)", line)
            if id_m:
                if current:
                    results.append(current)
                current = {"id": id_m.group(1)}
                continue
            det_m = re.match(r"\s+detected:\s+(true|false)", line, re.IGNORECASE)
            if det_m and current:
                current["detected"] = det_m.group(1).lower() == "true"
        if current:
            results.append(current)

    return mutations, results


def compute_mdr(
    mutations: list[dict],
    results: list[dict],
) -> tuple[float | None, str, list[str]]:
    """Return (rate, verdict, blind_spots).

    rate is None when no results are recorded yet.
    blind_spots: mutation IDs where detection_expected=True but detected=False.
    """
    if not results:
        return None, "PENDING", []

    det_map = {r["id"]: r.get("detected") for r in results if "id" in r}
    expected = [m for m in mutations if m.get("detection_expected", True)]
    if not expected:
        return None, "NO_EXPECTED_DETECTIONS", []

    blind_spots: list[str] = []
    actually_detected = 0
    for m in expected:
        detected = det_map.get(m["id"])
        if detected is True:
            actually_detected += 1
        elif detected is False:
            blind_spots.append(m["id"])
        # None → result not yet recorded, skip

    scored = len(expected) - sum(1 for m in expected if det_map.get(m["id"]) is None)
    if scored == 0:
        return None, "PENDING", []

    rate = actually_detected / scored
    if rate >= _MDR_PASS:
        verdict = "PASS"
    elif rate >= _MDR_WARN:
        verdict = "WARN"
    else:
        verdict = "FAIL"

    return round(rate, 3), verdict, blind_spots


# ---------------------------------------------------------------------------
# YAML write-back helpers
# ---------------------------------------------------------------------------


def _yaml_list_str(items: list[str]) -> str:
    if not items:
        return "[]"
    return "[" + ", ".join(items) + "]"


def _update_mdr_in_content(
    content: str,
    mutations: list[dict],
    results: list[dict],
    rate: float | None,
    verdict: str,
    blind_spots: list[str],
) -> str:
    """Rewrite the mdr: block at the bottom of mutation_suite.yaml."""
    expected = [m for m in mutations if m.get("detection_expected", True)]
    new_block = (
        f"mdr:\n"
        f"  total_mutations: {len(mutations)}\n"
        f"  expected_detected: {len(expected)}\n"
        f"  actually_detected: {sum(1 for r in results if r.get('detected'))}\n"
        f"  rate: {rate if rate is not None else 'null'}\n"
        f"  verdict: {verdict}\n"
        f"  blind_spots: {_yaml_list_str(blind_spots)}\n"
    )
    # Replace existing mdr block or append
    updated = re.sub(
        r"^mdr:.*$(?:\n(?:  .*)?)*",
        new_block.rstrip(),
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if updated == content:
        updated = content.rstrip() + "\n\n" + new_block
    return updated


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------


def _is_mutation_suite(file_path: str) -> bool:
    p = Path(file_path)
    return p.name == "mutation_suite.yaml" and "experiments" in set(p.parts)


def _is_template(content: str) -> bool:
    return "<YYYYMMDD-short-slug>" in content or "<paste exact command here>" in content


def main() -> None:
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    if data.get("tool_name", "") not in ("Write", "Edit"):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path or not _is_mutation_suite(file_path):
        sys.exit(0)

    content = tool_input.get("content") or ""
    if not content:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            sys.exit(0)

    if _is_template(content):
        sys.exit(0)

    mutations, results = _parse_results(content)
    rate, verdict, blind_spots = compute_mdr(mutations, results)

    # Write MDR back to file
    try:
        updated = _update_mdr_in_content(content, mutations, results, rate, verdict, blind_spots)
        Path(file_path).write_text(updated, encoding="utf-8")
    except OSError:
        pass

    if verdict == "PENDING" or rate is None:
        sys.exit(0)  # no results yet — nothing to warn about

    # Build message
    rate_pct = f"{rate:.0%}" if rate is not None else "?"
    lines = [f"[{_MSG_HOOK}] MDR: {rate_pct} → verdict: {verdict}"]

    if blind_spots:
        lines.append(f"  Blind spots (expected detection, not caught): {blind_spots}")

    if verdict == "FAIL":
        lines.append(
            "  ⛔ FAIL: oracle cannot reliably distinguish correct from mutated. "
            "Do NOT use this oracle as evidence for PROMOTE. "
            "Fix the verifier or reduce claims to what the oracle actually tests."
        )
    elif verdict == "WARN":
        lines.append(
            "  ⚠️  WARN: oracle catches some mutations but has blind spots. "
            "Document blind spots in caveats.md before promoting."
        )
    else:
        lines.append("  ✓ PASS: oracle is discriminating (MDR ≥ 80%).")

    msg = "\n".join(lines)
    emit_hook_result(_MSG_HOOK, msg)


if __name__ == "__main__":
    main()
