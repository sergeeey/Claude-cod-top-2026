#!/usr/bin/env python3
"""
Consistency Audit — Independent FL experiment result checker.

Prevents validation theater by cross-checking claimed metrics vs actual evidence.

Usage:
  python scripts/consistency_audit.py experiments/20260515-foo/
  python scripts/consistency_audit.py experiments/20260515-foo/ --strict

Exit codes:
  0 = clean (no warnings, no errors)
  1 = errors found  (always exits 1)
  2 = warnings only (exits 2 normally; exits 1 with --strict)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ─────────────────────────────────────────────
# ANSI colours
# ─────────────────────────────────────────────

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"


def _c(text: str, code: str) -> str:
    """Apply ANSI colour when stdout is a TTY."""
    if sys.stdout.isatty():
        return f"{code}{text}{RESET}"
    return text


# ─────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────

SEVERITY_ERROR = "error"
SEVERITY_WARN = "warning"
SEVERITY_OK = "ok"


@dataclass
class Finding:
    """Single check finding."""

    check_id: int
    check_name: str
    severity: str  # "ok" | "warning" | "error"
    message: str
    detail: str = ""


@dataclass
class AuditReport:
    """Full audit result for one experiment directory."""

    exp_dir: Path
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_WARN]

    @property
    def oks(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_OK]


# ─────────────────────────────────────────────
# Markdown helpers (regex-only, no deps)
# ─────────────────────────────────────────────


def _read(path: Path) -> str | None:
    """Read file text; return None if missing."""
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_markdown_table_rows(text: str) -> list[dict[str, str]]:
    """
    Parse first markdown table found in text.

    Returns list of dicts keyed by lowercased header names.
    WHY: result_summary.md stores metrics in a markdown table;
    regex is sufficient and avoids markdown-parser dependency.
    """
    # Find table: header row, separator row, data rows
    table_pattern = re.compile(
        r"^\|(.+)\|\s*\n"  # header
        r"\|[-| :]+\|\s*\n"  # separator
        r"((?:\|.+\|\s*\n?)+)",  # data rows
        re.MULTILINE,
    )
    m = table_pattern.search(text)
    if not m:
        return []

    headers = [h.strip().lower() for h in m.group(1).split("|") if h.strip()]
    rows_text = m.group(2)
    rows: list[dict[str, str]] = []

    for line in rows_text.strip().splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < len(headers):
            continue
        rows.append(dict(zip(headers, cells, strict=False)))

    return rows


def _extract_checked_verdict(text: str, options: list[str]) -> str | None:
    """
    Find the first checked checkbox [x] or [X] among a list of verdict options.

    Pattern: **[x] PROMOTE** or **[X] REPEAT** etc.
    Returns the matched option string (uppercased), or None if nothing checked.
    """
    for opt in options:
        # Match [x] or [X] followed by optional ** and the option text
        pattern = re.compile(
            r"\[([xX])\]\s*\*{0,2}" + re.escape(opt) + r"\b",
            re.IGNORECASE,
        )
        if pattern.search(text):
            return opt.upper()
    return None


def _extract_section(text: str, section_heading: str) -> str:
    """
    Extract content of a named markdown section (## Heading) until next ## heading.
    """
    pattern = re.compile(
        r"^##\s+" + re.escape(section_heading) + r"\s*\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def _count_checkboxes(text: str) -> tuple[int, int]:
    """Count (checked, total) checkboxes in text."""
    all_boxes = re.findall(r"\[[ xX]\]", text)
    checked = re.findall(r"\[[xX]\]", text)
    return len(checked), len(all_boxes)


def _count_evidence_sources(text: str) -> int:
    """
    Count evidence sources: URLs, local file paths, dataset names.

    WHY: integrity rules say HIGH confidence requires ≥2 independent sources.
    We detect: http(s) URLs, local paths with extensions, and quoted dataset names.
    """
    urls = re.findall(r"https?://\S+", text)
    # file paths: word chars + / or \ + word chars + dot + ext
    file_paths = re.findall(r"\b[\w./\\-]+\.\w{2,5}\b", text)
    # filter noise (remove common markdown artifacts)
    file_paths = [
        p
        for p in file_paths
        if not p.endswith(".md") and not p.endswith(".py") and len(p) > 6 and "/" in p or "\\" in p
    ]
    return len(urls) + len(file_paths)


_SYNTHETIC_PATTERNS: list[re.Pattern] = [
    re.compile(r"create_synthetic", re.IGNORECASE),
    re.compile(r"mock_data", re.IGNORECASE),
    re.compile(r"np\.random\.seed", re.IGNORECASE),
    re.compile(r"\[VERIFIED-SYNTHETIC\]"),
    re.compile(r"generate_fake", re.IGNORECASE),
    re.compile(r"fake_dataset", re.IGNORECASE),
]


def _find_synthetic_patterns(text: str) -> list[str]:
    """Return list of matched synthetic data pattern strings."""
    found: list[str] = []
    for pat in _SYNTHETIC_PATTERNS:
        m = pat.search(text)
        if m:
            found.append(m.group(0))
    return found


CONFIDENCE_LEVELS = ["HIGH", "MEDIUM", "LOW"]
VERDICT_OPTIONS = ["PROMOTE", "REPEAT", "REJECT", "ARCHIVE"]


def _extract_confidence(text: str) -> str | None:
    """Find checked confidence level checkbox in text."""
    return _extract_checked_verdict(text, CONFIDENCE_LEVELS)


# ─────────────────────────────────────────────
# Checks
# ─────────────────────────────────────────────


def check_metrics_vs_run_json(exp_dir: Path) -> Finding:
    """
    Check 1: result_summary.md metric table vs metrics/run.json.

    WHY: the primary guard against "claimed X in text but actual result was Y"
    (see ARCHCODE manuscript incident where text showed 0.98 vs figures 0.79).
    """
    cid = 1
    name = "result_summary ↔ metrics/run.json"

    summary_path = exp_dir / "result_summary.md"
    summary_text = _read(summary_path)
    if summary_text is None:
        return Finding(cid, name, SEVERITY_WARN, "result_summary.md not found — cannot check")

    rows = _extract_markdown_table_rows(summary_text)
    if not rows:
        return Finding(cid, name, SEVERITY_WARN, "No metrics table found in result_summary.md")

    run_json_path = exp_dir / "metrics" / "run.json"
    if not run_json_path.exists():
        return Finding(
            cid,
            name,
            SEVERITY_WARN,
            "metrics/run.json not found — cannot verify metric claims",
            detail="Create metrics/run.json with actual run output to enable this check",
        )

    try:
        run_data: dict = json.loads(run_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return Finding(cid, name, SEVERITY_ERROR, f"metrics/run.json is invalid JSON: {exc}")

    mismatches: list[str] = []
    checked: list[str] = []

    for row in rows:
        metric_name = row.get("metric", "")
        result_val_str = row.get("result", "")
        if not metric_name or not result_val_str:
            continue

        # Try to extract float from result cell
        num_match = re.search(r"[-+]?\d*\.?\d+", result_val_str)
        if not num_match:
            continue
        claimed = float(num_match.group())

        # Find matching key in run.json (case-insensitive, ignore punctuation)
        clean_name = re.sub(r"[^a-z0-9]", "_", metric_name.lower())
        actual: float | None = None
        for key, val in run_data.items():
            clean_key = re.sub(r"[^a-z0-9]", "_", key.lower())
            if clean_name in clean_key or clean_key in clean_name:
                try:
                    actual = float(val)
                except (ValueError, TypeError):
                    pass
                break

        if actual is None:
            continue

        delta_pct = abs(claimed - actual) / max(abs(actual), 1e-9) * 100
        if delta_pct > 5.0:
            mismatches.append(
                f"{metric_name}: claimed={claimed:.4f}, actual={actual:.4f} "
                f"(Δ={delta_pct:.1f}%)"
            )
        else:
            checked.append(metric_name)

    if mismatches:
        return Finding(
            cid,
            name,
            SEVERITY_ERROR,
            f"{len(mismatches)} metric mismatch(es) > 5%",
            detail="\n    ".join(mismatches),
        )
    if checked:
        return Finding(
            cid, name, SEVERITY_OK, f"All {len(checked)} checked metric(s) within 5% tolerance"
        )
    return Finding(
        cid,
        name,
        SEVERITY_WARN,
        "No matchable metrics found between result_summary.md and run.json",
    )


def check_verdict_consistency(exp_dir: Path) -> Finding:
    """
    Check 2: decision.md verdict matches result_summary.md classification.

    WHY: copy-paste errors between these two files are a common source of
    inconsistency in experiment records.
    """
    cid = 2
    name = "decision.md ↔ result_summary.md classification"

    decision_text = _read(exp_dir / "decision.md")
    summary_text = _read(exp_dir / "result_summary.md")

    if decision_text is None:
        return Finding(cid, name, SEVERITY_WARN, "decision.md not found")
    if summary_text is None:
        return Finding(cid, name, SEVERITY_WARN, "result_summary.md not found")

    decision_verdict = _extract_checked_verdict(decision_text, VERDICT_OPTIONS)
    summary_verdict = _extract_checked_verdict(summary_text, VERDICT_OPTIONS)

    if decision_verdict is None and summary_verdict is None:
        return Finding(cid, name, SEVERITY_WARN, "No checked verdict found in either file")
    if decision_verdict is None:
        return Finding(
            cid,
            name,
            SEVERITY_WARN,
            f"decision.md has no checked verdict (result_summary says: {summary_verdict})",
        )
    if summary_verdict is None:
        return Finding(
            cid,
            name,
            SEVERITY_WARN,
            f"result_summary.md has no checked verdict (decision.md says: {decision_verdict})",
        )
    if decision_verdict != summary_verdict:
        return Finding(
            cid,
            name,
            SEVERITY_ERROR,
            f"Verdict mismatch: decision.md={decision_verdict}, "
            f"result_summary.md={summary_verdict}",
        )

    return Finding(cid, name, SEVERITY_OK, f"Both show: {decision_verdict}")


def check_confidence_vs_sources(exp_dir: Path) -> Finding:
    """
    Check 3: claimed confidence level is backed by sufficient evidence sources.

    Rules: HIGH ≥2 sources, MEDIUM ≥1, LOW = no requirement.
    WHY: prevents HIGH confidence claims based on a single synthetic run.
    """
    cid = 3
    name = "Confidence vs evidence sources"

    summary_text = _read(exp_dir / "result_summary.md")
    if summary_text is None:
        return Finding(cid, name, SEVERITY_WARN, "result_summary.md not found")

    confidence = _extract_confidence(summary_text)
    if confidence is None:
        return Finding(
            cid, name, SEVERITY_WARN, "No checked confidence level found in result_summary.md"
        )

    source_count = _count_evidence_sources(summary_text)

    required: dict[str, int] = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
    minimum = required.get(confidence, 0)

    if source_count < minimum:
        return Finding(
            cid,
            name,
            SEVERITY_WARN,
            f"Confidence={confidence} but only {source_count} source(s) cited "
            f"(minimum: {minimum})",
            detail="Add URLs, file paths, or dataset names as evidence sources",
        )

    return Finding(
        cid,
        name,
        SEVERITY_OK,
        f"Confidence={confidence}, {source_count} source(s) cited (minimum: {minimum})",
    )


def check_success_criteria_coverage(exp_dir: Path) -> Finding:
    """
    Check 4: success criteria in claim.md are addressed in result_summary.md.

    WHY: unchecked success criteria boxes indicate the experiment did not
    fully answer its own question — a sign of incomplete or rushed reporting.
    """
    cid = 4
    name = "Success criteria coverage"

    claim_text = _read(exp_dir / "claim.md")
    summary_text = _read(exp_dir / "result_summary.md")

    if claim_text is None:
        return Finding(cid, name, SEVERITY_WARN, "claim.md not found")
    if summary_text is None:
        return Finding(cid, name, SEVERITY_WARN, "result_summary.md not found")

    # Extract Success Criteria section from claim.md
    criteria_section = _extract_section(claim_text, "Success Criteria")
    if not criteria_section:
        return Finding(cid, name, SEVERITY_WARN, "No '## Success Criteria' section in claim.md")

    checked, total = _count_checkboxes(criteria_section)

    if total == 0:
        return Finding(cid, name, SEVERITY_WARN, "No checkboxes found in Success Criteria section")

    unchecked = total - checked
    pct_unchecked = unchecked / total

    if pct_unchecked > 0.50:
        return Finding(
            cid,
            name,
            SEVERITY_WARN,
            f"Only {checked}/{total} success criteria addressed "
            f"({int(pct_unchecked*100)}% unchecked)",
            detail="Mark criteria as [x] in claim.md as they are validated",
        )

    return Finding(cid, name, SEVERITY_OK, f"{checked}/{total} criteria addressed")


def check_synthetic_data(exp_dir: Path) -> Finding:
    """
    Check 5: detect synthetic data patterns combined with HIGH confidence claim.

    WHY: [SYNTHETIC-OVERCLAIM] is the primary anti-pattern we guard against —
    see ТОП-10 theater postmortem (2026-05-01).
    """
    cid = 5
    name = "Synthetic data detection"

    summary_text = _read(exp_dir / "result_summary.md")
    controls_text = _read(exp_dir / "controls.md") or ""

    combined = (summary_text or "") + "\n" + controls_text

    patterns_found = _find_synthetic_patterns(combined)

    if not patterns_found:
        return Finding(cid, name, SEVERITY_OK, "No synthetic data patterns found")

    # Check if confidence is HIGH
    confidence = _extract_confidence(summary_text or "") if summary_text else None
    if confidence == "HIGH":
        return Finding(
            cid,
            name,
            SEVERITY_ERROR,
            "[SYNTHETIC-OVERCLAIM] Synthetic data detected with HIGH confidence claim",
            detail=f"Patterns found: {', '.join(patterns_found)}\n"
            "    Downgrade confidence to LOW or replace with real data",
        )

    return Finding(
        cid,
        name,
        SEVERITY_WARN,
        f"Synthetic data patterns found: {', '.join(patterns_found)}",
        detail="Ensure confidence level reflects synthetic-only validation",
    )


# ─────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────

ALL_CHECKS = [
    check_metrics_vs_run_json,
    check_verdict_consistency,
    check_confidence_vs_sources,
    check_success_criteria_coverage,
    check_synthetic_data,
]

CHECK_NAMES = [
    "result_summary ↔ metrics/run.json",
    "decision.md ↔ result_summary.md classification",
    "Confidence vs evidence sources",
    "Success criteria coverage",
    "Synthetic data detection",
]


def run_audit(exp_dir: Path) -> AuditReport:
    """Execute all checks against an experiment directory."""
    report = AuditReport(exp_dir=exp_dir)
    for check_fn in ALL_CHECKS:
        finding = check_fn(exp_dir)
        report.findings.append(finding)
    return report


# ─────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────


def _finding_icon(severity: str) -> str:
    if severity == SEVERITY_OK:
        return _c("✅", GREEN)
    if severity == SEVERITY_WARN:
        return _c("⚠️ ", YELLOW)
    return _c("❌", RED)


def render_audit_report(report: AuditReport) -> str:
    """Build human-readable audit report."""
    sep = "═" * 54
    lines: list[str] = []
    title = f"═══ Consistency Audit: {report.exp_dir} "
    lines.append(_c(title + sep[: max(0, 72 - len(title))], BOLD))

    for f in report.findings:
        lines.append("")
        lines.append(f"[{f.check_id}] {f.check_name}")
        icon = _finding_icon(f.severity)
        lines.append(f"    {icon} {f.message}")
        if f.detail:
            for dl in f.detail.splitlines():
                lines.append(f"    {_c(dl, DIM)}")

    lines.append("")
    lines.append("─" * 56)

    n_warn = len(report.warnings)
    n_err = len(report.errors)
    summary = f"Summary: {n_warn} warning(s), {n_err} error(s)"

    if n_err > 0:
        status = _c("❌ FAILED — errors must be resolved", RED)
    elif n_warn > 0:
        status = _c("⚠️  REVIEW NEEDED", YELLOW)
    else:
        status = _c("✅ CLEAN — all checks passed", GREEN)

    lines.append(summary)
    lines.append(f"Status: {status}")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Consistency Audit — FL experiment result cross-checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "experiment_dir",
        type=Path,
        help="Path to experiment directory (e.g. experiments/20260515-foo/)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (exit 1 on any warning)",
    )
    return parser


def main() -> None:
    """Main entry point."""
    parser = _build_arg_parser()
    args = parser.parse_args()

    exp_dir: Path = args.experiment_dir
    if not exp_dir.exists():
        print(f"Error: directory not found — {exp_dir}", file=sys.stderr)
        sys.exit(1)
    if not exp_dir.is_dir():
        print(f"Error: {exp_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    report = run_audit(exp_dir)
    print(render_audit_report(report))

    n_err = len(report.errors)
    n_warn = len(report.warnings)

    if n_err > 0:
        sys.exit(1)
    if n_warn > 0:
        # WHY: separate exit code 2 allows CI to distinguish "needs review"
        # from "hard failure" without --strict; with --strict both → exit 1
        sys.exit(1 if args.strict else 2)
    sys.exit(0)


if __name__ == "__main__":
    main()
