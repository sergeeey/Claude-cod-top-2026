# Claude Code Config — Full Methodology

How this configuration works end-to-end: from installation to daily workflow.

## Architecture: 6 Loading Layers

```
Layer 1: CLAUDE.md        ~500 tok/msg   Always loaded (core rules)
Layer 2: Rules (8 files)   0 tok         On-demand (coding, security, testing, integrity, memory, context-loading, permissions, mentor)
Layer 3: Skills (8+8)      ~100 tok      Trigger-based (routing, TDD, brainstorming, agent-teams, ...)
Layer 4: Agents (9+3)      0 tok         Isolated context (navigator, builder, reviewer, ... + 3 teams)
Layer 5: Hooks (40)        0 tok         Deterministic Python guards (25 hook events)
Layer 6: MCP Profiles (3)  ~3000 tok     Switchable server sets (core/science/deploy)
```

**Design principle**: Only Layer 1 loads every message. Everything else loads on demand, saving 40-50% tokens vs monolithic configs.

---

## Layer 1: Core (CLAUDE.md — 66 lines, ~500 tokens)

Loaded **every message**. Contains:

- **Identity**: Senior technical mentor, English language, English code/terms
- **80/20 filter**: "Which 20% of work delivers 80% of results?" — checked before every action
- **Plan-First**: 3+ files = mandatory EnterPlanMode
- **Stuck Detection**: 4-tier recovery (quick retry → context refresh → strategy switch → human escalation, max depth 3 per tier)
- **Evidence Policy**: Every factual claim tagged with confidence markers
- **Self-Review**: 4-point checklist for plans and 1-2 file changes (30 sec vs 25 min full review)
- **Agent table**: 9 active agents + 3 teams with model/memory/isolation assignments
- **Pointers**: To 8 modular rules (loaded on demand)

## Layer 2: Rules (8 files, 0 tokens until needed)

| Rule | Loads when | What it does |
|------|-----------|-------------|
| `coding-style.md` | Writing/editing code | Python 3.11+, type hints, ruff format, structlog, React/TS strict |
| `security.md` | Data, API, deployment | PII never in logs, parameterized SQL only, secrets in env vars |
| `testing.md` | Tests, coverage | >=80% for business logic, TDD, Test Protection (never delete test to pass broken code) |
| `integrity.md` | Any factual claims | Evidence markers, Confidence Scoring, 10 rationalization antidotes |
| `memory-protocol.md` | Commit, session end | Project vs global memory, pattern tags, context overflow at 70% |
| `context-loading.md` | Agent invocation | Agents read shared state (activeContext, decisions, patterns) before working; graceful degradation |
| `permissions.md` | Permission decisions | Compound approval rules, deny patterns, auto-allow/deny/ask logic |
| `mentor-protocol.md` | Educational content | Organic mode v2: mini-ПОЧЕМУ every 5-7 responses, woven into answer (no TIP/INSIGHT blocks) |

## Layer 3: Skills (8 core + 8 extensions)

Load **on trigger word** in user message. Only ~100 tokens of metadata loaded always.

### Core Skills (universal)

| Trigger | Skill | What happens |
|---------|-------|-------------|
| any task start | `routing-policy` | Routes: task type -> skill -> agent -> tools. Shell preprocessing: injects `git status` + `git diff` |
| "tests", "TDD", "coverage" | `tdd-workflow` | RED -> GREEN -> REFACTOR cycle. Shell preprocessing: injects `pytest --co` (existing tests) |
| "think", "alternatives", "brainstorm" | `brainstorming` | Deep Interview (Phase 0) + 2-3 options with trade-offs, then choose |
| "worktree", "experiment" | `git-worktrees` | Isolated branch for experiments |
| "explain", "teach", "how does X work" | `mentor-mode` | Analogies from user's domain (security/finance) |
| "reference", "external docs" | `reference-registry` | External documentation lookup. Shell preprocessing: injects project references.md |
| "install MCP" | `mcp-installer` | Step-by-step MCP server setup |
| "team", "squad", "parallel agents" | `agent-teams` | Orchestration patterns: review-squad, build-squad, research-squad |

