#!/usr/bin/env python3
"""Populate Obsidian vault with knowledge from multiple sources.

WHY: Obsidian vault starts empty. Real knowledge lives in git history,
CogniML retrospectives, and patterns.md. This script mines all three
and drops structured .md files into raw/ so the Raw→Wiki pipeline
converts them into linked wiki entries automatically.

Usage:
    python scripts/populate_vault.py --all
    python scripts/populate_vault.py --git --limit 50
    python scripts/populate_vault.py --cogniml
    python scripts/populate_vault.py --patterns
"""

import argparse
import json
import re
import subprocess
import urllib.request
from datetime import datetime, UTC
from pathlib import Path

RAW_DIR = Path.home() / ".claude" / "memory" / "raw"
MEMORY_DIR = Path.home() / ".claude" / "memory"
COGNIML_URL = "http://localhost:8400"

# ── helpers ───────────────────────────────────────────────────────────────────


def _write_raw(slug: str, content: str) -> Path:
    """Write content to raw/ dir. Skip if already exists."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    # sanitize slug
    safe = re.sub(r"[^\w\-]", "_", slug)[:60]
    dest = RAW_DIR / f"{safe}.md"
    if dest.exists():
        return dest  # idempotent
    dest.write_text(content, encoding="utf-8")
    return dest


def _cogniml_get(path: str) -> dict | None:
    """GET from CogniML API. Returns None if unavailable."""
    try:
        with urllib.request.urlopen(f"{COGNIML_URL}{path}", timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return None


# ── source 1: git history ─────────────────────────────────────────────────────


def mine_git_history(repo_path: Path, limit: int = 100) -> int:
    """Convert feat/fix/refactor commits to wiki entries.

    WHY: commit messages are the ground truth of what worked and what broke.
    feat commits = positive examples. fix commits = negative examples (what
    went wrong) + positive example (how it was resolved).
    """
    # WHY: use unique sentinel to delimit commits — survives multiline bodies.
    SENTINEL = "==COMMIT_BOUNDARY=="
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                f"--max-count={limit}",
                f"--format={SENTINEL}%n%H%n%ad%n%s%n%b",
                "--date=short",
            ],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=15,
        )
    except Exception as e:
        print(f"  [git] ERROR: {e}")
        return 0

    count = 0
    for block in result.stdout.split(SENTINEL):
        block = block.strip()
        if not block:
            continue
        lines_b = block.splitlines()
        if len(lines_b) < 3:
            continue
        sha = lines_b[0].strip()
        date = lines_b[1].strip()
        subject = lines_b[2].strip()
        body = "\n".join(lines_b[3:]).strip()

        # Only process meaningful commit types
        commit_type = None
        if subject.startswith("feat:") or subject.startswith("feat("):
            commit_type = "feat"
        elif subject.startswith("fix:") or subject.startswith("fix("):
            commit_type = "fix"
        elif subject.startswith("refactor:"):
            commit_type = "refactor"
        else:
            continue

        # Emoji + tag mapping
        emoji = {"feat": "✅", "fix": "🐛", "refactor": "♻️"}[commit_type]
        tag = {
            "feat": "feat positive-example",
            "fix": "fix negative-example",
            "refactor": "refactor",
        }[commit_type]

        title = f"{emoji} {subject}"
        slug = f"git-{commit_type}-{sha[:8]}"

        lines = [
            f"# {title}",
            f"",
            f"#raw #{commit_type} #git {' #'.join(tag.split()[1:])}",
            f"",
            f"**Date:** {date}  ",
            f"**Commit:** `{sha[:12]}`  ",
            f"",
            f"---",
            f"",
        ]

        if commit_type == "fix":
            lines += [
                "## What went wrong",
                "",
                body if body else subject,
                "",
                "## How it was fixed",
                "",
                subject,
                "",
            ]
        else:
            lines += [
                "## What was built",
                "",
                subject,
                "",
            ]
            if body:
                lines += ["## Details", "", body, ""]

        content = "\n".join(lines)
        _write_raw(slug, content)
        count += 1

    print(f"  [git] {count} commits → raw/")
    return count


# ── source 2: CogniML Skills ──────────────────────────────────────────────────


def sync_cogniml_skills() -> int:
    """Fetch all CogniML skills and create wiki entries.

    WHY: CogniML stores structured retrospectives (root_cause, fix_summary,
    evidence_strength). Converting them to wiki entries makes them searchable
    in Obsidian graph view and linkable via [[wikilinks]].
    """
    data = _cogniml_get("/api/skills?limit=200")
    if not data:
        print("  [cogniml] API unavailable — skipping")
        return 0

    skills = data.get("skills", [])
    count = 0

    for skill in skills:
        skill_id = skill.get("skill_id", "")[:8]
        title = skill.get("title", "Untitled")
        body = skill.get("body", "")
        tags = skill.get("tags", [])
        domain = skill.get("domain", "")
        evidence = skill.get("evidence_strength", "unknown")
        status = skill.get("status", "draft")
        confidence = skill.get("confidence", 0.0)
        created = skill.get("created_at", "")[:10] if skill.get("created_at") else ""

        # Determine sentiment from failure_cause presence
        has_failure = skill.get("failure_cause") is not None
        emoji = "🐛" if has_failure else "✅"
        tag_sentiment = "negative-example fix" if has_failure else "positive-example"

        all_tags = ["cogniml", "retrospective"] + list(tags) + tag_sentiment.split()
        tag_str = " #".join(all_tags)

        slug = f"cogniml-skill-{skill_id}"

        failure_section = ""
        if has_failure:
            fc = skill["failure_cause"]
            failure_section = (
                f"## Failure Cause\n\n"
                f"**Primary:** {fc.get('primary', '—')}  \n"
                f"**Description:** {fc.get('description', '—')}  \n"
                f"**Resolution:** {fc.get('resolution', '—')}  \n\n"
            )

        applicability = skill.get("applicability_conditions", [])
        apply_section = ""
        if applicability:
            apply_section = (
                "## When this applies\n\n" + "\n".join(f"- {a}" for a in applicability) + "\n\n"
            )

        content = (
            f"# {emoji} {title}\n\n"
            f"#raw #{tag_str}\n\n"
            f"**Domain:** {domain}  \n"
            f"**Evidence:** {evidence}  \n"
            f"**Confidence:** {confidence:.0%}  \n"
            f"**Status:** {status}  \n"
            f"**Created:** {created}  \n\n"
            f"---\n\n"
            f"{failure_section}"
            f"{apply_section}"
            f"## Knowledge\n\n"
            f"{body}\n"
        )

        _write_raw(slug, content)
        count += 1

    print(f"  [cogniml] {count} skills → raw/")
    return count


# ── source 3: patterns.md ─────────────────────────────────────────────────────


def split_patterns() -> int:
    """Split patterns.md [AVOID]/[REPEAT] entries into individual wiki notes.

    WHY: patterns.md is a flat list — hard to navigate in Obsidian.
    Individual notes become graph nodes, linkable from any wiki entry.
    """
    patterns_path = MEMORY_DIR / "patterns.md"
    if not patterns_path.exists():
        print("  [patterns] patterns.md not found — skipping")
        return 0

    content = patterns_path.read_text(encoding="utf-8")
    count = 0

    # WHY: patterns.md uses ### headings with [AVOID]/[REPEAT] tags
    # followed by bullet-point body — parse as blocks, not line-by-line.
    blocks = re.split(r"\n(?=###\s)", content)
    for block in blocks:
        block = block.strip()
        if not block.startswith("###"):
            continue

        block_lines = block.splitlines()
        header_line = block_lines[0]
        body_lines = block_lines[1:]

        tag = None
        emoji = ""
        if "[AVOID]" in header_line:
            tag = "avoid negative-example"
            emoji = "⛔"
        elif "[REPEAT]" in header_line:
            tag = "repeat positive-example"
            emoji = "✅"
        else:
            continue

        clean_title = re.sub(
            r"\[\d{4}-\d{2}-\d{2}\]|\[AVOID\]|\[REPEAT\]|\[×\d+\]|###", "", header_line
        ).strip()
        if not clean_title or len(clean_title) < 5:
            continue

        count_match = re.search(r"\[×(\d+)\]", header_line)
        occurrences = int(count_match.group(1)) if count_match else 1
        body = "\n".join(l.strip() for l in body_lines if l.strip())

        slug = f"pattern-{re.sub(r'[^\w]', '-', clean_title[:40]).lower()}"
        note = (
            f"# {emoji} {clean_title}\n\n"
            f"#raw #{' #'.join(tag.split())} #pattern\n\n"
            f"**Occurrences:** {occurrences}×  \n\n"
            f"---\n\n"
            f"{body}\n"
        )
        _write_raw(slug, note)
        count += 1

    print(f"  [patterns] {count} patterns → raw/")
    return count


# ── source 4: retrospectives from activeContext ───────────────────────────────


def mine_retrospectives() -> int:
    """Extract Worked/Avoid/Next items from activeContext.md retrospectives."""
    # WHY: retros live in project activeContext, not global ~/.claude/memory/
    candidates = [
        Path("D:/Claude-cod-top-2026/.claude/memory/activeContext.md"),
        Path(".claude/memory/activeContext.md"),
        MEMORY_DIR / "activeContext.md",
    ]
    ctx_path = next((p for p in candidates if p.exists()), None)
    if not ctx_path:
        print("  [retro] activeContext.md not found — skipping")
        return 0

    content = ctx_path.read_text(encoding="utf-8")
    count = 0

    # Find all Retrospective sections
    retro_blocks = re.findall(r"## Retrospective \[([^\]]+)\](.*?)(?=## |\Z)", content, re.DOTALL)

    for date_str, block in retro_blocks:
        worked = re.findall(r"- Worked: (.+)", block)
        avoid = re.findall(r"- Avoid: (.+)", block)
        nexts = re.findall(r"- Next: (.+)", block)

        if not (worked or avoid):
            continue

        slug = f"retro-{date_str.replace(' ', '-')}"
        lines = [
            f"# 🔄 Retrospective {date_str}",
            "",
            "#raw #retro #retrospective",
            "",
            f"**Date:** {date_str}  ",
            "",
            "---",
            "",
        ]

        if worked:
            lines += ["## ✅ What worked", ""]
            for w in worked:
                lines.append(f"- {w}")
            lines.append("")

        if avoid:
            lines += ["## ⛔ Avoid next time", ""]
            for a in avoid:
                lines.append(f"- {a}")
            lines.append("")

        if nexts:
            lines += ["## ➡️ Next", ""]
            for n in nexts:
                lines.append(f"- {n}")
            lines.append("")

        _write_raw(slug, "\n".join(lines))
        count += 1

    print(f"  [retro] {count} retrospectives → raw/")
    return count


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate Obsidian vault from multiple sources")
    parser.add_argument("--all", action="store_true", help="Run all sources")
    parser.add_argument("--git", action="store_true", help="Mine git history")
    parser.add_argument("--cogniml", action="store_true", help="Sync CogniML skills")
    parser.add_argument("--patterns", action="store_true", help="Split patterns.md")
    parser.add_argument("--retro", action="store_true", help="Mine retrospectives")
    parser.add_argument("--repo", default=".", help="Git repo path (default: current dir)")
    parser.add_argument("--limit", type=int, default=200, help="Max git commits to process")
    args = parser.parse_args()

    if not any([args.all, args.git, args.cogniml, args.patterns, args.retro]):
        parser.print_help()
        return

    print(f"\n🧠 Populating Obsidian vault → {RAW_DIR}\n")
    total = 0

    if args.all or args.git:
        total += mine_git_history(Path(args.repo), args.limit)

    if args.all or args.cogniml:
        total += sync_cogniml_skills()

    if args.all or args.patterns:
        total += split_patterns()

    if args.all or args.retro:
        total += mine_retrospectives()

    print(f"\n✅ Total: {total} notes written to raw/")
    print("   Run session_save.py (or end a Claude Code session) to convert raw/ → wiki/")
    print(f"   Or run: python hooks/session_save.py")


if __name__ == "__main__":
    main()
