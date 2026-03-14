# MCP Profiles — Server Management

## The Problem

Each MCP server adds ~1000-2000 tokens of tool definitions to the context
on every message. With 16 servers that is ~20,000 tokens of dead weight.

## Solution: Profiles

Connect only the servers needed for the current task.

## 3 Profiles

### core.json (default)
5 servers for everyday work:
- **context7** — library documentation
- **basic-memory** — structured memory
- **sequential-thinking** — reasoning chains
- **playwright** — browser automation
- **ollama** — local inference

### science.json
Core + scientific servers:
- **ncbi-datasets** — NCBI genomic data
- **uniprot** — protein databases
- **pubmed-mcp** — scientific publications

### deploy.json
Core + deployment servers:
- **vercel** — frontend deployment
- **netlify** — static sites
- **supabase** — DB and auth
- **sentry** — error monitoring

## Switching

### PowerShell (Windows)
```powershell
~/.claude/mcp-profiles/switch-profile.ps1 science
```

### Bash (Linux/Mac)
```bash
cp ~/.claude/mcp-profiles/core.json ~/.claude/settings.local.json
```

### After Switching
**Claude Code must be restarted!** MCP servers are loaded at startup.

Verification: `claude mcp list`

## Creating Your Own Profile

1. Copy `core.json` as a base
2. Add/remove servers in the `permissions.allow` section
3. Save as `my-profile.json`
4. Switch: `switch-profile.ps1 my-profile`

## Important: .mcp.json vs settings.local.json

- `.mcp.json` — Cursor/Windsurf format (Claude Code does NOT read this)
- `settings.local.json` — Claude Code format
- Servers are added via: `claude mcp add -s user <name> -- <command> <args>`
- Verification: `claude mcp list`
