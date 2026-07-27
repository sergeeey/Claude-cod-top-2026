# Agents — Local Rules

## Structure
Each agent is a single markdown file with YAML frontmatter + instruction body.

Required frontmatter fields:
```yaml
---
name: <agent-name>
description: <one-line — used for routing decisions>
tools: Read, Edit, Write, Bash, Glob   # list only what the agent needs
model: sonnet | opus | haiku
---
```

Optional fields: `maxTurns`, `isolation`, `effort`, `permissionMode`, `whenToUse`
- `whenToUse` — One-sentence trigger condition — used by dispatcher and skill-scout for agent routing.

## Context Protocol (every agent must do this)
Read `.claude/memory/activeContext.md` before taking any action.
Return results tagged with the context item they address.
Do NOT write to memory files directly — return results to orchestrator.

## Tool Scope — Minimum Viable
Only list tools the agent actually needs.
- Read-only agents: `Read, Glob, Grep`
- Builder agents: `Read, Edit, Write, Bash, Glob`
- Research agents: `Read, Glob, Grep, WebSearch, WebFetch`

## Teams (in teams/)
Teams run 2+ agents in parallel. Use for:
- `review-squad` — reviewer + sec-auditor simultaneously
- `build-squad` — builder + tester simultaneously
- `research-squad` — explorer + verifier simultaneously

## Adding a New Agent
1. Copy closest existing agent as template
2. Set minimum tool scope
3. Add context-loading step (read activeContext.md)
4. Register in README agents table
