# Configuration Architecture

## 6 Loading Layers

### Layer 1: CLAUDE.md (Red Zone)
**Cost**: paid on EVERY message; the shipped `claude-md/CLAUDE.md` template is ~2.1k tokens (125 lines, 8.5 KB; estimated as bytes/4).
**Rule**: keep it short (the shipped template is 125 lines). Everything not always needed goes into rules or skills.

Contains:
- Identity (who you are, language, style)
- Workflow (80/20, Plan-First, Stuck Detection)
- Self-Review (4-point checklist for plans and 1-2 file changes)
- Integrity (confirmation required for irreversible operations)
- Agents (13 active: 5 core + 8 extended, plus 3 teams)
- Evidence Policy (short version)
- Pointers to the modular rules

### Layer 2: Rules (Yellow Zone)
**Cost**: always-on unless a rule is `paths:`-scoped (only `coding-style` and `testing` are); ~58k tokens if all 21 are installed (`minimal` profile: 2 rules ≈ 2k), estimated as bytes/4.

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
**Cost**: ~150 tokens per installed skill (name + description only; measured average of 621 characters over the 99 of 135 shipped SKILL.md files whose frontmatter parses as YAML, estimated as chars/4 — the loader may truncate long descriptions). SKILL.md is loaded on trigger.

Each skill has YAML frontmatter with lifecycle:
- `STATUS`: draft → confirmed → review → deprecated
- `CONFIDENCE`: low → medium → high
- `VALIDATED`: date of last verification

### Layer 4: Agents (Green Zone)
**Cost**: agent names and descriptions are listed in the Agent tool's description on every message; an agent's full definition is read only when it is called.

13 agents (+ 3 teams) cover: architecture, code, review, tests, search, security, learning, verification.

### Layer 5: Hooks (Free Zone)
**Cost**: 0 tokens. Executed as OS processes, consume no context.

101 hooks across 25 event types = deterministic automation: every registered hook fires
100% of the time (unlike instructions in CLAUDE.md, which the model can choose to ignore).
**Firing is not the same as blocking** — only 7 of the 95 can actually deny a tool call
(`escalation: block` in `hooks/registry.yaml`); most fire, observe or warn, and never stop
anything. See `docs/hook-control-matrix.md` for the full PREVENT/WARN/OBSERVE/Dormant/Library
breakdown.

### Layer 6: MCP Profiles (Management)
Each MCP server adds ~1000-2000 tokens of tool definitions.
Profiles allow connecting only the servers needed.

## Progressive Disclosure Principle

```
Message 1: CLAUDE.md loaded (~2.1k tokens)
Message 2: User writes code → rules/coding-style.md (~330 tokens)
Message 3: Mentions tests → rules/testing.md (~870 tokens)
Message 4: Trigger "audit" → skills/security-audit/SKILL.md (~920 tokens)
```

Without Progressive Disclosure every shipped rule and skill would load immediately — skill metadata alone is ~15k tokens (measured over 99 of 135 skills; ~21k extrapolated to all 135), plus the rule bodies. Only `coding-style` and `testing` are `paths:`-scoped; the other rules are always-on, so rule loading is not zero-cost.

## Red Zone vs Green Zone

| Zone | What | Cost | Rule |
|------|------|------|------|
| Red | CLAUDE.md | ~2.1k tok/msg | Minimum lines, maximum impact |
| Yellow | Rules | always-on unless `paths:`-scoped (2 of 21); ~58k tok if all installed | See `claude-md/CLAUDE.md` § RULES |
| Green | Skills, Agents | skill metadata always (~150 tok each); skill body on trigger (~2.5k avg) | On trigger/call |
| Free | Hooks, Scripts | 0 tok | Always execute, cost no tokens |
