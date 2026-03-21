#!/bin/bash
# MCP Profile Switcher for Claude Code (bash version)
# Usage: bash switch-profile.sh core|science|deploy

set -e

PROFILE="${1:-}"

if [ -z "$PROFILE" ] || [[ ! "$PROFILE" =~ ^(core|science|deploy)$ ]]; then
    echo "Usage: bash switch-profile.sh core|science|deploy"
    echo ""
    echo "Profiles:"
    echo "  core     Context7, basic-memory, sequential-thinking, playwright, ollama"
    echo "  science  core + ncbi-datasets, uniprot, pubmed-mcp"
    echo "  deploy   core + vercel, netlify, supabase, sentry"
    exit 1
fi

PROFILE_DIR="$HOME/.claude/mcp-profiles"
PROFILE_FILE="$PROFILE_DIR/$PROFILE.json"
CONFIG_FILE="$HOME/.claude.json"

if [ ! -f "$PROFILE_FILE" ]; then
    echo "Profile not found: $PROFILE_FILE" >&2
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Config not found: $CONFIG_FILE" >&2
    echo "Run 'claude' first to create the initial config." >&2
    exit 1
fi

# WHY: Use python for reliable JSON merging — jq is not always available.
# The script replaces the mcpServers key in .claude.json with the profile's mcpServers.
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "Python required for JSON merging. Install Python 3.8+." >&2
    exit 1
fi

$PYTHON_CMD -c "
import json, sys

config_path = sys.argv[1]
profile_path = sys.argv[2]

with open(config_path, 'r') as f:
    config = json.load(f)

with open(profile_path, 'r') as f:
    profile = json.load(f)

config['mcpServers'] = profile.get('mcpServers', {})

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')

server_count = len(profile.get('mcpServers', {}))
print(f'MCP profile switched to: {sys.argv[3]} ({server_count} servers)')
print('Restart Claude Code to apply changes.')
" "$CONFIG_FILE" "$PROFILE_FILE" "$PROFILE"
