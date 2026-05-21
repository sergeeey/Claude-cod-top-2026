#!/usr/bin/env python3
"""
Skill Propagation System — sync skills from source to agent bundles.

DRY principle at scale:
- Skills defined once in ~/.claude/skills/
- Agents declare required skills in frontmatter (skills: [skill1, skill2])
- This script copies skill definitions into agent bundles
- Validation detects drift (agent copy ≠ source)

Pattern source: Anthropic Financial Services repo
https://github.com/anthropics/anthropic-financial-services/tree/main/tools

Usage:
    python scripts/sync-agent-skills.py                # sync all agents
    python scripts/sync-agent-skills.py --check        # check for drift (CI mode)
    python scripts/sync-agent-skills.py --agent builder  # sync specific agent
"""

import argparse
import hashlib
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class SkillRef:
    """Reference to a skill that should be bundled with an agent."""

    name: str
    source_path: Path
    agent_bundle_path: Path


@dataclass
class SyncResult:
    """Result of syncing one skill."""

    skill_name: str
    action: str  # "copied" | "up-to-date" | "drift-detected" | "missing"
    details: str


def get_skill_hash(skill_path: Path) -> str:
    """Compute SHA256 hash of skill content for drift detection."""
    if not skill_path.exists():
        return ""
    content = skill_path.read_text(encoding="utf-8")
    return hashlib.sha256(content.encode()).hexdigest()


def extract_skills_from_frontmatter(agent_path: Path) -> list[str]:
    """
    Extract skills list from agent frontmatter.

    Expected format:
    ---
    name: agent-name
    skills: [skill1, skill2, skill3]
    ---

    Returns:
        List of skill names (empty if no skills field)
    """
    content = agent_path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return []

    # Extract frontmatter (between first and second "---")
    parts = content.split("---", 2)
    if len(parts) < 3:
        return []

    frontmatter_text = parts[1].strip()
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        return []

    skills = frontmatter.get("skills", [])
    if isinstance(skills, str):
        # Handle YAML single-line: "skills: skill1, skill2"
        skills = [s.strip() for s in skills.split(",")]
    return skills


def find_agents(agents_dir: Path, agent_name: str | None = None) -> list[Path]:
    """Find all agent files to process."""
    if agent_name:
        agent_path = agents_dir / f"{agent_name}.md"
        return [agent_path] if agent_path.exists() else []

    # Find all *.md files in agents/ (excluding teams/ subdirectory)
    agents = []
    for path in agents_dir.glob("*.md"):
        if path.is_file():
            agents.append(path)
    return sorted(agents)


def sync_skill(
    skill_name: str,
    skills_source_dir: Path,
    agent_bundle_dir: Path,
    check_only: bool = False,
) -> SyncResult:
    """
    Sync one skill from source to agent bundle.

    Args:
        skill_name: Name of skill (e.g., "routing-policy")
        skills_source_dir: Source skills directory (~/.claude/skills/)
        agent_bundle_dir: Agent's bundle directory (.claude/agents/builder/bundled-skills/)
        check_only: If True, only check for drift (don't copy)

    Returns:
        SyncResult with action taken
    """
    # Try to find skill in source (could be in subfolder)
    skill_candidates = list(skills_source_dir.rglob(f"{skill_name}.md"))
    if not skill_candidates:
        # Try without .md extension
        skill_candidates = list(skills_source_dir.rglob(f"{skill_name}/*.md"))

    if not skill_candidates:
        return SyncResult(
            skill_name=skill_name,
            action="missing",
            details=f"Skill not found in {skills_source_dir}",
        )

    source_skill = skill_candidates[0]  # Take first match
    target_skill = agent_bundle_dir / f"{skill_name}.md"

    source_hash = get_skill_hash(source_skill)
    target_hash = get_skill_hash(target_skill) if target_skill.exists() else ""

    if source_hash == target_hash:
        return SyncResult(
            skill_name=skill_name,
            action="up-to-date",
            details=f"Hash: {source_hash[:8]}",
        )

    if check_only:
        if target_skill.exists():
            return SyncResult(
                skill_name=skill_name,
                action="drift-detected",
                details=f"Source: {source_hash[:8]}, Target: {target_hash[:8]}",
            )
        else:
            return SyncResult(
                skill_name=skill_name,
                action="missing",
                details="Target does not exist",
            )

    # Copy skill from source to target
    agent_bundle_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_skill, target_skill)

    return SyncResult(
        skill_name=skill_name,
        action="copied",
        details=f"{source_skill} → {target_skill}",
    )


