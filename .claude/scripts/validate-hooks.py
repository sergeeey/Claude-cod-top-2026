#!/usr/bin/env python3
"""
Hook Validation Tool — catch errors before runtime.

Validates hooks configuration to prevent broken deployments:
- Checks hook imports (all imported modules exist)
- Verifies Python paths (interpreter exists)
- Detects duplicate event registrations
- Validates JSON structure in settings.json

Pattern source: Anthropic Financial Services repo (check.py + validate.py)
https://github.com/anthropics/anthropic-financial-services/tree/main/tools

Usage:
    python scripts/validate-hooks.py                     # validate all hooks
    python scripts/validate-hooks.py --config settings.json  # specific config
    python scripts/validate-hooks.py --ci                # CI mode (exit code 1 on error)
"""

import argparse
import ast
import json
import sys
from collections import defaultdict
from pathlib import Path


class ValidationError:
    """A single validation error."""

    def __init__(self, severity: str, hook: str, message: str, details: str = ""):
        self.severity = severity  # "ERROR" | "WARNING" | "INFO"
        self.hook = hook
        self.message = message
        self.details = details

    def __str__(self):
        icon = {"ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️"}.get(self.severity, "?")
        result = f"{icon} [{self.severity}] {self.hook}: {self.message}"
        if self.details:
            result += f"\n    Details: {self.details}"
        return result


def validate_json_structure(config_path: Path) -> list[ValidationError]:
    """Validate settings.json structure."""
    errors = []

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(
            ValidationError(
                severity="ERROR",
                hook="settings.json",
                message="Invalid JSON syntax",
                details=str(e),
            )
        )
        return errors  # Can't continue validation if JSON invalid

    except FileNotFoundError:
        errors.append(
            ValidationError(
                severity="ERROR",
                hook="settings.json",
                message=f"Config file not found: {config_path}",
            )
        )
        return errors

    # Check required top-level fields
    if "hooks" not in config:
        errors.append(
            ValidationError(
                severity="ERROR",
                hook="settings.json",
                message='Missing required field: "hooks"',
            )
        )

    return errors


def validate_python_paths(config: dict) -> list[ValidationError]:
    """Validate Python interpreter paths in hook configurations."""
    errors = []

    hooks = config.get("hooks", {})
    for event, hook_configs in hooks.items():
        if not isinstance(hook_configs, list):
            hook_configs = [hook_configs]

        for hook_config in hook_configs:
            if not isinstance(hook_config, dict):
                continue

            python_path = hook_config.get("python")
            if not python_path:
                continue  # No python field, skip

            python_path_obj = Path(python_path)
            if not python_path_obj.exists():
                errors.append(
                    ValidationError(
                        severity="ERROR",
                        hook=hook_config.get("script", event),
                        message=f"Python interpreter not found: {python_path}",
                        details="Update python field to valid interpreter path",
                    )
                )

    return errors


def validate_hook_imports(hook_script: Path) -> list[ValidationError]:
    """
    Validate imports in a hook script.

    Checks if all imported modules can be resolved (basic static check).
    """
    errors = []

    if not hook_script.exists():
        errors.append(
            ValidationError(
                severity="ERROR",
                hook=hook_script.name,
                message=f"Hook script not found: {hook_script}",
            )
        )
        return errors

    try:
        with open(hook_script, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(hook_script))
    except SyntaxError as e:
        errors.append(
            ValidationError(
                severity="ERROR",
                hook=hook_script.name,
                message="Python syntax error",
                details=f"Line {e.lineno}: {e.msg}",
            )
        )
        return errors

    # Extract imports
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])

    # Try importing each module (basic check)
    for module_name in set(imports):
        try:
            __import__(module_name)
        except ImportError:
            # Not necessarily an error — could be project-local module
            # Only flag if it's a common stdlib/third-party module
            if module_name in [
                "yaml",
                "pydantic",
                "structlog",
                "anthropic",
                "openai",
            ]:
                errors.append(
                    ValidationError(
                        severity="WARNING",
                        hook=hook_script.name,
                        message=f"Module may not be installed: {module_name}",
                        details="Run: pip install <module> if needed",
                    )
                )

    return errors


def validate_duplicate_events(config: dict) -> list[ValidationError]:
    """Detect duplicate event registrations (same script registered twice for same event)."""
    errors = []

    hooks = config.get("hooks", {})
    event_to_scripts = defaultdict(list)

    for event, hook_configs in hooks.items():
        if not isinstance(hook_configs, list):
            hook_configs = [hook_configs]

        for hook_config in hook_configs:
            if not isinstance(hook_config, dict):
                continue

            script = hook_config.get("script", "")
            if script:
                event_to_scripts[event].append(script)

    # Check for duplicates
    for event, scripts in event_to_scripts.items():
        seen = set()
        for script in scripts:
            if script in seen:
                errors.append(
                    ValidationError(
                        severity="WARNING",
                        hook=script,
                        message=f"Duplicate registration for event: {event}",
                        details="Same script registered multiple times (may be intentional)",
                    )
                )
            seen.add(script)

    return errors


