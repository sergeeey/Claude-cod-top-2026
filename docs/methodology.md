# Claude Code Config — Full Methodology

How this configuration works end-to-end: from installation to daily workflow.

## Architecture: 6 Loading Layers

```
Layer 1: CLAUDE.md        ~500 tok/msg   Always loaded (core rules)
Layer 2: Rules (5 files)   0 tok         On-demand (coding, security, testing, integrity, memory)
Layer 3: Skills (7+6)      ~100 tok      Trigger-based (routing, TDD, brainstorming, ...)
Layer 4: Agents (9)        0 tok         Isolated context (navigator, builder, reviewer, ...)
Layer 5: Hooks (16)        0 tok         Deterministic Python guards (pre/post tool use)
Layer 6: MCP Profiles (3)  ~3000 tok     Switchable server sets (core/science/deploy)
```

**Design principle**: Only Layer 1 loads every message. Everything else loads on demand, saving 40-50% tokens vs monolithic configs.

---

## Layer 1: Core (CLAUDE.md — 70 lines, ~500 tokens)

Loaded **every message**. Contains:

- **Identity**: Senior technical mentor, Russian language, English code/terms
- **80/20 filter**: "Which 20% of work delivers 80% of results?" — checked before every action
- **Plan-First**: 3+ files = mandatory EnterPlanMode
- **Stuck Detection**: 3 failed attempts = STOP, report what was tried, suggest alternative
- **Evidence Policy**: Every factual claim tagged with confidence markers
- **Agent table**: 5 core agents with model assignments
- **Pointers**: To modular rules (loaded on demand)

## Layer 2: Rules (5 files, 0 tokens until needed)

| Rule | Loads when | What it does |
|------|-----------|-------------|
| `coding-style.md` | Writing/editing code | Python 3.11+, type hints, ruff format, structlog, React/TS strict |
| `security.md` | Data, API, deployment | PII never in logs, parameterized SQL only, secrets in env vars |
| `testing.md` | Tests, coverage | >=80% for business logic, TDD, Test Protection (never delete test to pass broken code) |
| `integrity.md` | Any factual claims | Evidence markers, Confidence Scoring, 10 rationalization antidotes |
| `memory-protocol.md` | Commit, session end | Project vs global memory, pattern tags, context overflow at 70% |

## Layer 3: Skills (7 core + 6 extensions)

Load **on trigger word** in user message. Only ~100 tokens of metadata loaded always.

### Core Skills (universal)

| Trigger | Skill | What happens |
|---------|-------|-------------|
| any task start | `routing-policy` | Routes: task type -> skill -> agent -> tools |
| "tests", "TDD", "coverage" | `tdd-workflow` | RED -> GREEN -> REFACTOR cycle |
| "think", "alternatives", "brainstorm" | `brainstorming` | 2-3 options with trade-offs, then choose |
| "worktree", "experiment" | `git-worktrees` | Isolated branch for experiments |
| "explain", "teach", "how does X work" | `mentor-mode` | Analogies from user's domain (security/finance) |
| "reference", "external docs" | `reference-registry` | External documentation lookup |
| "install MCP" | `mcp-installer` | Step-by-step MCP server setup |

### Extension Skills (domain-specific, installed on demand)

- `security-audit` — regulatory compliance, fraud detection (financial systems)
- `archcode-genomics` — ClinVar variant analysis, chromatin simulation
- `geoscan` — Satellite gold prospecting (Sentinel-2 indices)
- `notebooklm` — Google NotebookLM queries with browser automation
- `suno-music` — Suno AI music prompt generation
- `python-geodata` — rasterio/geopandas patterns

## Layer 4: Agents (9 active, isolated context)

Run in **subprocess** — zero tokens in main conversation.

### Strategic (Opus — 20% of tasks)

| Agent | When | What |
|-------|------|------|
| `navigator` | Session start, unclear priorities | 80/20 decomposition, impact/effort scoring |
| `architect` | Before new module or refactoring | Architecture proposal with justification |
| `reviewer` | After implementation, before commit | 3-pass review: spec -> quality -> adversarial |
| `verifier` | Config changes, unfamiliar packages | Prove claim is WRONG first (hallucination hypothesis) |
| `sec-auditor` | Working with data, logs, databases | PII masking, injection blocking, regulatory compliance |

