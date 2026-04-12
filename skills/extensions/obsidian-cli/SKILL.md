---
name: obsidian-cli
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-04-12]
  Obsidian CLI tools: obsidian:// URI protocol, Local REST API plugin,
  mcpvault MCP server, populate_vault.py script, scripted vault operations.
  Triggers: obsidian cli, obsidian api, obsidian uri, local rest api,
  obsidian mcp, vault automation, obsidian script, obsidian terminal.
effort: minimal
tokens: ~250
---

# Obsidian CLI & Automation

## obsidian:// URI Protocol

Open notes, searches, graphs directly from terminal or scripts:

```bash
# Open a specific note
open "obsidian://open?vault=MyVault&file=projects%2Fmy-note"

# Create new note with content
open "obsidian://new?vault=MyVault&name=Quick%20Note&content=Hello%20World"

# Search
open "obsidian://search?vault=MyVault&query=python%20async"

# Open daily note
open "obsidian://daily?vault=MyVault"
```

On Windows use `start` instead of `open`:
```cmd
start obsidian://open?vault=MyVault&file=Note%20Name
```

## Local REST API Plugin

Install "Local REST API" from Obsidian community plugins. Exposes HTTP API at `localhost:27124`.

```bash
# Get vault info
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:27124/

# Read a note
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:27124/vault/projects/my-note.md"

# Create/update a note
curl -X PUT \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: text/markdown" \
  -d "# New Note\n\nContent here." \
  "http://localhost:27124/vault/inbox/new-note.md"

# Search
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:27124/search/simple/?query=python&contextLength=100"
```

## mcpvault — MCP Server for Claude Code

```bash
# Add to Claude Code
claude mcp add obsidian-vault -- npx -y @bitbonsai/mcpvault

# Set env vars (in .env or shell)
OBSIDIAN_API_KEY=your_token_here
OBSIDIAN_HOST=http://localhost:27124
```

Available MCP tools: `read_note`, `write_note`, `patch_note`, `search_notes`,
`list_all_tags`, `list_directory`, `get_notes_info`, `move_note`, etc.

## populate_vault.py — Bulk Seed Script

Mines 4 sources and pushes to Obsidian via Local REST API:

```bash
# Seed from all sources (git history + CogniML + patterns + retros)
python D:/Claude-cod-top-2026/scripts/populate_vault.py --all

# Individual sources
python populate_vault.py --git      # git history → wiki entries
python populate_vault.py --cogniml  # CogniML skills → wiki entries
python populate_vault.py --patterns # patterns.md blocks → notes
python populate_vault.py --retro    # retrospectives → timeline
```

## Windows Task Scheduler (daily refresh)

```cmd
schtasks /create /tn "ObsidianVaultRefresh" /tr \
  "C:\miniconda3\envs\ape311\python.exe D:\Claude-cod-top-2026\scripts\populate_vault.py --all" \
  /sc daily /st 09:00 /f
```

## Quick Raw Note from Terminal

```bash
# Dump quick thought to raw inbox (processed at session end by session_save.py)
echo "# Idea: retry logic\n\nUse exponential backoff. #architecture" \
  >> ~/.claude/memory/raw/ideas.md
```

## Tips
- Local REST API token is in: Obsidian Settings → Local REST API → API Key
- mcpvault auto-discovers vault if `OBSIDIAN_HOST` is set
- URI protocol requires Obsidian to be running
- populate_vault.py is idempotent — safe to run multiple times
