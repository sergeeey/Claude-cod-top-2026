#!/usr/bin/env python3
"""FL (Falsification Ladder) + EstimandOps 2.0 experiment folder validator.

Checks that an experiment directory contains the required artifact files
for its declared tier (micro | standard | full), that files are non-empty
and placeholder-free, and that EstimandOps fields are filled in experiment.yaml
and claim.md.

Usage:
    python scripts/validate_experiment.py experiments/20260515-foo/
    python scripts/validate_experiment.py experiments/20260515-foo/ --sha256
    python scripts/validate_experiment.py experiments/20260515-foo/ --tier full
    python scripts/validate_experiment.py --list
    python scripts/validate_experiment.py experiments/20260515-foo/ --estimand
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
# WHY: full-ladder list matches falsification-ladder.md Step -2 to 11 artifacts.
# EstimandOps 2.0: estimand.md added as required for full-ladder (Step -1).
REQUIRED_FILES: dict[str, list[str]] = {
    "micro": [],  # no folder required — just a PR inline block
    "standard": ["claim.md", "controls.md", "decision.md"],
    "full": [
        "claim.md",
        "estimand.md",  # EstimandOps 2.0: required for full-ladder (Step -1)
        "experiment.yaml",
        "manifest.md",
        "controls.md",
        "stress_tests.md",
        "caveats.md",
        "result_summary.md",
        "decision.md",
    ],
}

# EstimandOps: required fields in experiment.yaml
# WHY: declarative check — catches unfilled estimand slots before experiments run.
REQUIRED_YAML_FIELDS: dict[str, list[str]] = {
    "micro": [],
    "standard": ["question_type", "hypothesis"],
    "full": [
        "question_type",
        "hypothesis",
        "estimand.population",
        "estimand.intervention",
        "estimand.endpoint",
        "estimand.mcid",
        "estimand.summary_measure",
    ],
}

# EstimandOps: required fields in claim.md (checked by pattern presence)
# WHY: claim.md has L0 gate checkbox — verify it was filled (not left as template).
REQUIRED_CLAIM_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "micro": [],
    "standard": [
        re.compile(r"\[x\]|\[X\]", re.IGNORECASE),  # at least one checkbox ticked
    ],
    "full": [
        re.compile(r"question.type|L0", re.IGNORECASE),  # L0 section present
        re.compile(r"natural language|estimand statement", re.IGNORECASE),  # NL statement
        re.compile(r"does not mean|does not prove|not mean", re.IGNORECASE),  # not-mean
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


# ── EstimandOps 2.0 checks ────────────────────────────────────────────────────
def check_yaml_estimand_fields(
    experiment_dir: Path,
    tier: str,
) -> list[CheckResult]:
    """Check required EstimandOps fields in experiment.yaml (stdlib-only line scan).

    WHY: Declarative check catches unfilled estimand slots before experiments run.
    Uses simple line scanning — no pyyaml dep — sufficient for flat key detection.
    Nested keys like 'estimand.population' are matched as 'population:' anywhere
    in the file, which is acceptable for our YAML structure.
    """
    required_fields = REQUIRED_YAML_FIELDS.get(tier, [])
    if not required_fields:
        return []

    yaml_path = experiment_dir / "experiment.yaml"
    if not yaml_path.exists():
        # File existence already checked via check_artifact_file; skip here.
        return []

    try:
        content = yaml_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = content.splitlines()
    results: list[CheckResult] = []

    for field in required_fields:
        # WHY: nested keys like "estimand.population" → look for "population:" in file.
        leaf = field.split(".")[-1]
        key_pattern = re.compile(rf"^\s*{re.escape(leaf)}\s*:", re.IGNORECASE)
        found = any(key_pattern.match(line) for line in lines)

        if not found:
            results.append(
                CheckResult(f"yaml:{field}", "warn", f"missing or placeholder in experiment.yaml")
            )
        else:
            # Check that the found value is not a placeholder/blank
            for line in lines:
                m = key_pattern.match(line)
                if m:
                    value = line.split(":", 1)[1].strip().strip('"').strip("'")
                    placeholder = find_placeholder(value) or (
                        value in ("", "null", "~", "[]", "{}")
                    )
                    if placeholder:
                        results.append(
                            CheckResult(
                                f"yaml:{field}",
                                "warn",
                                f"value is placeholder/empty in experiment.yaml",
                            )
                        )
                    else:
                        results.append(CheckResult(f"yaml:{field}", "pass", f"present"))
                    break

    return results


def check_claim_estimand_patterns(
    experiment_dir: Path,
    tier: str,
) -> list[CheckResult]:
    """Check that claim.md contains required EstimandOps patterns.

    WHY: claim.md is the first artifact filled. These patterns confirm the author
    completed the L0 gate (question type), wrote the natural language estimand
    statement, and documented what the result does NOT mean — all required by
    EstimandOps before any falsifiable claim is written.
    """
    patterns = REQUIRED_CLAIM_PATTERNS.get(tier, [])
    if not patterns:
        return []

    claim_path = experiment_dir / "claim.md"
    if not claim_path.exists():
        return []

    try:
        content = claim_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    results: list[CheckResult] = []
    pattern_names = {
        0: "claim:L0-checkbox",
        1: "claim:L0-question-type",
        2: "claim:nl-estimand-statement",
        3: "claim:not-mean-section",
    }

    for i, pattern in enumerate(patterns):
        name = pattern_names.get(i, f"claim:pattern-{i}")
        if pattern.search(content):
            results.append(CheckResult(name, "pass", "pattern found"))
        else:
            results.append(
                CheckResult(name, "warn", f"EstimandOps pattern missing: {pattern.pattern}")
            )

    return results


def validate_experiment(
    experiment_dir: Path,
    tier_override: str | None = None,
    compute_sha256: bool = False,
    check_estimand: bool = True,
) -> tuple[list[CheckResult], str, bool]:
    """Validate a single experiment folder.

    Returns:
        (results, tier, is_valid)

    WHY: Returns structured results instead of printing directly so that
    --list mode can reuse the same logic without output side-effects.
    check_estimand=True runs EstimandOps 2.0 field and pattern checks on top of
    the base artifact checks (can be disabled with --no-estimand for legacy folders).
    """
    tier = tier_override or detect_tier(experiment_dir)
    results: list[CheckResult] = []

    for filename in REQUIRED_FILES[tier]:
        results.append(check_artifact_file(experiment_dir / filename))

    for dirname in REQUIRED_DIRS[tier]:
        results.append(check_artifact_dir(experiment_dir / dirname))

    if check_estimand:
        results.extend(check_yaml_estimand_fields(experiment_dir, tier))
        results.extend(check_claim_estimand_patterns(experiment_dir, tier))

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
        description="Validate FL (Falsification Ladder) + EstimandOps 2.0 experiment folders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate_experiment.py experiments/20260515-foo/
  python scripts/validate_experiment.py experiments/20260515-foo/ --sha256
  python scripts/validate_experiment.py experiments/20260515-foo/ --tier full
  python scripts/validate_experiment.py experiments/20260515-foo/ --estimand
  python scripts/validate_experiment.py experiments/20260515-foo/ --no-estimand
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
    parser.add_argument(
        "--estimand",
        action="store_true",
        default=True,
        help="Run EstimandOps 2.0 field checks (default: enabled).",
    )
    parser.add_argument(
        "--no-estimand",
        dest="estimand",
        action="store_false",
        help="Skip EstimandOps 2.0 checks (use for legacy experiment folders).",
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
        check_estimand=args.estimand,
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
