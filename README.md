<p align="center">
  <img src="https://github.com/sergeeey/Claude-cod-top-2026/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/badge/Claude_Code-v2.4.0-0969DA?style=for-the-badge&logo=anthropic&logoColor=white" alt="Version">
  <img src="https://img.shields.io/badge/Hooks-18_guards-2ea44f?style=for-the-badge" alt="Hooks">
  <img src="https://img.shields.io/badge/Agents-9_active-f5a623?style=for-the-badge" alt="Agents">
  <img src="https://img.shields.io/badge/Tests-394_passing-2ea44f?style=for-the-badge" alt="Tests">
  <img src="https://img.shields.io/badge/Coverage-90%25-2ea44f?style=for-the-badge" alt="Coverage">
  <img src="https://img.shields.io/badge/mypy-strict-0969DA?style=for-the-badge" alt="mypy">
  <img src="https://img.shields.io/badge/license-MIT-f5f5f5?style=for-the-badge" alt="License">
</p>

<h1 align="center">Claude Code Config v2.4.0</h1>

<p align="center">
  <b>Production-grade Claude Code configuration with Evidence Policy, adversarial validation, and MCP resilience.</b><br>
  Battle-tested on production systems handling sensitive data.<br><br>
  <code>394 tests</code> &middot; <code>90% coverage</code> &middot; <code>mypy strict</code> &middot; <code>ruff clean</code>
</p>

---

## System Architecture

```
                          Claude Code Config v2.4.0
    ┌──────────────────────────────────────────────────────────────────┐
    │                                                                  │
    │   CLAUDE.md  ──────────────────────────────────  ALWAYS LOADED   │
    │   70 lines  ~500 tokens                                          │
    │   Identity  80/20  Plan-First  Evidence Policy                   │
    │                                                                  │
    │         │              │              │              │            │
    │         ▼              ▼              ▼              ▼            │
    │    ┌─────────┐   ┌──────────┐   ┌─────────┐   ┌──────────┐     │
    │    │ Rules   │   │ Skills   │   │ Agents  │   │  Hooks   │     │
    │    │ 6 files │   │ 15 total │   │ 9 active│   │ 18 guards│     │
    │    │         │   │          │   │         │   │          │     │
    │    │on-demand│   │on-trigger│   │isolated │   │ ALWAYS   │     │
    │    │~200 tok │   │~500 tok  │   │own ctx  │   │ 0 tokens │     │
    │    └─────────┘   └──────────┘   └─────────┘   └──────────┘     │
    │                                                                  │
    ├──────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │   MCP Request Pipeline                                           │
    │                                                                  │
    │   Request                                                        │
    │     │                                                            │
    │     ├── InputGuard ────── 7 injection categories                 │
    │     ├── CircuitBreaker ── CLOSED / OPEN / HALF_OPEN              │
    │     ├── LocalityGuard ─── "did you try local search first?"      │
    │     ├── PII Redact ────── 12 patterns auto-stripped              │
    │     │                                                            │
    │     ▼                                                            │
    │   EXECUTE                                                        │
    │     │                                                            │
    │     └── CircuitBreaker (Post) ── record success/failure          │
    │                                                                  │
    ├──────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │   Token Economy                                                  │
    │                                                                  │
    │   Always loaded    ~500 tokens    CLAUDE.md core                 │
    │   On-demand        ~200 tokens    Rules (loaded by context)      │
    │   On-trigger       ~500 tokens    Skills (loaded by keyword)     │
    │   Free             0 tokens       Hooks (Python runtime)         │
    │                                                                  │
    │   Total per message: ~500 tokens  (vs 3000-5000 in monolithic)   │
    │                                                                  │
    └──────────────────────────────────────────────────────────────────┘
```

---

## Why This Config?

> **Claude Code without configuration** is like an IDE without settings: it works, but you lose 60% of its potential.

Most configs are a single CLAUDE.md bloated to 3000+ tokens. This approach is different:

| | Typical config | This config |
|---|---|---|
| **Tokens/msg** | 3000-5000 | ~500 (core only) |
| **Hallucinations** | "trust me" | Evidence Policy + Confidence Scoring |
| **MCP failures** | session hangs | CircuitBreaker (auto-recovery in 60s) |
| **Prompt injection** | no protection | InputGuard (7 categories, auto-block) |
| **PII leakage** | hope for the best | 12 regex patterns + auto-redact |
| **Code quality** | optional review | DoubterAgent (3-pass adversarial review) |
| **Tests** | "I'll write them later" | TDD-first + Test Protection |

---

## Quick Start

### One-liner: paste this into Claude Code