def validate_hook_scripts_exist(config: dict, hooks_dir: Path) -> list[ValidationError]:
    """Check that all referenced hook scripts exist."""
    errors = []

    hooks = config.get("hooks", {})
    for event, hook_configs in hooks.items():
        if not isinstance(hook_configs, list):
            hook_configs = [hook_configs]

        for hook_config in hook_configs:
            if not isinstance(hook_config, dict):
                continue

            script = hook_config.get("script", "")
            if not script:
                errors.append(
                    ValidationError(
                        severity="WARNING",
                        hook=event,
                        message=f'No "script" field in hook config for event: {event}',
                    )
                )
                continue

            script_path = hooks_dir / script
            if not script_path.exists():
                errors.append(
                    ValidationError(
                        severity="ERROR",
                        hook=script,
                        message=f"Hook script not found: {script_path}",
                        details=f"Event: {event}",
                    )
                )

    return errors


def validate_all(
    config_path: Path, hooks_dir: Path, check_imports: bool = True
) -> list[ValidationError]:
    """Run all validation checks."""
    all_errors = []

    # 1. Validate JSON structure
    all_errors.extend(validate_json_structure(config_path))

    # If JSON invalid, stop here
    if any(e.severity == "ERROR" for e in all_errors):
        return all_errors

    # Load config
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    # 2. Validate Python paths
    all_errors.extend(validate_python_paths(config))

    # 3. Check hook scripts exist
    all_errors.extend(validate_hook_scripts_exist(config, hooks_dir))

    # 4. Detect duplicate events
    all_errors.extend(validate_duplicate_events(config))

    # 5. Validate imports (optional, slower)
    if check_imports:
        hooks = config.get("hooks", {})
        checked_scripts = set()

        for _event, hook_configs in hooks.items():
            if not isinstance(hook_configs, list):
                hook_configs = [hook_configs]

            for hook_config in hook_configs:
                if not isinstance(hook_config, dict):
                    continue

                script = hook_config.get("script", "")
                if not script or script in checked_scripts:
                    continue

                script_path = hooks_dir / script
                if script_path.exists():
                    all_errors.extend(validate_hook_imports(script_path))
                    checked_scripts.add(script)

    return all_errors


def print_summary(errors: list[ValidationError]) -> dict:
    """Print validation results summary."""
    errors_count = sum(1 for e in errors if e.severity == "ERROR")
    warnings_count = sum(1 for e in errors if e.severity == "WARNING")
    info_count = sum(1 for e in errors if e.severity == "INFO")

    if not errors:
        print("✅ All validation checks passed!")
        return {"errors": 0, "warnings": 0, "info": 0}

    print("📋 Validation Results:\n")
    for error in errors:
        print(error)

    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"  ❌ Errors: {errors_count}")
    print(f"  ⚠️  Warnings: {warnings_count}")
    print(f"  ℹ️  Info: {info_count}")
    print("=" * 60)

    return {"errors": errors_count, "warnings": warnings_count, "info": info_count}


def main():
    parser = argparse.ArgumentParser(description="Validate hooks configuration before deployment")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".claude" / "settings.json",
        help="Path to settings.json (default: ~/.claude/settings.json)",
    )
    parser.add_argument(
        "--hooks-dir",
        type=Path,
        default=Path.home() / ".claude" / "hooks",
        help="Path to hooks directory (default: ~/.claude/hooks/)",
    )
    parser.add_argument(
        "--no-imports",
        action="store_true",
        help="Skip import validation (faster, less thorough)",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: exit with code 1 if errors found",
    )

    args = parser.parse_args()

    print("🔍 Validating hooks configuration...")
    print(f"📂 Config: {args.config}")
    print(f"📂 Hooks directory: {args.hooks_dir}\n")

    # Run validation
    errors = validate_all(
        config_path=args.config,
        hooks_dir=args.hooks_dir,
        check_imports=not args.no_imports,
    )

    # Print summary
    summary = print_summary(errors)

    # Exit code for CI
    if args.ci and summary["errors"] > 0:
        print("\n❌ Validation failed. Fix errors before deployment.")
        sys.exit(1)

    if summary["errors"] > 0:
        print("\n⚠️  Errors found. Run without --ci to see details.")
        sys.exit(1)

    print("\n✅ Validation complete!")
    sys.exit(0)


if __name__ == "__main__":
    main()
