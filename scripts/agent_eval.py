#!/usr/bin/env python3
"""Agent evaluation logger.

Appends agent performance scores to ~/.claude/memory/agent_scores.md.
Called manually or via post-agent hook.

Usage:
  python agent_eval.py <agent_name> <score_1_5> [comment]

Example:
  python agent_eval.py reviewer 5 "caught real bug in auth middleware"
  python agent_eval.py explorer 2 "missed obvious match in utils/"
"""

import sys
from datetime import datetime
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python agent_eval.py <agent_name> <score_1-5> [comment]")
        sys.exit(1)

    agent = sys.argv[1]
    score = int(sys.argv[2])
    comment = sys.argv[3] if len(sys.argv) > 3 else ""

    if not 1 <= score <= 5:
        print("Score must be 1-5")
        sys.exit(1)

    scores_file = Path.home() / ".claude" / "memory" / "agent_scores.md"
    scores_file.parent.mkdir(parents=True, exist_ok=True)

    # Create header if new file
    if not scores_file.exists() or scores_file.stat().st_size == 0:
        scores_file.write_text(
            "# Agent Performance Scores\n\n"
            "| Date | Agent | Score | Comment |\n"
            "|------|-------|-------|---------|\n",
            encoding="utf-8",
        )

    # Append score
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    stars = "★" * score + "☆" * (5 - score)
    line = f"| {date} | {agent} | {stars} | {comment} |\n"

    with open(scores_file, "a", encoding="utf-8") as f:
        f.write(line)

    print(f"Logged: {agent} = {stars} ({score}/5)")

    # Show summary if enough data
    lines = scores_file.read_text(encoding="utf-8").strip().split("\n")
    data_lines = [l for l in lines if l.startswith("| 2") and "|" in l]

    if len(data_lines) >= 5:
        from collections import defaultdict

        totals: dict[str, list[int]] = defaultdict(list)
        for dl in data_lines:
            parts = [p.strip() for p in dl.split("|") if p.strip()]
            if len(parts) >= 3:
                name = parts[1]
                star_count = parts[2].count("★")
                if star_count > 0:
                    totals[name].append(star_count)

        print("\n--- Agent averages ---")
        for name, scores_list in sorted(totals.items(), key=lambda x: -sum(x[1]) / len(x[1])):
            avg = sum(scores_list) / len(scores_list)
            print(f"  {name:15s} {avg:.1f}/5  ({len(scores_list)} evals)")


if __name__ == "__main__":
    main()