### Extension Skills (domain-specific, installed on demand)

| Skill | Domain | Path activation | Effort |
|-------|--------|-----------------|--------|
| `security-audit` | Finance/compliance | `**/*auth*`, `**/*payment*`, `**/*crypto*`, `**/*.env*`, `**/*secret*` | max |
| `archcode-genomics` | Genomics | `**/*variant*`, `**/*vcf*`, `**/*clinvar*`, `**/*extrusion*`, `**/*chromatin*` | max |
| `geoscan` | Satellite prospecting | `**/*sentinel*`, `**/*raster*`, `**/*spectral*`, `**/*ndvi*`, `**/*.tif` | max |
| `notebooklm` | Productivity | — | default |
| `suno-music` | Creative | — | default |
| `python-geodata` | Geospatial | — | default |
| `last30days` | Research | — (external repo) | default |
| `research-pipeline` | Research | — [EXPERIMENTAL] | default |

## Layer 4: Agents (9 active + 3 teams, isolated context)

Run in **subprocess** — zero tokens in main conversation.

### Strategic (Opus — 20% of tasks)

| Agent | Memory | When | What |
|-------|--------|------|------|
| `navigator` | user | Session start, unclear priorities | 80/20 decomposition, can spawn builder/reviewer/tester |
| `architect` | — | Before new module or refactoring | Architecture proposal, can spawn builder |
| `sec-auditor` | project | Working with data, logs, databases | PII masking, injection blocking, regulatory compliance |
| `teacher` | — | User asks to explain concepts | Analogies, multiple perspectives |

### Workhorse (Sonnet — 80% of tasks, 5-10x cheaper)

| Agent | Memory | Isolation | When | What |
|-------|--------|-----------|------|------|
| `builder` | — | worktree | Architecture defined, need implementation | Code generation with type hints, tests, linting |
| `tester` | — | worktree | After business logic written | Happy path -> edge cases -> failures |
| `reviewer` | project | — | After implementation, before commit | 3-pass review: spec -> quality -> adversarial |
| `explorer` | local | — | Need to find something in codebase | Fast Glob/Grep/Read, structured report |
| `verifier` | — | — | Config changes, unfamiliar packages | Prove claim is WRONG first (hallucination hypothesis) |

### Agent Teams

| Team | Members | Strategy | Use case |
|------|---------|----------|----------|
| `review-squad` | reviewer + sec-auditor | parallel | Code review + security audit simultaneously (2x speed) |
| `build-squad` | builder + tester | parallel worktree | Implementation + tests in isolated worktrees |
| `research-squad` | explorer + verifier | sequential | Find facts, then verify for hallucinations |

### Dispatch pattern

```
Sequential (writes to same files):
  navigator -> architect -> builder -> tester -> reviewer -> commit

Parallel (read-only):
  review-squad (reviewer + sec-auditor run simultaneously)
  build-squad (builder + tester in separate worktrees)

Sonnet-first (80% savings):
  builder/tester/explorer/reviewer run Sonnet
  Escalate to Opus only when needed (navigator/architect/sec-auditor/teacher)
```

## Layer 5: Hooks (40 Python scripts, 25 events, 0 tokens)

**Deterministic** — execute 100% of the time (unlike CLAUDE.md instructions which Claude may skip).

### Before tool call (PreToolUse)

| Hook | Matcher | Action |
|------|---------|--------|
| `pre_commit_guard.py` | Bash | Block: rm -rf, push --force, DROP TABLE, chmod 777 |
| `read_before_edit.py` | Edit\|Write | "Did you Read the file before editing?" |
| `security_verify.py` | Edit\|Write | Auto-warn on sensitive files (.env, auth, payment, secret, migration, crypto) |
| `input_guard.py` | mcp__* | Detect 7 prompt injection categories |
| `mcp_circuit_breaker.py` | mcp__* | Block MCP server after 3 failures (CLOSED->OPEN->HALF_OPEN) |
| `mcp_locality_guard.py` | mcp__context7, etc | "Did you try local search first?" |
| `redact.py` | external MCP | Mask PII: national IDs, phone, email, tokens, API keys (12 patterns) |

