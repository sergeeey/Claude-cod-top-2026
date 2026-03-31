#!/usr/bin/env python3
"""AgentShield — self-audit of Claude Code configuration.

WHY: Hooks protect against external threats, but nothing checks whether
the configuration itself is secure. This script scans CLAUDE.md,
settings.json, agent definitions, and MCP configs for vulnerabilities.

Usage:
    python scripts/config_audit_scan.py              # from project root
    python scripts/config_audit_scan.py --fix        # show fix suggestions
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Severity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class Finding:
    severity: Severity
    category: str
    message: str
    file: str
    fix: str = ""


def scan_settings(settings_path: Path) -> list[Finding]:
    """Scan settings.json for permission and hook issues."""
    findings: list[Finding] = []
    if not settings_path.exists():
        findings.append(
            Finding(
                Severity.HIGH,
                "missing-config",
                "settings.json not found — no hooks or permissions active",
                str(settings_path),
                "Run install.sh --link full to install settings.json",
            )
        )
        return findings

    try:
        with open(settings_path, encoding="utf-8") as f:
            settings = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        findings.append(
            Finding(
                Severity.CRITICAL,
                "broken-config",
                f"settings.json is not valid JSON: {e}",
                str(settings_path),
                "Fix JSON syntax errors",
            )
        )
        return findings

    # Check permissions
    perms = settings.get("permissions", {})
    allow_list = perms.get("allow", [])
    deny_list = perms.get("deny", [])

    if "Bash(*)" in allow_list and not deny_list:
        findings.append(
            Finding(
                Severity.CRITICAL,
                "wide-open-bash",
                "Bash(*) allowed with NO deny rules — any command can run",
                str(settings_path),
                "Add deny rules for dangerous patterns (rm -rf, push --force, DROP TABLE)",
            )
        )

    # Check for bypassPermissions
    if settings.get("defaultMode") == "bypassPermissions":
        findings.append(
            Finding(
                Severity.CRITICAL,
                "bypass-permissions",
                "defaultMode is bypassPermissions — ALL safety checks disabled",
                str(settings_path),
                "Use 'default' or 'acceptEdits' mode instead",
            )
        )

    # Check hooks exist
    hooks = settings.get("hooks", {})
    critical_hooks = ["PreToolUse", "PostToolUse", "SessionStart", "PermissionRequest"]
    for hook_name in critical_hooks:
        if hook_name not in hooks:
            findings.append(
                Finding(
                    Severity.HIGH,
                    "missing-hook",
                    f"No {hook_name} hooks configured — safety gap",
                    str(settings_path),
                    f"Add {hook_name} hooks to settings.json",
                )
            )

    return findings


def scan_agents(agents_dir: Path) -> list[Finding]:
    """Scan agent definitions for security issues."""
    findings: list[Finding] = []
    if not agents_dir.exists():
        return findings

    for agent_file in agents_dir.glob("*.md"):
        try:
            content = agent_file.read_text(encoding="utf-8")
        except OSError:
            continue

        # Check for overly permissive tools
        if "Bash" in content and "Write" in content and "Edit" in content:
            # WHY: agents with all three can modify any file and run any command
            if "isolation" not in content.lower() and "worktree" not in content.lower():
                findings.append(
                    Finding(
                        Severity.MEDIUM,
                        "unrestricted-agent",
                        f"{agent_file.name} has Bash+Write+Edit but no isolation",
                        str(agent_file),
                        "Add isolation: worktree or limit tools",
                    )
                )

        # Check for missing maxTurns
        if "maxTurns" not in content:
            findings.append(
                Finding(
                    Severity.LOW,
                    "unbounded-agent",
                    f"{agent_file.name} has no maxTurns — could run indefinitely",
                    str(agent_file),
                    "Add maxTurns field to agent frontmatter",
                )
            )

    return findings


def scan_claude_md(claude_md_path: Path) -> list[Finding]:
    """Scan CLAUDE.md for injection risks."""
    findings: list[Finding] = []
    if not claude_md_path.exists():
        return findings

    try:
        content = claude_md_path.read_text(encoding="utf-8")
    except OSError:
        return findings

    # Check for dangerous instructions
    dangerous_patterns = [
        (r"ignore.*previous.*instructions", "prompt injection pattern"),
        (r"you are now", "role hijacking pattern"),
        (r"forget.*everything", "context reset pattern"),
        (r"bypass.*safety", "safety bypass pattern"),
    ]
    for pattern, desc in dangerous_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            findings.append(
                Finding(
                    Severity.CRITICAL,
                    "injection-risk",
                    f"CLAUDE.md contains suspicious pattern: {desc}",
                    str(claude_md_path),
                    "Review and remove suspicious instructions",
                )
            )

    return findings


def scan_mcp(mcp_path: Path) -> list[Finding]:
    """Scan MCP configuration for risky servers."""
    findings: list[Finding] = []
    if not mcp_path.exists():
        return findings

    try:
        with open(mcp_path, encoding="utf-8") as f:
            mcp_config = json.load(f)
    except (json.JSONDecodeError, OSError):
        return findings

    servers = mcp_config.get("mcpServers", {})
    for name, config in servers.items():
        cmd = config.get("command", "")
        args = config.get("args", [])

        # Check for servers running with elevated privileges
        if "sudo" in cmd or "--privileged" in str(args):
            findings.append(
                Finding(
                    Severity.HIGH,
                    "privileged-mcp",
                    f"MCP server '{name}' runs with elevated privileges",
                    str(mcp_path),
                    "Remove sudo/privileged flags unless absolutely necessary",
                )
            )

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentShield — Claude Code config audit")
    parser.add_argument("--fix", action="store_true", help="Show fix suggestions")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    claude_home = Path.home() / ".claude"

    all_findings: list[Finding] = []
    all_findings.extend(scan_settings(claude_home / "settings.json"))
    all_findings.extend(scan_agents(claude_home / "agents"))
    all_findings.extend(scan_claude_md(claude_home / "CLAUDE.md"))
    all_findings.extend(scan_mcp(claude_home / ".mcp.json"))

    if args.json:
        output = [
            {
                "severity": f.severity.value,
                "category": f.category,
                "message": f.message,
                "file": f.file,
                **({"fix": f.fix} if args.fix else {}),
            }
            for f in all_findings
        ]
        print(json.dumps(output, indent=2))
        sys.exit(1 if any(f.severity == Severity.CRITICAL for f in all_findings) else 0)

    # Human output
    by_severity = {s: [] for s in Severity}
    for f in all_findings:
        by_severity[f.severity].append(f)

    total = len(all_findings)
    critical = len(by_severity[Severity.CRITICAL])

    print("=== AgentShield Config Audit ===\n")

    if not all_findings:
        print("ALL CLEAR: No issues found.\n")
        return

    for severity in Severity:
        items = by_severity[severity]
        if not items:
            continue
        print(f"--- {severity.value} ({len(items)}) ---")
        for f in items:
            print(f"  [{f.category}] {f.message}")
            print(f"    File: {f.file}")
            if args.fix and f.fix:
                print(f"    Fix: {f.fix}")
            print()

    print(f"Total: {total} findings ({critical} critical)")
    sys.exit(1 if critical > 0 else 0)


if __name__ == "__main__":
    main()
