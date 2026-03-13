# Claude Code Config v11.1

Battle-tested Claude Code configuration: Evidence Policy, 11 hooks, 10 skills, 13 agents, MCP profiles, PII redaction.
Proven on real projects: fraud detection, genomic analysis, satellite geology, financial platforms.

**[Русская документация / Russian docs](README.md)**

## Quick Start — 5 minutes to a working config

### Step 1: Clone
```bash
git clone https://github.com/sergeeey/Claude-cod-top-2026.git
cd Claude-cod-top-2026
```

### Step 2: Install
```bash
# Option A: Copy (stable, manual updates)
bash install.sh

# Option B: Symlinks (auto-update via git pull)
bash install.sh --link
```

### Step 3: Choose a profile

| Profile | What it installs | For whom |
|---------|-----------------|----------|
| **minimal** | CLAUDE.md + integrity.md + security.md | Try Evidence Policy |
| **standard** | + all rules + hooks + skills + agents | Daily work |
| **full** | + MCP profiles + PII redaction + memory | Full control |

### Step 4: Verify
```bash
claude
# Inside Claude Code:
/context
```

**Done.** Adapt `~/.claude/CLAUDE.md` (IDENTITY section) to your needs.

## Key Features

### Evidence Policy — Claude doesn't hallucinate

Every factual claim must be marked with evidence level:

| Marker | Meaning |
|--------|---------|
| `[VERIFIED]` | Checked with a tool (Read, Bash, test output) |
| `[DOCS]` / `[CODE]` | From documentation or source code |
| `[INFERRED]` | Logical deduction from verified facts |
| `[WEAK]` | Indirect evidence, analogy |
| `[CONFLICTING]` | Sources disagree — both listed |
| `[UNKNOWN]` | No confirmation — needs verification |

### 11 Hooks — Deterministic Guards

Hooks execute with 100% reliability (unlike CLAUDE.md instructions which are probabilistic):

| Hook | What it does |
|------|-------------|
| `read_before_edit` | Reminds to Read file before Edit (prevents hallucinated edits) |
| `pre_commit_guard` | Blocks commits to main branch |
| `pii_redact` | Strips PII (national IDs, phone, email) before external MCP calls |
| `mcp_locality_guard` | Reminds to search locally before calling MCP servers |
| `session_start` | Loads project context + auto-updates config repo |
| `plan_mode_guard` | Enforces planning mode for 3+ file changes |
| + 5 more | Deny patterns, commit memory, checkpoint warnings |

### 10 Skills — Domain Knowledge on Demand

Skills load only when triggered (~100 tokens idle, full content on activation):

- **tdd-workflow** — RED→GREEN→REFACTOR with rationalization prevention
- **routing-policy** — Task→skill→agent→tools decision matrix
- **security-audit** — PII checklist, SQL injection, compliance (Kazakhstan ARRFR)
- **brainstorming** — Socratic design with 2-3 alternatives and trade-offs
- **mentor-mode** — Extended pedagogical mode with real-world analogies
- And 5 more domain-specific skills

### 13 Agents — Specialized Workers

5 core agents (always available) + 8 extended (on explicit call):

| Agent | Model | Role |
|-------|-------|------|
| `navigator` | Opus | Architecture, planning, session start |
| `builder` | Sonnet | Code generation from spec |
| `reviewer` | Opus | Code review, bug hunting |
| `tester` | Sonnet | Test generation and execution |
| `explorer` | Sonnet | Codebase search |

### 80/20 Principle

Embedded throughout the system: navigator plans by 80/20, scope-guard blocks feature creep, brainstorming always offers the simplest option first. "What 20% of work gives 80% of the result?"

### Token Economy

| Layer | When loaded | Token cost |
|-------|-----------|------------|
| CLAUDE.md | Always | ~500 |
| Rules | On context match | ~200 each |
| Skills | On trigger | ~100 idle, ~500 active |
| Hooks | Never (Python) | 0 |

Total idle cost: ~800 tokens. Compare with monolithic configs at 3000-5000 tokens.

## Architecture

```
~/.claude/
├── CLAUDE.md          # Core config (~52 lines, always loaded)
├── rules/             # Contextual rules (5 files)
├── hooks/             # Python guards (11 scripts)
├── skills/            # Domain knowledge (10 skills)
├── agents/            # Specialized workers (13 agents)
├── scripts/           # PII redaction
├── mcp-profiles/      # MCP server groupings
├── memory/            # Session persistence
└── settings.json      # Hook registry + deny patterns
```

## Comparison

| Criterion | Ours v11.1 | superpowers (80K+) | everything-claude-code (35K+) |
|-----------|:---------:|:------------------:|:----------------------------:|
| Evidence Policy | **9/10** | 6/10 | 3/10 |
| Security & PII | **9/10** | 1/10 | 5/10 |
| Hooks automation | **9/10** | 3/10 | 7/10 |
| Domain skills | **9/10** | 2/10 | 4/10 |
| TDD enforcement | **9/10** | **9/10** | 5/10 |
| Memory system | **8/10** | 4/10 | 6/10 |
| Multi-platform | 3/10 | **9/10** | 6/10 |
| Community/OSS | 4/10 | **9/10** | **9/10** |

**Our strength**: depth of engineering (Evidence Policy, PII, hooks, security).
**Their strength**: breadth of adoption and community.

## Documentation

Full documentation in Russian: [docs/](docs/)

| Document | Description |
|----------|------------|
| [Architecture](docs/architecture.md) | 6-layer system design |
| [Evidence Policy](docs/evidence-policy.md) | Anti-hallucination protocol |
| [Hooks Guide](docs/hooks-guide.md) | All 11 hooks explained |
| [Skills Guide](docs/skills-guide.md) | Creating custom skills |
| [MCP Profiles](docs/mcp-profiles.md) | Server grouping and switching |
| [Anti-Patterns](docs/anti-patterns.md) | 8 common mistakes |
| [Troubleshooting](docs/troubleshooting.md) | 10-point diagnostic checklist |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines (bilingual).

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting policy.

## License

MIT