Open `claude` in any project and paste this single message:

```
https://github.com/sergeeey/Claude-cod-top-2026.git

Clone this repo to /tmp, run `bash install.sh --profile=standard --non-interactive`,
then delete the clone. After install:

1. Show what was installed (hooks, agents, skills, rules) as a table
2. Create .claude/memory/activeContext.md for the current project with:
   - Current branch and last 3 commits (from git log)
   - Project stack (detect from package.json / pyproject.toml / Cargo.toml)
   - Current focus: "New session — awaiting first task"
3. Show this mini-presentation:

## What just changed

**Before:** Claude Code works from memory, no guardrails, no learning.
**After:** 18 deterministic hooks + 9 specialized agents + 15 skills.

What you get RIGHT NOW (zero config):
- Evidence Policy — every fact marked [VERIFIED]/[INFERRED]/[UNKNOWN]
- pre_commit_guard — blocks rm -rf, push --force, DROP TABLE automatically
- 4-tier crash recovery — retry → context refresh → new approach → ask human
- Feature branch enforcement — no commits to main/master
- Auto-format on save — ruff for Python, prettier for JS/TS
- Keyword routing — type "security" and security-audit skill activates
- Thinking-level boost — complex tasks auto-suggest /think ultrathink
- Session memory — activeContext.md persists across sessions
- Pattern learning — every fix: commit extracts Symptom→Cause→Fix→Lesson

To verify it works, try:
  - Edit any file → read_before_edit hook should nudge you
  - Type "tdd" in a prompt → keyword_router suggests tdd-workflow
  - Try `git commit` on main → pre_commit_guard blocks it

Restart the session (`/exit` then `claude`) to activate all hooks.
```

That's it — one paste, full setup, instant verification.

### Manual Install

```bash
# 1. Clone
git clone https://github.com/sergeeey/Claude-cod-top-2026.git
cd Claude-cod-top-2026

# 2. Install (interactive profile selection)
bash install.sh                                    # interactive, copy mode
bash install.sh --link full                        # symlink + auto-update
bash install.sh --profile=full --non-interactive   # CI / Docker / headless

# 3. Verify
claude
> /context   # should show: CLAUDE.md, rules, skills loaded
```

### Installation Profiles

| Profile | What it installs | For whom |
|---------|-----------------|----------|
| `minimal` | CLAUDE.md + integrity + security rules | Try Evidence Policy |
| `standard` | + all rules + hooks + core skills + agents | Daily work |
| `full` | + MCP profiles + PII redaction + memory templates | Full control |

---

## Key Features

### Evidence Policy

Every factual claim is tagged with a confidence level:

```
 VERIFIED-HIGH     2+ sources confirmed      "Python 3.11+ required"
 VERIFIED-MEDIUM   1 source + inference       "Context overflow ~70%"
 VERIFIED-LOW      indirect evidence          "Opus better for architecture"
 UNKNOWN           no confirmation            "needs verification"
```

**Confidence Scoring** (0.0-1.0) based on source count. **Rationalization Prevention** — 10 common AI excuses with countermeasures.

### DoubterAgent — 3-Pass Code Review

```
 Pass 1   Spec Compliance       does the code solve the task?
 Pass 2   Code Quality          type hints, DRY, security?
 Pass 3   Adversarial Challenge "What if...?" for every decision
              ACCEPT (HIGH)       sufficient evidence
              CHALLENGE (MEDIUM)  needs verification
              REJECT (LOW)        clear error
```

### CircuitBreaker — MCP Never Hangs

```
 MCP server fails 3x    OPEN (blocked 60s)
                           |
 After 60s               HALF_OPEN (test 1 request)
                           |
 Success                 CLOSED (recovered)
 Failure                 OPEN (retry later)
```

Automatic fallback: `context7` -> WebSearch, `playwright` -> WebFetch, `ollama` -> cloud model.

### InputGuard — Prompt Injection Protection

7 detection categories in real-time:

| Category | Examples | Action |
|----------|---------|--------|
| `system_override` | "ignore previous instructions" | LOW / HIGH |
| `encoding_attack` | null bytes, zero-width chars | **AUTO-BLOCK** |
| `command_injection` | `; rm -rf`, `` `$(curl)` `` | **AUTO-BLOCK** |
| `jailbreak` | "DAN mode", "bypass safety" | LOW / HIGH |
| `data_exfil` | "send to http", "curl" | LOW / HIGH |
| `role_injection` | `[SYSTEM]`, `<system>` | LOW |
| `credential_harvest` | "show me your api key" | LOW |

### PII Redaction — 12 Patterns