def sync_agent(
    agent_path: Path,
    skills_source_dir: Path,
    check_only: bool = False,
) -> list[SyncResult]:
    """
    Sync all skills for one agent.

    Args:
        agent_path: Path to agent file (e.g., .claude/agents/builder.md)
        skills_source_dir: Source skills directory
        check_only: If True, only check for drift (don't copy)

    Returns:
        List of SyncResult for each skill
    """
    agent_name = agent_path.stem
    skills = extract_skills_from_frontmatter(agent_path)

    if not skills:
        return []  # No skills to sync

    agent_bundle_dir = agent_path.parent / agent_name / "bundled-skills"

    results = []
    for skill_name in skills:
        result = sync_skill(
            skill_name=skill_name,
            skills_source_dir=skills_source_dir,
            agent_bundle_dir=agent_bundle_dir,
            check_only=check_only,
        )
        results.append(result)

    return results


def print_summary(all_results: dict[str, list[SyncResult]]):
    """Print summary of sync results."""
    total_copied = 0
    total_up_to_date = 0
    total_drift = 0
    total_missing = 0

    for agent_name, results in all_results.items():
        if not results:
            continue  # Agent has no skills

        print(f"\n## {agent_name}")
        for result in results:
            icon = {
                "copied": "✅",
                "up-to-date": "⏭️",
                "drift-detected": "⚠️",
                "missing": "❌",
            }.get(result.action, "❓")

            print(f"  {icon} {result.skill_name}: {result.action} — {result.details}")

            # Update counters
            if result.action == "copied":
                total_copied += 1
            elif result.action == "up-to-date":
                total_up_to_date += 1
            elif result.action == "drift-detected":
                total_drift += 1
            elif result.action == "missing":
                total_missing += 1

    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"  ✅ Copied: {total_copied}")
    print(f"  ⏭️  Up-to-date: {total_up_to_date}")
    print(f"  ⚠️  Drift detected: {total_drift}")
    print(f"  ❌ Missing: {total_missing}")
    print("=" * 60)

    return {
        "copied": total_copied,
        "up_to_date": total_up_to_date,
        "drift": total_drift,
        "missing": total_missing,
    }


def main():
    parser = argparse.ArgumentParser(description="Sync skills from source to agent bundles")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for drift without copying (CI mode)",
    )
    parser.add_argument(
        "--agent",
        type=str,
        help="Sync specific agent only (e.g., 'builder')",
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=Path.home() / ".claude" / "skills",
        help="Source skills directory (default: ~/.claude/skills/)",
    )
    parser.add_argument(
        "--agents-dir",
        type=Path,
        default=Path.home() / ".claude" / "agents",
        help="Agents directory (default: ~/.claude/agents/)",
    )

    args = parser.parse_args()

    # Validate directories
    if not args.skills_dir.exists():
        print(f"❌ Skills directory not found: {args.skills_dir}", file=sys.stderr)
        sys.exit(1)

    if not args.agents_dir.exists():
        print(f"❌ Agents directory not found: {args.agents_dir}", file=sys.stderr)
        sys.exit(1)

    # Find agents to process
    agents = find_agents(args.agents_dir, args.agent)
    if not agents:
        if args.agent:
            print(f"❌ Agent not found: {args.agent}", file=sys.stderr)
        else:
            print(f"❌ No agents found in {args.agents_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"🔄 {'Checking' if args.check else 'Syncing'} skills for {len(agents)} agent(s)...")
    print(f"📂 Skills source: {args.skills_dir}")
    print(f"📂 Agents directory: {args.agents_dir}")

    # Sync all agents
    all_results = {}
    for agent_path in agents:
        agent_name = agent_path.stem
        results = sync_agent(
            agent_path=agent_path,
            skills_source_dir=args.skills_dir,
            check_only=args.check,
        )
        if results:
            all_results[agent_name] = results

    # Print summary
    summary = print_summary(all_results)

    # Exit code for CI
    if args.check and (summary["drift"] > 0 or summary["missing"] > 0):
        print("\n❌ Drift or missing skills detected. Run without --check to fix.")
        sys.exit(1)

    print("\n✅ Done!")
    sys.exit(0)


if __name__ == "__main__":
    main()
