---
name: Feature Request
about: Suggest a new feature
title: "[FEATURE] "
labels: enhancement
assignees: ''
---

## Problem

What problem does this solve? Why is it needed?

## Proposed Solution

Describe the feature you'd like.

## Which layer?

- [ ] CLAUDE.md (core config, must stay under 60 lines)
- [ ] Rule (contextual instruction in `rules/`)
- [ ] Hook (deterministic Python guard in `hooks/`)
- [ ] Skill (domain knowledge in `skills/`)
- [ ] Agent (specialized subagent in `agents/`)
- [ ] MCP Profile (server grouping in `mcp-profiles/`)
- [ ] install.sh (installer logic)
- [ ] Documentation (docs/)
- [ ] Other

## Token Impact

Estimated token cost of the feature:
- Always loaded (CLAUDE.md): ~___ tokens
- On-context (rules): ~___ tokens
- On-trigger (skills): ~___ tokens
- Zero (hooks): 0 tokens

## Alternatives Considered

What other approaches did you consider?

## 80/20 Check

Does this feature deliver 80% of the value with 20% of the effort?