### Workhorse (Sonnet — 80% of tasks, 5-10x cheaper)

| Agent | When | What |
|-------|------|------|
| `builder` | Architecture defined, need implementation | Code generation with type hints, tests, linting |
| `tester` | After business logic written | Happy path -> edge cases -> failures |
| `explorer` | Need to find something in codebase | Fast Glob/Grep/Read, structured report |
| `teacher` | User asks to explain concepts | Analogies, multiple perspectives |

### Dispatch pattern

```
Sequential (writes to same files):
  navigator -> architect -> builder -> tester -> reviewer -> commit

Parallel (read-only):
  reviewer + sec-auditor (run simultaneously)

Sonnet-first (80% savings):
  builder/tester/explorer run Sonnet
  Escalate to Opus only when needed (navigator/architect/reviewer)
```

## Layer 5: Hooks (16 Python scripts, 0 tokens)

**Deterministic** — execute 100% of the time (unlike CLAUDE.md instructions which Claude may skip).

### Before tool call (PreToolUse)

| Hook | Matcher | Action |
|------|---------|--------|
| `pre_commit_guard.py` | Bash | Block: rm -rf, push --force, DROP TABLE, chmod 777 |
| `input_guard.py` | mcp__* | Detect 7 prompt injection categories |
| `mcp_circuit_breaker.py` | mcp__* | Block MCP server after 3 failures (CLOSED->OPEN->HALF_OPEN) |
| `mcp_locality_guard.py` | mcp__context7, etc | "Did you try local search first?" |
| `redact.py` | external MCP | Mask PII: national IDs, phone, email, tokens, API keys (12 patterns) |
| `read_before_edit.py` | Edit\|Write | "Did you Read the file before editing?" |

### After tool call (PostToolUse)

| Hook | Matcher | Action |
|------|---------|--------|
| `post_format.py` | Edit\|Write | Auto-format: Python (ruff), JS/TS (prettier) |
| `plan_mode_guard.py` | Edit\|Write | Warn if 3+ files edited without a plan |
| `drift_guard.py` | Skill\|Agent | Check NOT NOW keywords from scope fence |
| `memory_guard.py` | Bash | Remind to update activeContext.md after commits |
| `checkpoint_guard.py` | Bash | Remind to checkpoint before rebase/migration |
| `post_commit_memory.py` | Bash | Auto-log commit to activeContext.md |
| `pattern_extractor.py` | Bash | Extract lesson from fix: commits into patterns.md |
| `mcp_circuit_breaker_post.py` | mcp__* | Record MCP success/failure for circuit state |

### Session lifecycle hooks

| Hook | Event | Action |
|------|-------|--------|
| `session_start.py` | SessionStart | Load activeContext.md into context |
| `pre_compact.py` | PreCompact | Save state before context compaction |
| `session_save.py` | Stop | Warn if memory is stale before exit |

### Command deny-list (17 patterns)

```
rm -rf $HOME/.claude/*    rm -rf /*              git push --force
git reset --hard          git clean -fd          git branch -D
DROP TABLE                DROP DATABASE          TRUNCATE TABLE
chmod 777                 npm publish            curl | bash
wget | bash               pip install --break-system-packages
```

## Layer 6: MCP Profiles

Switchable server sets to avoid loading unnecessary tools:

| Profile | Servers | Use case |
|---------|---------|----------|
| `core` | context7, basic-memory, sequential-thinking, playwright, ollama | Default daily work |
| `science` | core + ncbi-datasets, uniprot, pubmed-mcp | Bioinformatics research |
| `deploy` | core + vercel, netlify, supabase, sentry | Deployment and monitoring |

Switch:
```bash
bash ~/.claude/mcp-profiles/switch-profile.sh core
# or Windows:
powershell ~/.claude/mcp-profiles/switch-profile.ps1 core
```

---

## Session Lifecycle

### Phase 1: Session Start

```
session_start.py fires
  -> loads activeContext.md into context
  -> loads scope fence (if exists)
  -> Claude: "Continuing [task] or new goal?"
```