Strips sensitive data before external MCP calls:

```
 National IDs   Bank cards   IBAN   API keys   GitHub tokens
 Slack tokens   AWS keys   JWT   Generic secrets   IPs   Email   Phone

> PII patterns ship with example formats. Adapt regex in `scripts/redact.py` for your region.
```

Smart exceptions: ClinVar IDs, dbSNP, genomic coordinates, decimal numbers, git SHA.

---

## 18 Hooks

> Hooks execute **100% of the time**. Unlike CLAUDE.md instructions which are probabilistic, hooks are deterministic Python guards.

| Hook | Event | Protects Against |
|------|-------|-----------------|
| `input_guard` | PreToolUse (MCP) | Prompt injection via MCP |
| `mcp_circuit_breaker` | PreToolUse (MCP) | Session hang on MCP failure |
| `mcp_circuit_breaker_post` | PostToolUse (MCP) | Records failures for recovery |
| `mcp_locality_guard` | PreToolUse (MCP) | MCP call without local search first |
| `pre_commit_guard` | PreToolUse (Bash) | Commits to main, `rm -rf`, `DROP TABLE` |
| `read_before_edit` | PreToolUse (Edit) | Edit without prior Read |
| `session_start` | SessionStart | Context loss between sessions |
| `pre_compact` | PreCompact | Data loss during compaction |
| `post_format` | PostToolUse (Edit) | Unformatted code (ruff / prettier) |
| `plan_mode_guard` | PostToolUse (Edit) | 3+ files edited without a plan |
| `drift_guard` | PostToolUse (Skill) | Scope creep (NOT NOW keywords) |
| `memory_guard` | PostToolUse (Bash) | Forgotten memory update after commit |
| `checkpoint_guard` | PostToolUse (Bash) | Risky ops without checkpoint |
| `post_commit_memory` | PostToolUse (Bash) | Context loss after commits |
| `pattern_extractor` | PostToolUse (Bash) | Lost lessons from fix: commits |
| `keyword_router` | UserPromptSubmit | Auto-trigger skills by keywords |
| `thinking_level` | UserPromptSubmit | Boost thinking depth for complex tasks |
| `session_save` | SessionEnd | State loss on exit |

All hooks share `utils.py` — 16 common functions, zero duplication (DRY-refactored).

---

## 9 Agents

```
 STRATEGIC (Opus)                       20% of tasks
 navigator   architect   reviewer   verifier   teacher

 WORKHORSE (Sonnet)                     80% of tasks
 builder   tester   explorer   sec-auditor

 Routing: Sonnet-First, Opus escalation only
 Saves ~60% on tokens while maintaining quality
```

4 specialized agents archived in `agents/_archived/` (available if needed).

---

## Skills

**7 Core** (universal, installed by default):

| Skill | Domain | Triggers |
|-------|--------|---------|
| `routing-policy` | Task routing | any task start |
| `tdd-workflow` | TDD | tests, coverage |
| `brainstorming` | Design | brainstorm, think |
| `mentor-mode` | Learning | explain, teach |
| `git-worktrees` | Git | worktree, experiment |
| `mcp-installer` | Setup | mcp, install |
| `reference-registry` | References | external links, docs |

**8 Extensions** (install on demand — these are **examples** of domain-specific skills; adapt or replace for your domain):

| Skill | Category | Triggers |
|-------|----------|---------|
| `security-audit` | Finance | audit, fraud, compliance, PCI |
| `archcode-genomics` | Science | ClinVar, chromatin |
| `geoscan` | Science | Sentinel, spectral |
| `notebooklm` | Productivity | NotebookLM, query docs |
| `suno-music` | Creative | Suno, BPM, track |
| `python-geodata` | Geospatial | rasterio, geopandas |
| `last30days` | Research | `/last30days` — 10+ platforms, external repo |
| `research-pipeline` | Research | [EXPERIMENTAL] multi-agent asyncio pipeline |

```bash
bash skill-manager.sh list              # show installed + available
bash skill-manager.sh install notebooklm
bash install.sh --profile=full          # includes last30days (git clone)
```

> Skills consume **0 tokens** until triggered. Extensions are individually installable.

---

## MCP Profiles

```
   CORE (default)       SCIENCE            DEPLOY
   context7             + ncbi-datasets    + vercel
   basic-memory         + uniprot          + netlify
   playwright           + pubmed-mcp       + supabase
   ollama                                  + sentry
```

```bash
~/.claude/mcp-profiles/switch-profile.ps1 science
```

---

## Testing

