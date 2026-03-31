# Configuration Architecture

## 6 Loading Layers

### Layer 1: CLAUDE.md (Red Zone)
**Cost**: ~500 tokens on EVERY message.
**Rule**: 80 lines maximum. Everything not always needed goes into rules or skills.

Contains:
- Identity (who you are, language, style)
- Workflow (80/20, Plan-First, Stuck Detection)
- Self-Review (4-point checklist for plans and 1-2 file changes)
- Integrity (confirmation required for irreversible operations)
- Agents (9 active: 5 core + 4 extended, plus 3 teams)
- Evidence Policy (short version)
- Pointers to 8 modular rules

### Layer 2: Rules (Yellow Zone)
**Cost**: 0 tokens until activated. Loaded based on task context.

| File | Lines | Load Trigger |
|------|-------|--------------|
| coding-style.md | 20 | Writing/editing code |
| security.md | 17 | Working with data, API, deployment |
| testing.md | 12 | Tests, pytest, coverage |
| integrity.md | 68 | Factual claims, recommendations |
| memory-protocol.md | 45 | Git commit, end of session, checkpoint |
| context-loading.md | 74 | Agent invocation (shared state protocol) |
| permissions.md | 34 | Permission decisions (auto-allow/deny/ask) |
| mentor-protocol.md | 27 | Educational content (organic mode v2) |

### Layer 3: Skills (Green Zone)
**Cost**: ~100 tokens total (name + description only). SKILL.md is loaded on trigger.

Each skill has YAML frontmatter with lifecycle:
- `STATUS`: draft → confirmed → review → deprecated
- `CONFIDENCE`: low → medium → high
- `VALIDATED`: date of last verification

### Layer 4: Agents (Green Zone)
**Cost**: 0 tokens until called. Definitions are loaded by the Agent tool.

9 agents (+ 3 teams) cover: architecture, code, review, tests, search, security, learning, verification.

### Layer 5: Hooks (Free Zone)
**Cost**: 0 tokens. Executed as OS processes, consume no context.

40 hooks across 25 event types = deterministic automation. Unlike instructions in CLAUDE.md,
hooks execute 100% of the time.

### Layer 6: MCP Profiles (Management)
Each MCP server adds ~1000-2000 tokens of tool definitions.
Profiles allow connecting only the servers needed.

## Progressive Disclosure Principle

```
Message 1: CLAUDE.md loaded (500 tokens)
Message 2: User writes code → rules/coding-style.md (200 tokens)
Message 3: Mentions tests → rules/testing.md (100 tokens)
Message 4: Trigger "audit" → skills/security-audit/SKILL.md (500 tokens)
```

Without Progressive Disclosure all 5 rules + 8 skills would load immediately = +3000 tokens/message.

## Red Zone vs Green Zone

| Zone | What | Cost | Rule |
|------|------|------|------|
| Red | CLAUDE.md | ~500 tok/msg | Minimum lines, maximum impact |
| Yellow | Rules | 0 → 100-300 tok | Based on task context |
| Green | Skills, Agents | 0 → 200-500 tok | On trigger/call |
| Free | Hooks, Scripts | 0 tok | Always execute, cost no tokens |