### Phase 2: Task Routing

`routing-policy` skill determines the path:

| Task type | Route |
|-----------|-------|
| Research/question | explorer agent -> if not found -> MCP (Context7, WebSearch) |
| Code change (1-2 files) | Read -> brief plan -> Edit -> test -> commit |
| Code change (3+ files) | EnterPlanMode -> navigator -> architect -> builder -> tester -> reviewer |
| TDD | tdd-workflow: RED (failing test) -> GREEN (minimal code) -> REFACTOR |
| Debugging | Read error -> explore -> hypothesis [INFERRED] -> verify [VERIFIED] -> fix |
| Security/compliance | security-audit skill -> reviewer -> check deny-list |

### Phase 3: Execution with Guard Rails

Every action passes through the hook pipeline:

```
User request
  -> routing-policy determines path
  -> PreToolUse hooks fire (block dangerous, mask PII, check MCP health)
  -> Tool executes
  -> PostToolUse hooks fire (format code, check plan, extract patterns)
  -> Result shown to user
```

### Phase 4: Code Review (before commit)

Reviewer agent runs 3 passes:

| Pass | Focus | Output |
|------|-------|--------|
| 1. Spec Compliance | Solves the task? Edge cases? No scope creep? | Checklist |
| 2. Code Quality | Types? DRY? Error handling? No debug statements? | Issue list |
| 3. Adversarial | ACCEPT / CHALLENGE / REJECT for each decision | Verdict |

Verdict: **READY** / **NEEDS FIXES** / **BLOCKED**

### Phase 5: Commit and Memory Update

```
git commit
  -> post_commit_memory.py: auto-logs to activeContext.md
  -> pattern_extractor.py: extracts lesson from fix: commits
  -> memory_guard.py: reminds to update context manually
```

### Phase 6: Context Overflow (70% threshold)

```
pre_compact.py saves state
  -> update activeContext.md with critical context
  -> /clear
  -> session_start.py reloads context
  -> continue working
```

### Phase 7: Session End

```
session_save.py fires
  -> warns if activeContext.md is stale
  -> user updates: activeContext.md, patterns.md, learning_log.md
```

---

## Evidence Policy

The anti-hallucination core. Every factual claim is marked:

| Marker | Meaning | Confidence |
|--------|---------|------------|
| `[VERIFIED]` | Confirmed with tool (Read, Bash, test output) | HIGH (>=0.8) |
| `[DOCS]` | From official documentation | HIGH |
| `[CODE]` | From project source code (file:line) | HIGH |
| `[INFERRED]` | Logical conclusion (reasoning chain stated) | MEDIUM (0.6-0.79) |
| `[WEAK]` | Indirect data, single source | LOW (0.4-0.59) |
| `[CONFLICTING]` | Sources contradict (both listed) | Requires resolution |
| `[UNKNOWN]` | No confirmation | Triggers verification |

**Core principle**: `[UNKNOWN]` is better than a false `[INFERRED]`.

### Hard rules

1. NO FABRICATION — do not invent metrics, versions, URLs
2. NO PHANTOM REFERENCES — verify files/packages exist before recommending
3. NO UNGROUNDED RECOMMENDATIONS — "best practice" needs a source
4. NO CONFIDENCE WITHOUT EVIDENCE — numbers from memory are capped at LOW

### Rationalization Prevention

10 common AI excuses and why they are wrong:

| Excuse | Counter |
|--------|---------|
| "I already know this API" | [MEMORY] != [VERIFIED]. Read the file. |
| "Tests are excessive for this" | Simple changes break most often. 1 test minimum. |
| "MCP will be faster" | Local tools = 0 tokens. Try first. |
| "No plan needed for 2 files" | Threshold is 3. Follow it. |
| "I'll write tests after" | Tests after = testing implementation, not requirements. RED first. |
| "Security check not needed, internal API" | Internal APIs are also vulnerable (lateral movement). |
| "Too simple for Evidence markers" | Simple claims can be wrong. [VERIFIED] takes 1 second. |
| "I'm 90% sure" | 10% errors = hundreds of bugs per year. Check. |
| "Sub-agents verified this" | Agents read docs, not code. Re-verify with grep/bash. |
| "User is in a hurry, skip review" | Skipping review = tech debt. Reviewer runs in 30 sec. |

