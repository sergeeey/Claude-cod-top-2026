#!/usr/bin/env python3
"""PreToolUse hook: remind to search locally before using MCP.

Outputs a soft nudge via stderr when an MCP tool is called,
reminding Claude to try Read/Grep/Glob first.
Excludes basic-memory and sequential-thinking (utility MCPs).

Matcher: mcp__context7|mcp__claude_ai|mcp__ollama|mcp__ncbi|mcp__uniprot|mcp__pubmed
"""

import sys

from utils import parse_stdin

# Utility MCPs that don't need locality check
EXEMPT_MCPS = {
    "mcp__basic-memory",
    "mcp__sequential-thinking",
    "mcp__playwright",
}


def main():
    data = parse_stdin()
    if not data:
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    if not tool_name.startswith("mcp__"):
        sys.exit(0)

    # Check if this MCP is exempt
    mcp_prefix = "__".join(tool_name.split("__")[:2])
    if mcp_prefix in EXEMPT_MCPS:
        sys.exit(0)

    print(
        f"[mcp-locality] Before using {tool_name}: "
        f"did you try local Read/Grep/Glob first? "
        f"Local search costs 0 tokens and 0 latency. "
        f"Use MCP only if local search didn't find the answer.",
        file=sys.stderr,
    )

    sys.exit(0)


if __name__ == "__main__":
    main()