### After tool call (PostToolUse)

| Hook | Matcher | Action |
|------|---------|--------|
| `post_format.py` | Edit\|Write | Auto-format: Python (ruff), JS/TS (prettier). **Async** — non-blocking |
| `plan_mode_guard.py` | Edit\|Write | Warn if 3+ files edited without a plan |
| `drift_guard.py` | Skill\|Agent | Check NOT NOW keywords from scope fence |
| `memory_guard.py` | Bash | Remind to update activeContext.md after commits |
| `checkpoint_guard.py` | Bash | Remind to checkpoint before rebase/migration |
| `post_commit_memory.py` | Bash | Auto-log commit to activeContext.md |
| `pattern_extractor.py` | Bash | Extract lesson from fix: commits into patterns.md. **Async** — non-blocking |
| `mcp_circuit_breaker_post.py` | mcp__* | Record MCP success/failure for circuit state |

### User input hooks (UserPromptSubmit)

| Hook | Action |
|------|--------|
| `keyword_router.py` | Auto-suggest skills by keywords (tdd→tdd-workflow, security→security-audit) |
| `thinking_level.py` | Auto-suggest `/think ultrathink` for complex tasks |

### Session lifecycle hooks

| Hook | Event | Action |
|------|-------|--------|
| `session_start.py` | SessionStart | Load activeContext.md + scope fence into context |
| `pre_compact.py` | PreCompact | Save state before context compaction (progressive compression) |
| `session_save.py` | Stop | Warn if memory is stale before exit. **Async** |
| `webhook_notify.py` | Stop | Send Slack/Telegram notification on session events. **Async**. SSRF-protected |

### Permission hooks

| Hook | Event | Action |
|------|-------|--------|
| `permission_policy.py` | PermissionRequest | Auto-allow Read/Glob/Grep, auto-deny 39 dangerous patterns, chain-operator bypass protection |

### Environment hooks

| Hook | Event | Action |
|------|-------|--------|
| `env_reload.py` | FileChanged | Watch .env/.envrc → safe reload (shlex.quote + regex validation) |
| `direnv_loader.py` | CwdChanged | Load directory-specific .env with path traversal protection |

### Agent lifecycle hooks

| Hook | Event | Action |
|------|-------|--------|
| `agent_lifecycle.py --start` | SubagentStart | Inject project context (activeContext.md) into agent |
| `agent_lifecycle.py --stop` | SubagentStop | Log agent completion to audit trail |

### Error recovery hooks

| Hook | Event | Action |
|------|-------|--------|
| `post_tool_failure.py` | PostToolUseFailure | Recovery logic after tool execution failure |
| `stop_failure.py` | StopFailure | Handle turn end due to API error |

### Context lifecycle hooks

| Hook | Event | Action |
|------|-------|--------|
| `post_compact.py` | PostCompact | Post-compression actions after context compaction |
| `session_end.py` | SessionEnd | Cleanup on session exit |

### Worktree hooks

| Hook | Event | Action |
|------|-------|--------|
| `worktree_lifecycle.py` | WorktreeCreate | Track git worktree creation |
| `worktree_lifecycle.py` | WorktreeRemove | Cleanup on worktree removal |

### Task lifecycle hooks

| Hook | Event | Action |
|------|-------|--------|
| `task_audit.py` | TaskCreated | Log task creation to tasks.jsonl (audit trail) |
| `task_audit.py` | TaskCompleted | Log task completion to tasks.jsonl |

### Instructions hooks

| Hook | Event | Action |
|------|-------|--------|
| `instructions_audit.py` | InstructionsLoaded | Log which CLAUDE.md/rules loaded (debug config drift) |