```bash
pip install pytest pytest-cov ruff mypy

# Run all tests
pytest tests/ -v --cov=hooks --cov=scripts --cov-report=term-missing

# Lint
ruff check hooks/ scripts/ tests/

# Type check
mypy hooks/utils.py hooks/input_guard.py hooks/mcp_circuit_breaker.py

# Smoke tests
bash tests/test_all.sh
```

**394 tests** across 16 test files. Coverage: **90%**. All hooks syntax-validated, mypy strict, ruff clean.

---

## File Structure

```
Claude-cod-top-2026/
|
|-- claude-md/CLAUDE.md            Core config (70 lines, ~500 tokens)
|
|-- rules/                         6 modular rules
|   |-- coding-style.md              Code standards (Python, React/TS)
|   |-- security.md                   PII, secrets, SQL injection
|   |-- testing.md                    TDD, coverage, Test Protection
|   |-- integrity.md                  Evidence Policy + Confidence Scoring
|   |-- memory-protocol.md            Memory, checkpoints, overflow
|   +-- context-loading.md            Agent CONTEXT LOADING protocol
|
|-- hooks/                         18 Python guards + shared utils + statusline
|   |-- utils.py                      16 shared functions (DRY)
|   |-- settings.json                 Hook registry + deny patterns
|   |-- input_guard.py                Prompt injection (7 categories)
|   |-- mcp_circuit_breaker.py        MCP resilience (Pre + Post)
|   +-- ...                           12 more hooks
|
|-- scripts/
|   +-- redact.py                  PII redaction (12 patterns)
|
|-- agents/                        9 active agents
|   |-- navigator.md                  Strategic planning (Opus)
|   |-- builder.md                    Code generation (Sonnet)
|   |-- reviewer.md                   3-pass code review (Sonnet)
|   |-- sec-auditor.md                Security + PII audit (Opus)
|   +-- _archived/                    4 consolidated agents
|
|-- skills/
|   |-- core/                      7 universal skills
|   +-- extensions/                8 domain-specific skills (+last30days, +research-pipeline)
|
|-- mcp-profiles/                  3 profiles (core/science/deploy)
|-- tests/                         394 tests (16 files)
|-- docs/                          Architecture, guides, anti-patterns
|-- .github/workflows/ci.yml       CI: pytest + ruff + mypy + secrets scan
+-- pyproject.toml                 ruff + mypy + pytest config
```

---

## Documentation

| Document | Description |
|----------|------------|
| [Architecture](docs/architecture.md) | 6-layer system design |
| [Evidence Policy](docs/evidence-policy.md) | Anti-hallucination + Confidence Scoring |
| [Hooks Guide](docs/hooks-guide.md) | All 17 hooks with examples |
| [Skills Guide](docs/skills-guide.md) | Creating and managing skills |
| [Anti-Patterns](docs/anti-patterns.md) | 8 critical mistakes to avoid |
| [Troubleshooting](docs/troubleshooting.md) | 10-point diagnostic checklist |
| [CONTRIBUTING](CONTRIBUTING.md) | Contribution guidelines |
| [SECURITY](SECURITY.md) | Vulnerability reporting |
| [CHANGELOG](CHANGELOG.md) | Version history |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT — use, adapt, extend.

---

## Status Line

A persistent bar at the bottom of the terminal — zero token cost, always visible:

```
[Opus 4.6] ▓▓▓▓▓▓▓░░░░░░░░░░░░░ 35% | main | $0.42 | 3m5s
```

| Metric | Color | When to act |
|--------|-------|-------------|
| Context % | Green (<50%) | Keep working |
| Context % | Yellow (50-70%) | Plan a `/clear` soon |
| Context % | Red (>70%) | `/clear` now |

Included in `hooks/statusline.py`. Configured via `statusLine` in settings.json.

---

## Tips & Recommended Settings

| Setting | Value | Why |
|---------|-------|-----|
| `autoUpdatesChannel` | `"stable"` | Skips releases with regressions (~1 week delay) |
| `/btw <question>` | Built-in | Side question in overlay, never enters context — saves tokens |
| Notification hook | beep on finish | Built-in Claude Code feature — audio alert when Claude completes |

---

## Used In Production

This config has been battle-tested on a live production system (29K LOC, 690 tests, voice processing domain):

- `pre_commit_guard` blocked accidental push to main during a hotfix
- `pattern_extractor` auto-logged debugging lessons from fix: commits
- `memory_guard` ensured activeContext.md stayed current across 3 deploy cycles

> This is not a demo. The config runs on a live system with real users, real incidents, and real deploys.

---

<p align="center">
  <b>Built with Evidence, not hope.</b>
</p>
