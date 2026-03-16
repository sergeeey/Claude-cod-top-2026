---
name: mcp-installer
description: >
  [STATUS: confirmed] [CONFIDENCE: medium] [VALIDATED: 2026-03-12]
  Auto-search and install MCP servers via WebSearch + claude mcp add.
  Triggers: find MCP, connect server, new MCP, integration with.
---

# Skill: MCP Auto-Installer

## When to Load
When starting a new project or task that requires specialized tools (frameworks, APIs, databases) not available among the connected MCP servers.

## Triggers
- New project with an unfamiliar stack
- Task requires integration with an external service (Stripe, Firebase, Twilio...)
- Working with a framework without a connected MCP (React Native, Flutter, Django...)
- User explicitly asks to "find MCP for X"

## Workflow

### Step 1: Identify the Need
Based on the task, determine which MCP servers may help:
- Web/mobile app → UI framework MCP, database MCP, auth MCP
- API backend → database MCP, monitoring MCP
- Data science → jupyter MCP, database MCP
- DevOps → docker MCP, cloud provider MCP
- Bioinformatics → NCBI, UniProt, PubMed (already installed)

### Step 2: Search
```
WebSearch("mcpmarket.com <technology> MCP server")
WebSearch("github MCP server <technology> model context protocol")
```
IMPORTANT: mcpmarket.com blocks direct WebFetch (429). Search via WebSearch, read README via GitHub.

### Step 3: Evaluate Candidate
Before installing, check:
- [ ] GitHub stars > 10 (minimal validation)
- [ ] README contains installation instructions
- [ ] Last commit < 6 months ago (not abandoned)
- [ ] Dependencies: Node.js (npx/npm) or Python (pip/uvx)
- [ ] No suspicious permissions (filesystem access without reason)

### Step 4: Installation
Two paths in priority order:

**Path A — npx (preferred, no cloning):**
```bash
claude mcp add -s user <name> -- npx -y <package-name>
```
Verify connection:
```bash
claude mcp list 2>&1 | grep <name>
```
If "Failed to connect" → Path B.

**Path B — local install:**
```bash
cd /c/Users/serge/mcp-servers
git clone <repo-url>
cd <repo-name>
npm install && npm run build   # for Node.js
# or
pip install -r requirements.txt  # for Python
```
Register:
```bash
# Node.js
claude mcp add -s user <name> -- node C:/Users/serge/mcp-servers/<repo>/build/index.js
# Python
claude mcp add -s user <name> -- python C:/Users/serge/mcp-servers/<repo>/server.py
```

**Path C — Python (uvx):**
```bash
claude mcp add -s user <name> -- uvx <package-name>
```

### Step 5: Verification
```bash
claude mcp list 2>&1 | grep <name>
```
Expected result: `<name>: ... - ✓ Connected`

If Failed:
1. Check entry point in package.json (`main`, `bin`, `type: module` → dist/)
2. Verify runtime (node/python) is available
3. Try running manually: `node <path>/index.js` — catch the error

### Step 6: Activation
MCP servers connect at session initialization.
Tell the user:
> "MCP server [name] is installed and registered. Run `/clear` to activate — after that the tools will be available."

## Installation Directory
All MCP servers install to: `C:/Users/serge/mcp-servers/<name>/`

## Already Installed Servers (do not duplicate)
Check before installing:
```bash
claude mcp list
```

Typically already connected:
- context7 — library documentation
- playwright — browser automation
- basic-memory — persistent memory
- sequential-thinking — reasoning chains
- ncbi-datasets — genomics (31 tools)
- uniprot — proteins (26 tools)
- pubmed-mcp — literature (5 tools)
- bioRxiv — preprints (plugin)
- ollama — local LLM (11 tools)
- sentry, linear, figma, supabase, vercel, netlify — cloud plugins

## Anti-patterns
- Do NOT install MCP if the task can be solved with built-in tools (WebSearch, Bash, Read)
- Do NOT install MCP with 0 stars and no README
- Do NOT install MCP requiring an API key the user doesn't have (ask first)
- Do NOT try to use MCP in the same session — a /clear is required
