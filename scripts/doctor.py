"""Claude Code Doctor — configuration and environment diagnostic tool.

WHY: A single runnable script that audits all moving parts of the
Claude Code setup (hooks, MCP, memory, agents, skills, tooling) so
problems are caught before they silently break sessions.

Usage:
    python scripts/doctor.py            # from project root
    python ~/.claude/scripts/doctor.py  # from anywhere after install
"""

import json
import py_compile
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class Status(Enum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"


@dataclass
class CheckResult:
    """Outcome of a single diagnostic check."""

    label: str
    status: Status
    detail: str = ""

    def icon(self) -> str:
        return {"ok": "✅", "warn": "⚠️ ", "error": "❌"}[self.status.value]

    def line(self) -> str:
        suffix = f" — {self.detail}" if self.detail else ""
        return f"{self.icon()} {self.label}{suffix}"


@dataclass
class Report:
    """Aggregated diagnostic report."""

    results: list[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    def summary(self) -> tuple[int, int, int]:
        """Return (passed, warnings, errors)."""
        passed = sum(1 for r in self.results if r.status == Status.OK)
        warnings = sum(1 for r in self.results if r.status == Status.WARN)
        errors = sum(1 for r in self.results if r.status == Status.ERROR)
        return passed, warnings, errors

    def exit_code(self) -> int:
        """0 = all green, 1 = errors present, 2 = warnings only."""
        _, warnings, errors = self.summary()
        if errors:
            return 1
        if warnings:
            return 2
        return 0


# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------


def _resolve_base() -> Path:
    """Find the project/install root relative to this script.

    WHY: The script can run from two locations:
      1. <repo>/scripts/doctor.py  → base is <repo>/
      2. ~/.claude/scripts/doctor.py → base is ~/.claude/

    We detect which case we are in by checking for a known anchor file
    (hooks/ directory) one level up from the script.
    """
    script_dir = Path(__file__).resolve().parent
    candidate = script_dir.parent
    if (candidate / "hooks").is_dir():
        return candidate
    # Fallback: use CWD (e.g. when run as `python scripts/doctor.py`)
    cwd_candidate = Path.cwd()
    if (cwd_candidate / "hooks").is_dir():
        return cwd_candidate
    return candidate


BASE: Path = _resolve_base()


def _find_upward(filename: str, start: Path | None = None) -> Path | None:
    """Walk up the directory tree looking for a file by name."""
    current = (start or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        candidate = parent / filename
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_python_version() -> CheckResult:
    """Check 1: Python >= 3.11."""
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    if (v.major, v.minor) >= (3, 11):
        return CheckResult(f"Python {version_str} (>=3.11 required)", Status.OK)
    return CheckResult(
        f"Python {version_str} — upgrade to 3.11+",
        Status.ERROR,
        "install: https://python.org/downloads",
    )


def check_settings_json() -> tuple[CheckResult, dict]:
    """Check 2: settings.json exists and is valid JSON.

    Returns the parsed dict (or {}) alongside the result so later
    checks can reuse the already-parsed data without re-reading.
    """
    settings_path = BASE / "hooks" / "settings.json"
    # WHY: also check the repo-root settings.json used in tests
    if not settings_path.exists():
        settings_path = BASE / "settings.json"
    if not settings_path.exists():
        return (
            CheckResult("settings.json", Status.ERROR, f"not found under {BASE}"),
            {},
        )
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return (
            CheckResult("settings.json", Status.ERROR, f"invalid JSON: {exc}"),
            {},
        )

    hooks_section = data.get("hooks", {})
    # Count all hook entries across all event types
    hook_count = sum(
        len(hook_group.get("hooks", []))
        for event_hooks in hooks_section.values()
        for hook_group in event_hooks
    )
    return (
        CheckResult(
            f"settings.json valid ({hook_count} hooks registered)",
            Status.OK,
            str(
                settings_path.relative_to(BASE) if BASE in settings_path.parents else settings_path
            ),
        ),
        data,
    )


def _extract_py_paths_from_settings(settings: dict) -> list[Path]:
    """Pull every absolute Python script path out of the hook commands.

    WHY: Hook commands have the form:
      "python.exe /abs/path/to/hook.py [args]"
    We extract the .py argument, normalising Windows-style paths.
    """
    paths: list[Path] = []
    hooks_section = settings.get("hooks", {})
    for event_hooks in hooks_section.values():
        for hook_group in event_hooks:
            for hook in hook_group.get("hooks", []):
                cmd: str = hook.get("command", "")
                for token in cmd.split():
                    if token.endswith(".py"):
                        paths.append(Path(token))
    return paths


def _resolve_hook_path(path: Path) -> bool:
    """Check if a hook .py file exists, trying both absolute and relative to BASE.

    WHY: settings.json stores absolute install paths (e.g. C:/Users/sboi/.claude/hooks/X.py)
    but when running from the repo, files live at BASE/hooks/X.py. We check both.
    """
    if path.exists():
        return True
    # Try resolving by filename relative to BASE/hooks/
    relative = BASE / "hooks" / path.name
    if relative.exists():
        return True
    # Try BASE/scripts/ for redact.py etc.
    relative_scripts = BASE / "scripts" / path.name
    return relative_scripts.exists()


def check_hook_files_exist(settings: dict) -> CheckResult:
    """Check 3: every .py referenced in settings.json is present on disk."""
    py_paths = _extract_py_paths_from_settings(settings)
    if not py_paths:
        return CheckResult("Hook files", Status.WARN, "no .py hooks found in settings.json")

    # WHY: deduplicate by filename — settings.json may reference the same file
    # from multiple event types, inflating the "missing" count.
    unique_names = {p.name: p for p in py_paths}
    missing = [p for name, p in unique_names.items() if not _resolve_hook_path(p)]
    total = len(unique_names)
    if missing:
        names = ", ".join(p.name for p in missing[:5])
        extra = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
        return CheckResult(
            f"Hook files — {len(missing)}/{total} missing",
            Status.ERROR,
            f"{names}{extra}",
        )
    return CheckResult(f"All {total} hook files exist", Status.OK)


def _resolve_to_real_path(path: Path) -> Path | None:
    """Resolve a hook path to an actual file on disk."""
    if path.exists():
        return path
    for fallback_dir in [BASE / "hooks", BASE / "scripts"]:
        candidate = fallback_dir / path.name
        if candidate.exists():
            return candidate
    return None


def check_hook_syntax(settings: dict) -> CheckResult:
    """Check 4: all hook .py files compile without syntax errors."""
    py_paths = _extract_py_paths_from_settings(settings)
    unique = {p.name: p for p in py_paths}
    existing = [resolved for p in unique.values() if (resolved := _resolve_to_real_path(p))]
    if not existing:
        return CheckResult("Hook syntax", Status.WARN, "no hook files to check")

    errors: list[str] = []
    for path in existing:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{path.name}: {exc}")

    if errors:
        detail = "; ".join(errors[:3])
        return CheckResult(
            f"Hook syntax — {len(errors)} error(s)",
            Status.ERROR,
            detail,
        )
    return CheckResult(f"All {len(existing)} hook files have valid syntax", Status.OK)


def check_mcp_connectivity() -> CheckResult:
    """Check 5: run `claude mcp list` and report server count."""
    try:
        result = subprocess.run(
            ["claude", "mcp", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout.strip()
        if result.returncode != 0 or not output:
            return CheckResult("MCP servers", Status.WARN, "claude mcp list returned no output")

        # WHY: output is typically "server_name: status" lines or a table.
        # We count non-empty, non-header lines as a heuristic.
        lines = [ln for ln in output.splitlines() if ln.strip() and not ln.startswith("-")]
        # Extract server names from first token before ':' or whitespace
        names = [ln.split(":")[0].strip() for ln in lines if ":" in ln]
        count = len(names) if names else len(lines)
        preview = ", ".join(names[:5])
        extra = f" +{count - 5} more" if count > 5 else ""
        detail = f"{preview}{extra}" if preview else f"{count} lines"
        return CheckResult(f"MCP: {count} server(s) listed ({detail})", Status.OK)
    except FileNotFoundError:
        return CheckResult(
            "MCP check", Status.WARN, "`claude` CLI not found — skip if running outside Claude"
        )
    except subprocess.TimeoutExpired:
        return CheckResult("MCP check", Status.WARN, "claude mcp list timed out (>10s)")


def check_memory_dir() -> CheckResult:
    """Check 6: .claude/memory/ directory exists."""
    # WHY: Check both the project-local .claude/memory and the
    # global ~/.claude/memory since the script can be run from either context.
    candidates = [
        BASE / ".claude" / "memory",
        BASE / "memory",
        Path.home() / ".claude" / "memory",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            file_count = len(list(candidate.iterdir()))
            return CheckResult(
                f".claude/memory/ exists ({file_count} files)",
                Status.OK,
                str(candidate),
            )
    return CheckResult(
        ".claude/memory/ not found",
        Status.WARN,
        f"checked: {', '.join(str(c) for c in candidates)}",
    )


def check_claude_md() -> CheckResult:
    """Check 7: CLAUDE.md exists somewhere in the tree."""
    # Search upward from CWD, then also look in BASE/claude-md/
    found = _find_upward("CLAUDE.md")
    if not found:
        # Repo stores it under claude-md/ subdirectory
        alt = BASE / "claude-md" / "CLAUDE.md"
        if alt.exists():
            found = alt
    if found:
        try:
            rel = found.relative_to(Path.cwd())
            label = f"./{rel}"
        except ValueError:
            label = str(found)
        return CheckResult(f"CLAUDE.md found at {label}", Status.OK)
    return CheckResult(
        "CLAUDE.md not found", Status.WARN, "searched upward from CWD and BASE/claude-md/"
    )


def check_agent_definitions() -> CheckResult:
    """Check 8: agent .md files exist and are non-empty."""
    agents_dir = BASE / "agents"
    if not agents_dir.is_dir():
        return CheckResult(
            "Agent definitions", Status.WARN, f"agents/ dir not found at {agents_dir}"
        )

    # WHY: skip _archived — those are intentionally retired agents.
    md_files = [
        p for p in agents_dir.glob("*.md") if p.is_file() and not p.parent.name.startswith("_")
    ]
    if not md_files:
        return CheckResult("Agent definitions", Status.WARN, "no .md files found in agents/")

    empty = [p for p in md_files if p.stat().st_size == 0]
    if empty:
        names = ", ".join(p.name for p in empty)
        return CheckResult(
            f"Agent definitions — {len(empty)} empty file(s)",
            Status.WARN,
            names,
        )
    return CheckResult(f"{len(md_files)} agent definitions valid", Status.OK)


def check_skill_entry_files() -> CheckResult:
    """Check 9: each skill directory has a recognisable entry file."""
    skills_dir = BASE / "skills"
    if not skills_dir.is_dir():
        return CheckResult("Skills", Status.WARN, f"skills/ dir not found at {skills_dir}")

    # WHY: entry file conventions in this repo — prompt.md, README.md,
    # or a .md file with the same name as the directory, or a plain .md file.
    entry_patterns = ["prompt.md", "README.md", "readme.md"]

    skill_dirs = [p for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith("_")]
    # Also check core/ and extensions/ subdirectories
    for subgroup in ["core", "extensions"]:
        sub = skills_dir / subgroup
        if sub.is_dir():
            skill_dirs.extend(p for p in sub.iterdir() if p.is_dir() and not p.name.startswith("_"))

    if not skill_dirs:
        return CheckResult("Skills", Status.WARN, "no skill directories found")

    missing: list[str] = []
    for skill_dir in skill_dirs:
        has_entry = any((skill_dir / ep).exists() for ep in entry_patterns)
        if not has_entry:
            # Also accept any single .md file in the directory
            has_entry = bool(list(skill_dir.glob("*.md")))
        if not has_entry:
            missing.append(skill_dir.name)

    if missing:
        names = ", ".join(missing[:5])
        extra = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
        return CheckResult(
            f"Skills — {len(missing)} missing entry file(s)",
            Status.WARN,
            f"{names}{extra}",
        )
    return CheckResult(f"All {len(skill_dirs)} skill directories have entry files", Status.OK)


def _tool_version(cmd: list[str], name: str) -> CheckResult:
    """Helper: run `cmd --version` and report availability."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        version = (result.stdout.strip() or result.stderr.strip()).splitlines()[0]
        return CheckResult(f"{name} {version} available", Status.OK)
    except FileNotFoundError:
        return CheckResult(
            f"{name} not found",
            Status.ERROR,
            f"install: pip install {name.lower()}",
        )
    except (subprocess.TimeoutExpired, IndexError):
        return CheckResult(f"{name} check timed out", Status.WARN)


def check_ruff() -> CheckResult:
    """Check 10: ruff is available."""
    return _tool_version(["ruff", "--version"], "ruff")


def check_pytest() -> CheckResult:
    """Check 11: pytest is available."""
    return _tool_version(["pytest", "--version"], "pytest")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def run_doctor() -> Report:
    """Run all checks and return a populated Report."""
    report = Report()

    # Check 1
    report.add(check_python_version())

    # Check 2 — also returns parsed settings for reuse
    settings_result, settings_data = check_settings_json()
    report.add(settings_result)

    # Checks 3 & 4 depend on parsed settings
    report.add(check_hook_files_exist(settings_data))
    report.add(check_hook_syntax(settings_data))

    # Remaining checks are independent
    report.add(check_mcp_connectivity())
    report.add(check_memory_dir())
    report.add(check_claude_md())
    report.add(check_agent_definitions())
    report.add(check_skill_entry_files())
    report.add(check_ruff())
    report.add(check_pytest())

    return report


def print_report(report: Report) -> None:
    """Print the human-readable terminal report."""
    print("\n\U0001f3e5 Claude Code Doctor v1.0")
    print("=" * 30)
    print()
    for result in report.results:
        print(result.line())

    passed, warnings, errors = report.summary()
    total = len(report.results)
    print()
    parts = [f"{passed}/{total} checks passed"]
    if warnings:
        parts.append(f"{warnings} warning{'s' if warnings > 1 else ''}")
    if errors:
        parts.append(f"{errors} error{'s' if errors > 1 else ''}")
    print("Score: " + ", ".join(parts))
    print()


if __name__ == "__main__":
    report = run_doctor()
    print_report(report)
    sys.exit(report.exit_code())
