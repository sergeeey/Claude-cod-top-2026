#!/usr/bin/env python3
"""
Hypothesis Router Hook — автоматическое добавление гипотез в Tracker

Trigger: PostToolUse:Write
Condition: frontmatter содержит type: hypothesis
Action:
  1. Определить тип файла (hypothesis/analysis/experiment)
  2. Положить в правильную папку
  3. Обновить Hypothesis Tracker.md
  4. Инкрементировать Summary Stats
"""

import re
from datetime import datetime
from pathlib import Path

MEMORY_PATH = Path.home() / ".claude" / "memory"
TRACKER_PATH = MEMORY_PATH / "knowledge" / "research" / "hypotheses" / "Hypothesis Tracker.md"


def extract_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown file."""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    try:
        result = {}
        for line in match.group(1).strip().splitlines():
            if ":" in line and not line.startswith(" "):
                key, _, val = line.partition(":")
                result[key.strip()] = val.strip()
        return result
    except Exception:
        return {}


def determine_file_type(frontmatter: dict, filename: str) -> str:
    """Determine if file is hypothesis, analysis, or experiment."""
    file_type = frontmatter.get("type", "").lower()

    # Explicit type
    if file_type in ["hypothesis", "analysis", "experiment-protocol", "experiment"]:
        return file_type.replace("experiment-protocol", "experiment")

    # Infer from filename
    if "critical review" in filename.lower() or "analysis" in filename.lower():
        return "analysis"
    if "protocol" in filename.lower() or "experiment" in filename.lower():
        return "experiment"

    # Default: hypothesis
    return "hypothesis"


def get_target_directory(file_type: str) -> Path:
    """Get target directory based on file type."""
    research_path = MEMORY_PATH / "knowledge" / "research"

    if file_type == "hypothesis":
        return research_path / "hypotheses"
    elif file_type == "analysis":
        return research_path / "analysis"
    elif file_type == "experiment":
        return research_path / "experiments"
    else:
        return research_path / "hypotheses"  # default


def extract_hypothesis_metadata(frontmatter: dict, content: str) -> dict:
    """Extract metadata for Tracker entry."""
    # Get title from frontmatter or first heading
    title = frontmatter.get("title")
    if not title:
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = match.group(1) if match else "Untitled Hypothesis"

    return {
        "title": title,
        "score": frontmatter.get("discovery_score") or frontmatter.get("confidence", "N/A"),
        "status": frontmatter.get("status", "NOT STARTED").upper(),
        "date": frontmatter.get("created", datetime.now().strftime("%Y-%m-%d")),
        "domain": ", ".join(frontmatter.get("tags", [])[:3]),  # first 3 tags
        "kill_criterion": extract_kill_criterion(content),
    }


def extract_kill_criterion(content: str) -> str:
    """Extract falsification criterion from content."""
    # Look for patterns like "Критерий фальсификации", "Kill criterion", "Hypothesis ложна если"
    patterns = [
        r"(?:Критерий фальсификации|Kill criterion|Falsification criterion):?\s*(.+?)(?:\n\n|\Z)",
        r"Гипотеза ложна если:?\s*(.+?)(?:\n\n|\Z)",
        r"Hypothesis ложна:?\s*(.+?)(?:\n\n|\Z)",
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()[:100]  # first 100 chars

    return "Not specified"


def update_hypothesis_tracker(metadata: dict, filename: str):
    """Add entry to Hypothesis Tracker."""
    if not TRACKER_PATH.exists():
        print(f"[hypothesis_router] Tracker not found at {TRACKER_PATH}")
        return

    tracker_content = TRACKER_PATH.read_text(encoding="utf-8")

    # Find insertion point (before ## Portfolio Analytics)
    insertion_marker = "## Portfolio Analytics"
    if insertion_marker not in tracker_content:
        print("[hypothesis_router] Insertion marker not found in Tracker")
        return

    # Create new entry
    new_entry = f"""- [[{filename.replace(".md", "")}]] — **NEW {metadata["date"]}**
- Score: {metadata["score"]}. Focus: {metadata.get("focus", "Multi-agent systems")}
- Kill criterion: {metadata["kill_criterion"]}
- Status: {metadata["status"]}

"""

    # Insert before Portfolio Analytics
    parts = tracker_content.split(insertion_marker)
    updated_content = parts[0] + new_entry + insertion_marker + parts[1]

    # Update Summary Stats
    updated_content = increment_summary_stats(updated_content)

    # Write back
    TRACKER_PATH.write_text(updated_content, encoding="utf-8")
    print(f"[hypothesis_router] ✅ Added '{filename}' to Hypothesis Tracker")


def increment_summary_stats(content: str) -> str:
    """Increment total hypotheses count in Summary Stats."""
    # Find "Total hypotheses: N"
    pattern = r"(- Total hypotheses: )(\d+)"
    match = re.search(pattern, content)

    if match:
        current_count = int(match.group(2))
        new_count = current_count + 1
        content = re.sub(pattern, f"\\g<1>{new_count}", content)
        print(f"[hypothesis_router] Updated count: {current_count} → {new_count}")

    # Update "NOT STARTED" count
    pattern_not_started = r"(- NOT STARTED: )(\d+)"
    match_ns = re.search(pattern_not_started, content)
    if match_ns:
        current_ns = int(match_ns.group(2))
        content = re.sub(pattern_not_started, f"\\g<1>{current_ns + 1}", content)

    # Update timestamp
    today = datetime.now().strftime("%Y-%m-%d")
    if "---\n*Last updated:" in content:
        content = re.sub(
            r"---\n\*Last updated: .+?\*",
            f"---\n*Last updated: {today} — Auto-updated by hypothesis_router*",
            content,
        )
    else:
        # Add timestamp if not exists
        content += f"\n\n---\n*Last updated: {today} — Auto-updated by hypothesis_router*\n"

    return content


def main(event: dict) -> dict:
    """
    Hook entry point.

    Event structure (from PostToolUse:Write):
    {
        "tool": "Write",
        "file_path": "C:/Users/serge/.claude/memory/...",
        "content": "...",
    }
    """
    file_path = Path(event.get("file_path", ""))
    content = event.get("content", "")

    if not file_path or not content:
        return {"result": "skip", "message": "No file_path or content"}

    # Check if file is in memory/
    if ".claude/memory" not in str(file_path):
        return {"result": "skip", "message": "Not in memory/"}

    # Extract frontmatter
    frontmatter = extract_frontmatter(content)

    # Check if type: hypothesis (or related)
    file_type = determine_file_type(frontmatter, file_path.name)

    if file_type not in ["hypothesis", "analysis", "experiment"]:
        return {
            "result": "skip",
            "message": f"Not a hypothesis-related file (type={frontmatter.get('type')})",
        }

    # Extract metadata
    metadata = extract_hypothesis_metadata(frontmatter, content)

    # Update Tracker (only for hypotheses, not analysis/experiments)
    if file_type == "hypothesis":
        try:
            update_hypothesis_tracker(metadata, file_path.name)
        except Exception as e:
            return {"result": "error", "message": f"Failed to update Tracker: {e}"}

    return {
        "result": "success",
        "message": f"[hypothesis_router] ✅ Processed {file_type}: {file_path.name}",
        "metadata": metadata,
    }


if __name__ == "__main__":
    # Test mode
    import sys

    if len(sys.argv) > 1:
        test_file = Path(sys.argv[1])
        if test_file.exists():
            result = main(
                {"file_path": str(test_file), "content": test_file.read_text(encoding="utf-8")}
            )
            print(result)