### MCP elicitation hooks

| Hook | Event | Action |
|------|-------|--------|
| `elicitation_guard.py` | Elicitation | Log MCP server elicitation requests |
| `elicitation_guard.py` | ElicitationResult | Log user responses to MCP elicitations |

### Infrastructure hooks

| Hook | Event | Action |
|------|-------|--------|
| `config_audit.py` | ConfigChange | Append-only JSON audit trail to ~/.claude/logs/ |
| `team_rebalance.py` | TeammateIdle | Log idle events, notify orchestrator for task redistribution |
| `notification` | Notification | Audio beep (800Hz, 300ms) when Claude finishes |

### Utility

| Script | Role |
|--------|------|
| `async_wrapper.py` | Non-blocking launcher for slow hooks (Windows: DETACHED_PROCESS, Unix: start_new_session) |
| `utils.py` | 21 shared functions — DRY across all hooks |
| `statusline.py` | Persistent bar: model, context %, branch, cost, duration |

### Static deny rules (31 patterns in settings.json)

```
rm -rf $HOME/.claude/*    rm -rf /*              git push --force
git reset --hard          git clean -fd          git branch -D
DROP TABLE                DROP DATABASE          TRUNCATE TABLE
chmod 777                 npm publish            curl | bash
wget | bash               pip install --break-system-packages
docker rm                 kubectl delete         format C:
del /s /q                 rmdir /s /q            --delete-all
Edit(.env*)               Write(.env*)           Write(**/secrets/**)
Edit(**/*.test.py)        Edit(**/*.test.ts)     Edit(**/*.spec.ts)
Edit(**/*_test.py)        Edit(**/*tests.py)     > /dev/null 2>&1 &
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
session_start.py fires (SessionStart)
  -> loads activeContext.md into context
  -> loads scope fence (if exists)
  -> Claude: "Continuing [task] or new goal?"
```

### Phase 2: Task Routing

`routing-policy` skill determines the path (with live `git status` + `git diff` injected):

| Task type | Route |
|-----------|-------|
| Research/question | explorer agent -> if not found -> MCP (Context7, WebSearch) |
| Code change (1-2 files) | Read -> Self-Review -> Edit -> test -> commit |
| Code change (3+ files) | EnterPlanMode -> navigator -> architect -> builder -> tester -> reviewer |
| TDD | tdd-workflow (with live `pytest --co`): RED (failing test) -> GREEN (minimal code) -> REFACTOR |
| Debugging | Read error -> explore -> hypothesis [INFERRED] -> verify [VERIFIED] -> fix |
| Security/compliance | security-audit skill -> review-squad (reviewer + sec-auditor in parallel) |

### Phase 3: Execution with Guard Rails

Every action passes through the hook pipeline:

```
User request
  -> keyword_router + thinking_level (UserPromptSubmit)
  -> routing-policy determines path
  -> PermissionRequest: permission_policy auto-allows/denies/asks
  -> PreToolUse hooks fire:
     Bash: pre_commit_guard (block dangerous)
     Edit|Write: read_before_edit + security_verify (sensitive files)
     mcp__*: input_guard + circuit_breaker + locality_guard + PII redact
  -> Tool executes
  -> PostToolUse hooks fire:
     Edit|Write: async post_format + plan_mode_guard
     Bash: memory_guard + checkpoint_guard + post_commit_memory + async pattern_extractor
     Skill|Agent: drift_guard
     mcp__*: circuit_breaker_post
  -> Result shown to user
```

### Phase 4: Code Review (before commit)

Reviewer agent (or review-squad for parallel review + security audit) runs 3 passes:

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
  -> pattern_extractor.py: extracts lesson from fix: commits (async)
  -> memory_guard.py: reminds to update context manually
  -> webhook_notify.py: sends Slack/Telegram notification (async, if configured)
```

### Phase 6: Context Overflow (70% threshold)

```
pre_compact.py saves state (progressive compression — preserves errors, decisions)
  -> update activeContext.md with critical context
  -> /clear
  -> session_start.py reloads context
  -> continue working
