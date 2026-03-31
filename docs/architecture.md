# Configuration Architecture

## 6 Loading Layers

### Layer 1: CLAUDE.md (Red Zone)
**Cost**: ~500 tokens on EVERY message.
**Rule**: 70 lines maximum. Everything not always needed goes into rules or skills.

Contains:
- Identity (who you are, language, style)
- Workflow (80/20, Plan-First, 4-tier Stuck Detection)
- Evidence Policy (short version)
- Agents (9 active + 3 teams with model/memory/isolation assignments)
- Self-Review checklist (for plans and 1-2 file changes)
- Pointers to 8 modular rules

### Layer 2: Rules (Yellow Zone)
**Cost**: 0 tokens until activated. Loaded based on task context.

| File | Lines | Load Trigger |
|------|-------|--------------|
| coding-style.md | 20 | Writing/editing code |
| security.md | 17 | Working with data, API, deployment |
| testing.md | 11 | Tests, pytest, coverage |
| integrity.md | 32 | Factual claims, recommendations |
| memory-protocol.md | 32 | Git commit, end of session, checkpoint |
| context-loading.md | 45 | Agent invocation (agents read shared state) |
| permissions.md | 34 | Permission decisions, deny patterns |
| mentor-protocol.md | 20 | Educational tips (START TIP + END INSIGHT) |

### Layer 3: Skills (Green Zone)
**Cost**: ~100 tokens total (name + description only). SKILL.md is loaded on trigger.

8 core + 8 extension skills = 16 total.

Each skill has YAML frontmatter with lifecycle:
- `STATUS`: draft → confirmed → review → deprecated
- `CONFIDENCE`: low → medium → high
- `VALIDATED`: date of last verification

New in v3.0.0:
- **Shell preprocessing** — 3 skills inject live data (`git status`, `pytest --co`, `cat references.md`)
- **Path-based activation** — 3 extension skills trigger on file patterns (`**/*auth*`, `**/*variant*`, `**/*sentinel*`)
- **Effort levels** — domain skills use `effort: max` for thorough analysis

### Layer 4: Agents (Green Zone)
**Cost**: 0 tokens until called. Definitions are loaded by the Agent tool.

9 active agents + 3 teams cover: architecture, code, review, tests, search, security, learning, verification.

New in v3.0.0:
- **Persistent memory** — four agents (reviewer, sec-auditor, navigator, explorer) carry context between sessions via `memory:` field
- **Worktree isolation** — builder and tester operate in isolated git worktrees
- **Agent Teams** — review-squad, build-squad, research-squad for parallel workflows
- **Restricted spawning** — navigator can only spawn builder/reviewer/tester; architect only builder

### Layer 5: Hooks (Free Zone)
**Cost**: 0 tokens. Executed as OS processes, consume no context.

30 hooks (Python scripts) across 14 events = deterministic automation. Unlike instructions in CLAUDE.md, hooks execute 100% of the time.

New in v3.0.0:
- **7 new events**: PermissionRequest, FileChanged, CwdChanged, SubagentStart, SubagentStop, ConfigChange, TeammateIdle
- **Async wrapper** — non-blocking execution for slow hooks (post_format, pattern_extractor, session_save, webhook_notify)
- **31 deny rules** in static permissions (was 17)

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

Without Progressive Disclosure all 8 rules + 16 skills would load immediately = +5000 tokens/message.

## Red Zone vs Green Zone

| Zone | What | Cost | Rule |
|------|------|------|------|
| Red | CLAUDE.md | ~500 tok/msg | Minimum lines, maximum impact |
| Yellow | Rules (8 files) | 0 → 100-300 tok | Based on task context |
| Green | Skills (16), Agents (9+3) | 0 → 200-500 tok | On trigger/call |
| Free | Hooks (29), Scripts | 0 tok | Always execute, cost no tokens |