---

## Memory System

### Project memory (per-project, goes in git)

```
<project>/.claude/memory/
  activeContext.md  — what we are doing now (current task, scope fence)
  decisions.md      — architectural decisions with rationale
  checkpoints/      — save points before risky operations
```

### Global memory (cross-project, persists forever)

```
~/.claude/memory/
  user_profile.md   — WHO (identity, domain, expertise)
  patterns.md       — WHAT works [REPEAT] / fails [AVOID] / [xN] counters
  learning_log.md   — WHAT was learned across projects
  goals.md          — WHERE we are heading
  decisions.md      — WHY cross-project decisions were made
```

### Pattern tags

| Tag | Meaning |
|-----|---------|
| `[REPEAT]` | Proven approach, use again |
| `[AVOID]` | Mistake or anti-pattern, do not repeat |
| `[xN]` | Occurrence counter. [x3] = seen 3 times, treat as hard rule |

### Scope Fence (drift prevention)

```markdown
## Scope Fence
- Goal: Build payment API
- Boundary: Backend only, no frontend
- Done when: All endpoints pass integration tests
- NOT NOW: Admin panel, email notifications, analytics
```

`drift_guard.py` checks NOT NOW keywords after every Skill/Agent call.

---

## Token Economy

| Component | Tokens/message | When |
|-----------|---------------|------|
| CLAUDE.md | ~500 | Always |
| Rules | 0-300 | On-demand |
| Skill metadata | ~100 | Always |
| Full SKILL.md | 0-200 | On trigger |
| Agents | 0 | Isolated subprocess |
| Hooks | 0 | Python runtime |
| MCP servers (core) | ~3000 | Always |
| **Total (typical)** | **~3500** | — |
| Monolithic config | 5000-7000 | Always |
| **Savings** | **40-50%** | — |

---

## Anti-Patterns Prevented

| # | Anti-Pattern | Protection |
|---|-------------|------------|
| 1 | Context overflow (rules buried) | 70-line core + modular rules + pre_compact.py |
| 2 | Hallucination loops | Evidence Policy + Stuck Detection + integrity.md |
| 3 | PII leakage | redact.py (12 patterns) + security.md |
| 4 | Dangerous commands | pre_commit_guard.py (17 deny patterns) |
| 5 | MCP server failures | circuit_breaker (CLOSED/OPEN/HALF_OPEN) |
| 6 | Prompt injection via MCP | input_guard.py (7 detection categories) |
| 7 | Scope drift | Scope Fence + drift_guard.py + NOT NOW keywords |
| 8 | Editing without reading | read_before_edit.py |
| 9 | Coding without plan (3+ files) | plan_mode_guard.py |

---

## Quick Start for New Projects

```bash
# 1. Install config (once)
git clone https://github.com/sergeeey/Claude-cod-top-2026.git
bash Claude-cod-top-2026/install.sh --profile=full --non-interactive

# 2. Go to project directory
cd /path/to/new-project

# 3. Tell Claude
# "No CLAUDE.md found — what's the goal and stack?"
# Claude will:
#   -> ask for goal and tech stack
#   -> create CLAUDE.md + .claude/memory/activeContext.md
#   -> load routing-policy
#   -> start working per methodology
```

---

## Design Principles

1. **Evidence-First** — every claim tagged; hallucinations cannot hide
2. **Deterministic Automation** — hooks run 100% (not probabilistic like instructions)
3. **Progressive Disclosure** — load only what is needed (500 tok baseline vs 3000+)
4. **80/20 Focus** — prioritize the 20% of tasks that deliver 80% of results
5. **Test-Driven** — RED -> GREEN -> REFACTOR; never delete tests to pass broken code
6. **Security-by-Default** — PII auto-masked, injection auto-blocked, secrets env-only
7. **Token Scarcity** — aggressive on budget; fallbacks when MCP fails
8. **Modularity** — 70-line core extensible without bloat
9. **Autonomy with Guardrails** — Claude acts decisively within hard guards
10. **Honest Limitations** — [UNKNOWN] better than false [INFERRED]