```

### Phase 7: Session End

```
session_save.py fires (async)
  -> warns if activeContext.md is stale
  -> user updates: activeContext.md, patterns.md, learning_log.md
webhook_notify.py fires (async)
  -> sends session summary to Slack/Telegram (if configured)
```

### Phase 8: Environment Changes (continuous)

```
FileChanged (.env/.envrc)
  -> env_reload.py: safe parse + reload (shlex.quote, regex validation, path boundary)

CwdChanged (cd to new directory)
  -> direnv_loader.py: load directory-specific .env (with path traversal protection)

SubagentStart
  -> agent_lifecycle.py --start: inject activeContext.md into agent

SubagentStop
  -> agent_lifecycle.py --stop: log completion to audit trail

ConfigChange
  -> config_audit.py: append-only JSON audit log

TeammateIdle
  -> team_rebalance.py: log + notify for task redistribution
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

### Agent memory (new in v3.0.0)

4 agents carry persistent context between sessions:

| Agent | Memory type | What persists |
|-------|-------------|---------------|
| navigator | user | User preferences, priorities, working style |
| reviewer | project | Codebase patterns, past review findings |
| sec-auditor | project | Security findings, compliance state |
| explorer | local | Codebase structure, search history |

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
| Hooks | 0 | Python runtime (25 events) |
| MCP servers (core) | ~3000 | Always |
| **Total (typical)** | **~3500** | — |
| Monolithic config | 5000-7000 | Always |
| **Savings** | **40-50%** | — |

---

## Anti-Patterns Prevented

| # | Anti-Pattern | Protection |
|---|-------------|------------|
| 1 | Context overflow (rules buried) | 66-line core + 8 modular rules + pre_compact.py (progressive compression) |
| 2 | Hallucination loops | Evidence Policy + 4-tier Stuck Detection + integrity.md |
| 3 | PII leakage | redact.py (12 patterns) + security.md |
| 4 | Dangerous commands | pre_commit_guard.py + permission_policy.py (31 deny + 39 dangerous patterns) |
| 5 | MCP server failures | circuit_breaker (CLOSED/OPEN/HALF_OPEN) + auto-fallback |
| 6 | Prompt injection via MCP | input_guard.py (7 detection categories) |
| 7 | Scope drift | Scope Fence + drift_guard.py + NOT NOW keywords |
| 8 | Editing without reading | read_before_edit.py |
| 9 | Coding without plan (3+ files) | plan_mode_guard.py |
| 10 | Sensitive file edits unreviewed | security_verify.py (auto-warn on auth/payment/secret/migration) |
| 11 | Command injection via .env | parse_env_file_safe() — regex validation + shlex.quote |
| 12 | Chain operator bypass | permission_policy.py checks &&/\|\|/;/\| BEFORE prefix matching |
| 13 | SSRF via webhooks | validate_webhook_url() — blocks localhost, private IPs, file:// scheme |
| 14 | Path traversal | is_safe_path() — home-directory boundary check |
| 15 | Stateless agents | Persistent memory for 4 agents + worktree isolation for 2 |

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
2. **Deterministic Automation** — 40 hooks across 25 events run 100% (not probabilistic like instructions)
3. **Progressive Disclosure** — load only what is needed (500 tok baseline vs 5000+)
4. **80/20 Focus** — prioritize the 20% of tasks that deliver 80% of results
5. **Test-Driven** — RED -> GREEN -> REFACTOR; never delete tests to pass broken code
6. **Security-by-Default** — PII auto-masked, injection auto-blocked, SSRF prevented, secrets env-only
7. **Token Scarcity** — aggressive on budget; async hooks, fallbacks when MCP fails
8. **Modularity** — 66-line core extensible without bloat
9. **Autonomy with Guardrails** — Claude acts decisively within hard guards
10. **Honest Limitations** — [UNKNOWN] better than false [INFERRED]
