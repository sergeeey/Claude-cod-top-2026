#!/usr/bin/env python3
"""FL (Falsification Ladder) experiment folder validator.

Checks that an experiment directory contains the required artifact files
for its declared tier (micro | standard | full) and that files are
non-empty and placeholder-free.

Usage:
    python scripts/validate_experiment.py experiments/20260515-foo/
    python scripts/validate_experiment.py experiments/20260515-foo/ --sha256
    python scripts/validate_experiment.py experiments/20260515-foo/ --tier full
    python scripts/validate_experiment.py --list
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import NamedTuple

# WHY: no external deps — runs in any env, no pip install needed.
# ANSI codes inline (not colorama) keeps the file self-contained.

# ── ANSI colours ──────────────────────────────────────────────────────────────
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def _green(s: str) -> str:
    return f"{_GREEN}{s}{_RESET}"


def _red(s: str) -> str:
    return f"{_RED}{s}{_RESET}"


def _yellow(s: str) -> str:
    return f"{_YELLOW}{s}{_RESET}"


def _bold(s: str) -> str:
    return f"{_BOLD}{s}{_RESET}"


# ── Tier definitions ───────────────────────────────────────────────────────────
# WHY: full-ladder list matches falsification-ladder.md Step 0-10 artifacts.
REQUIRED_FILES: dict[str, list[str]] = {
    "micro": [],  # no folder required — just a PR inline block
    "standard": ["claim.md", "controls.md", "decision.md"],
    "full": [
        "claim.md",
        "experiment.yaml",
        "manifest.md",
        "controls.md",
        "stress_tests.md",
        "caveats.md",
        "result_summary.md",
        "decision.md",
    ],
}

# Directories required for full tier (may be empty)
REQUIRED_DIRS: dict[str, list[str]] = {
    "micro": [],
    "standard": [],
    "full": ["baselines", "metrics"],
}

# WHY: these patterns indicate the author copied the template but never filled it.
# We match on case-insensitive substrings because templates use angle-brackets.
PLACEHOLDER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"<YYYYMMDD", re.IGNORECASE),
    re.compile(r"YYYY-MM-DD"),
    re.compile(r"\[One sentence", re.IGNORECASE),
    re.compile(r"\[add project", re.IGNORECASE),
    re.compile(r"\[describe", re.IGNORECASE),
    re.compile(r"\[TODO\]", re.IGNORECASE),
    re.compile(r"<your-", re.IGNORECASE),
    re.compile(r"EXPERIMENT_ID"),
    re.compile(r"\[claim here\]", re.IGNORECASE),
    re.compile(r"\[fill in\]", re.IGNORECASE),
]


# ── Result types ──────────────────────────────────────────────────────────────
class CheckResult(NamedTuple):
    """Result of a single artifact check."""

    name: str
    status: str  # "pass" | "fail" | "warn"
    detail: str


# ── Core logic ────────────────────────────────────────────────────────────────
def detect_tier(experiment_dir: Path) -> str:
    """Read tier from experiment.yaml; fall back to 'standard' if absent.

    WHY: Auto-detection removes the need to pass --tier manually in most cases.
    The ground truth is always the experiment.yaml, not the folder name.
    """
    yaml_path = experiment_dir / "experiment.yaml"
    if not yaml_path.exists():
        return "standard"

    # WHY: stdlib-only — no pyyaml. Simple line scan is sufficient for
    # a single-key lookup without the overhead of a full YAML parser.
    content = yaml_path.read_text(encoding="utf-8", errors="replace")
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("tier:"):
            value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            if value in REQUIRED_FILES:
                return value
    return "standard"


def find_placeholder(content: str) -> str | None:
    """Return the first matching placeholder string, or None if clean."""
    for pattern in PLACEHOLDER_PATTERNS:
        match = pattern.search(content)
        if match:
            return match.group(0)
    return None


def check_artifact_file(path: Path) -> CheckResult:
    """Check a single required file: exists, non-empty, no placeholders."""
    name = path.name
    if not path.exists():
        return CheckResult(name, "fail", "MISSING")

    try:
        content = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        return CheckResult(name, "fail", f"READ ERROR: {exc}")

    if not content:
        return CheckResult(name, "warn", "empty file")

    placeholder = find_placeholder(content)
    if placeholder:
        return CheckResult(name, "warn", f'contains placeholder: "{placeholder}"')

    return CheckResult(name, "pass", "non-empty, no placeholders")


def check_artifact_dir(path: Path) -> CheckResult:
    """Check a required directory: exists (content may be empty)."""
    name = str(path.name) + "/"
    if not path.exists():
        return CheckResult(name, "fail", "MISSING")
    if not path.is_dir():
        return CheckResult(name, "fail", "exists but is not a directory")

    # WHY: empty dir is a warning, not a failure — baselines/ and metrics/ are
    # populated only after experiments run, which may not have happened yet.
    items = list(path.iterdir())
    if not items:
        return CheckResult(name, "warn", "empty directory")

    return CheckResult(name, "pass", "directory exists")


def validate_experiment(
    experiment_dir: Path,
    tier_override: str | None = None,
    compute_sha256: bool = False,
) -> tuple[list[CheckResult], str, bool]:
    """Validate a single experiment folder.

    Returns:
        (results, tier, is_valid)

    WHY: Returns structured results instead of printing directly so that
    --list mode can reuse the same logic without output side-effects.
    """
    tier = tier_override or detect_tier(experiment_dir)
    results: list[CheckResult] = []

    for filename in REQUIRED_FILES[tier]:
        results.append(check_artifact_file(experiment_dir / filename))

    for dirname in REQUIRED_DIRS[tier]:
        results.append(check_artifact_dir(experiment_dir / dirname))

    if compute_sha256 and results:
        _write_sha256(experiment_dir, results)

    is_valid = all(r.status == "pass" for r in results)
    return results, tier, is_valid


def _write_sha256(experiment_dir: Path, results: list[CheckResult]) -> None:
    """Compute SHA-256 for all artifact files and write to artifacts.sha256."""
    lines: list[str] = []
    for result in results:
        # WHY: only hash files that exist (pass or warn status, not fail)
        if result.status == "fail":
            continue
        name = result.name.rstrip("/")
        path = experiment_dir / name
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {name}")

    sha_path = experiment_dir / "artifacts.sha256"
    sha_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  SHA-256 written → {sha_path}")


# ── Rendering ─────────────────────────────────────────────────────────────────
def render_results(
    experiment_dir: Path,
    results: list[CheckResult],
    tier: str,
) -> tuple[int, int, int]:
    """Print formatted results. Returns (pass_count, fail_count, warn_count)."""
    print(f"\nValidating: {experiment_dir}/ [{_bold('tier: ' + tier)}]\n")

    pass_count = fail_count = warn_count = 0
    for r in results:
        if r.status == "pass":
            icon = _green("✅")
            detail = _green(f"({r.detail})")
            pass_count += 1
        elif r.status == "fail":
            icon = _red("❌")
            detail = _red(r.detail)
            fail_count += 1
        else:
            icon = _yellow("⚠️ ")
            detail = _yellow(f"({r.detail})")
            warn_count += 1

        # WHY: pad name to 20 chars for alignment across different lengths
        print(f"  {icon}  {r.name:<20} {detail}")

    return pass_count, fail_count, warn_count


def print_summary(results: list[CheckResult], tier: str) -> bool:
    """Print pass count summary and final status. Returns True if valid."""
    total = len(results)
    pass_count = sum(1 for r in results if r.status == "pass")
    fail_count = sum(1 for r in results if r.status == "fail")
    warn_count = sum(1 for r in results if r.status == "warn")

    print(f"\n{pass_count}/{total} checks passed")

    if fail_count == 0 and warn_count == 0:
        print(_green("Status: ✅ VALID"))
        return True
    elif fail_count == 0:
        status = _yellow(f"⚠️  VALID WITH WARNINGS — {warn_count} warning(s)")
        print(f"Status: {status}")
        return True
    else:
        parts = []
        if fail_count:
            parts.append(f"{fail_count} missing")
        if warn_count:
            parts.append(f"{warn_count} warnings")
        status = _red("❌ INVALID — " + ", ".join(parts))
        print(f"Status: {status}")
        return False


# ── --list mode ───────────────────────────────────────────────────────────────
def _status_icon(results: list[CheckResult], is_valid: bool) -> str:
    """Compact status icon for --list table."""
    if not results:
        # micro tier — no files required, always valid
        return "✅"
    if is_valid:
        if any(r.status == "warn" for r in results):
            return "⚠️ "
        return "✅"
    return "❌"


def list_experiments(experiments_root: Path) -> None:
    """Walk experiments/ and print a summary table."""
    if not experiments_root.exists():
        print(_red(f"Directory not found: {experiments_root}"))
        sys.exit(1)

    # WHY: sort by name = sort by date prefix (YYYYMMDD-slug format)
    dirs = sorted(
        [d for d in experiments_root.iterdir() if d.is_dir() and not d.name.startswith("_")],
        key=lambda d: d.name,
    )

    if not dirs:
        print("No experiments found.")
        return

    # Header
    header = f"{'ID':<35} {'Tier':<10} {'Status':<6} Missing files"
    print("\n" + _bold(header))
    print("─" * 80)

    for d in dirs:
        tier = detect_tier(d)
        results, tier, is_valid = validate_experiment(d)
        icon = _status_icon(results, is_valid)
        missing = [r.name for r in results if r.status == "fail"]
        missing_str = ", ".join(missing) if missing else "—"

        # Trim long experiment IDs
        exp_id = d.name[:33] + ".." if len(d.name) > 35 else d.name
        print(f"{exp_id:<35} {tier:<10} {icon:<6} {missing_str}")

    print()


# ── CLI ───────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="validate_experiment",
        description="Validate FL (Falsification Ladder) experiment folders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate_experiment.py experiments/20260515-foo/
  python scripts/validate_experiment.py experiments/20260515-foo/ --sha256
  python scripts/validate_experiment.py experiments/20260515-foo/ --tier full
  python scripts/validate_experiment.py --list
        """,
    )
    parser.add_argument(
        "experiment_dir",
        nargs="?",
        type=Path,
        help="Path to the experiment directory to validate.",
    )
    parser.add_argument(
        "--tier",
        choices=["micro", "standard", "full"],
        default=None,
        help="Override tier detection (default: read from experiment.yaml).",
    )
    parser.add_argument(
        "--sha256",
        action="store_true",
        help="Compute SHA-256 for each artifact and write to artifacts.sha256.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all experiments in experiments/ with their status.",
    )
    return parser


def main() -> int:
    """Entry point. Returns exit code (0=valid, 1=invalid)."""
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        # WHY: locate experiments/ relative to the script's parent (project root)
        project_root = Path(__file__).parent.parent
        list_experiments(project_root / "experiments")
        return 0

    if args.experiment_dir is None:
        parser.print_help()
        return 1

    experiment_dir = args.experiment_dir.resolve()
    if not experiment_dir.exists():
        print(_red(f"Error: directory does not exist: {experiment_dir}"))
        return 1

    if not experiment_dir.is_dir():
        print(_red(f"Error: not a directory: {experiment_dir}"))
        return 1

    results, tier, _ = validate_experiment(
        experiment_dir,
        tier_override=args.tier,
        compute_sha256=args.sha256,
    )

    if tier == "micro":
        print(f"\nValidating: {experiment_dir}/ [{_bold('tier: micro')}]")
        print(_green("  ✅  Micro-tier — no folder artifacts required."))
        print("\n1/1 checks passed")
        print(_green("Status: ✅ VALID"))
        return 0

    render_results(experiment_dir, results, tier)
    is_valid = print_summary(results, tier)
    return 0 if is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
