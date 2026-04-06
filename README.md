<p align="center">
  <img src="assets/banner.svg" alt="Claude Code Hooks — Top 2026" width="100%"/>
</p>

<p align="center">
  <a href="https://github.com/sergeeey/Claude-cod-top-2026/actions/workflows/ci.yml">
    <img src="https://github.com/sergeeey/Claude-cod-top-2026/actions/workflows/ci.yml/badge.svg" alt="CI"/>
  </a>
  &nbsp;
  <img src="https://img.shields.io/badge/version-3.2.0-bf5fff?style=flat-square&logo=anthropic&logoColor=white" alt="Version"/>
  &nbsp;
  <img src="https://img.shields.io/badge/hooks-40_guards-00f5ff?style=flat-square" alt="Hooks"/>
  &nbsp;
  <img src="https://img.shields.io/badge/agents-13_%2B_3_teams-ff2d78?style=flat-square" alt="Agents"/>
  &nbsp;
  <img src="https://img.shields.io/badge/tests-712_passing-00ff9f?style=flat-square" alt="Tests"/>
  &nbsp;
  <img src="https://img.shields.io/badge/coverage-86%25-00ff9f?style=flat-square" alt="Coverage"/>
  &nbsp;
  <img src="https://img.shields.io/badge/mypy-checked-0969DA?style=flat-square" alt="mypy"/>
  &nbsp;
  <img src="https://img.shields.io/badge/license-MIT-555?style=flat-square" alt="License"/>
</p>

<p align="center">
  <b>Production-grade Claude Code configuration with Evidence Policy, Agent Teams, persistent memory and MCP resilience.</b><br/>
  <sub>Battle-tested on production systems · 40 deterministic hooks · 86% coverage · Zero token overhead</sub>
</p>

---

<p align="center">
  <img src="assets/pipeline.svg" alt="Hook Execution Pipeline" width="100%"/>
</p>

---

## Why This Config?

> **Claude Code без конфига** — как IDE без настроек: работает, но 60% потенциала потеряно.

Most configs are a single `CLAUDE.md` bloated to 3000+ tokens. This is different:

| | Typical config | **This config** |
|---|---|---|
| **Tokens/msg** | 3 000 – 5 000 | **~500** (core only) |
| **Hallucinations** | "trust me" | Evidence Policy + Confidence Scoring |
| **MCP failures** | session hangs | CircuitBreaker — auto-recovery in 60s |
| **Prompt injection** | no protection | InputGuard — 7 categories, auto-block |
| **PII leakage** | hope for the best | 12 regex patterns + auto-redact |
| **Code review** | optional | review-squad — parallel reviewer + sec-auditor |
| **Permissions** | ask for everything | PermissionRequest hook — 75% auto-approved |
| **Agent memory** | stateless | 4 agents with persistent memory across sessions |
| **Tests** | "I'll write them later" | 712 tests, TDD-first, Test Protection hard rule |

---

## Quick Start

### One-liner — paste into Claude Code

```
https://github.com/sergeeey/Claude-cod-top-2026.git

Clone this repo to /tmp, run `bash install.sh --profile=standard --non-interactive`,
then delete the clone. After install:

1. Show what was installed (hooks, agents, skills, rules) as a table
2. Create .claude/memory/activeContext.md for the current project with:
   - Current branch and last 3 commits (from git log)
   - Project stack (detect from package.json / pyproject.toml / Cargo.toml)
   - Current focus: "New session — awaiting first task"
3. Confirm: "40 hooks active · 13 agents ready · restart with /exit then claude"
```

### Manual Install

```bash
git clone https://github.com/sergeeey/Claude-cod-top-2026.git
cd Claude-cod-top-2026

bash install.sh                                    # interactive
bash install.sh --link full                        # symlink + auto-update
bash install.sh --profile=full --non-interactive   # CI / headless
```

| Profile | Installs | For whom |
|---------|----------|----------|
| `minimal` | CLAUDE.md + integrity + security | Try Evidence Policy |
| `standard` | + all rules + hooks + skills + agents | Daily work |
| `full` | + MCP profiles + PII redaction + memory | Full control |

---

## 40 Hooks — 25 Events

> Hooks run **100% of the time** — deterministic Python guards, not probabilistic instructions.

<details>
<summary><b>PreToolUse guards (12 hooks)</b></summary>

| Hook | Protects Against |
|------|-----------------|
| `input_guard` | Prompt injection via MCP (7 categories) |
| `mcp_circuit_breaker` | Session hang on MCP failure (auto-recovery 60s) |
| `mcp_locality_guard` | MCP call without local search first |
| `pre_commit_guard` | Commits to main · `rm -rf` · `DROP TABLE` |
| `read_before_edit` | Edit without prior Read |
| `security_verify` | Sensitive file edits without review |
| `plan_mode_guard` | 3+ files edited without a plan |
| `permission_policy` | 75% fewer permission prompts |
| `checkpoint_guard` | Risky ops without checkpoint |

</details>

<details>
<summary><b>PostToolUse audit layer (9 hooks)</b></summary>

| Hook | Protects Against |
|------|-----------------|
| `mcp_circuit_breaker_post` | Records MCP failures for recovery |
| `post_format` | Unformatted code (ruff / prettier) |
| `memory_guard` | Forgotten memory update after commit |
| `post_commit_memory` | Context loss after commits |
| `pattern_extractor` | Lost lessons from `fix:` commits |
| `drift_guard` | Scope creep (NOT NOW keywords) |
| `post_tool_failure` | Repeated failures without strategy change |
| `config_audit` | Unauthorized settings changes |
| `elicitation_guard` | Elicitation events logging |

</details>

<details>
<summary><b>Lifecycle · Session · Memory (19 hooks)</b></summary>

| Hook | Event | Role |
|------|-------|------|
| `session_start` | SessionStart | Load context from memory |
| `session_end` | SessionEnd | Trim + save state |
| `session_save` | Stop (async) | State persistence on exit |
| `post_compact` | PostCompact | Context reminder after compaction |
| `pre_compact` | PreCompact | Data preservation |
| `keyword_router` | UserPromptSubmit | Auto-trigger skills + power modes |
| `thinking_level` | UserPromptSubmit | Boost thinking for complex tasks |
| `statusline` | PostToolUse | Live bar: model · context% · cost |
| `worktree_lifecycle` | WorktreeCreate/Remove | Track experiment branches |
| `agent_lifecycle` | SubagentStart/Stop | Context in agent handoffs |
| `subagent_verify` | SubagentStop | Verify agent output quality |
| `team_rebalance` | TeammateIdle | Rebalance idle agents |
| `stop_failure` | StopFailure | Silent API error handling |
| `task_audit` | TaskCreated/Completed | Task event logging |
| `instructions_audit` | InstructionsLoaded | Track loaded rules |
| `env_reload` | FileChanged | Stale env after `.env` change |
| `direnv_loader` | CwdChanged | Wrong env after `cd` |
| `async_wrapper` | — | Non-blocking wrapper for bg hooks |
| `webhook_notify` | Stop (async) | Slack/Telegram on commit + session end |

</details>

### ⚡ Power Modes — Magic Keywords

Type anywhere in your prompt:

| Keyword | Mode | Effect |
|---------|------|--------|
| `ralph` | Persistent | Don't stop until done. Auto-retry. No confirmations. |
| `autopilot` | Full Autonomy | Plan + execute all steps. Only stop if truly blocked. |
| `ultrawork` / `ulw` | Max Parallelism | Launch agents concurrently. Batch ops. Speed > caution. |
| `deep` | Deep Analysis | Read everything. Evidence-mark all claims. |
| `quick` / `быстро` | Speed | Minimal output. No explanations. Just do it. |

Modes are **additive** — `ralph security audit` = Persistent mode + security-audit skill.

---

## 13 Agents + 3 Teams

```
╔══════════════════════════════════════════════════════════╗
║  STRATEGIC — Opus          ·  20% of tasks               ║
║  navigator(memory:user)  architect  sec-auditor  teacher  ║
╠══════════════════════════════════════════════════════════╣
║  WORKHORSE — Sonnet        ·  80% of tasks               ║
║  builder(worktree)  tester(worktree)  explorer  reviewer  ║
╠══════════════════════════════════════════════════════════╣
║  TEAMS — parallel execution                              ║
║  review-squad  →  reviewer + sec-auditor (parallel)      ║
║  build-squad   →  builder  + tester     (isolated wt)    ║
║  research-squad →  explorer + verifier  (search+verify)  ║
╚══════════════════════════════════════════════════════════╝
```

4 agents with **persistent memory** · 2 agents with **worktree isolation** · Sonnet-first, Opus escalation only

---

## Evidence Policy

Every factual claim is tagged:

```
[VERIFIED-HIGH]    ≥2 sources confirmed       → can be used as fact
[VERIFIED-MEDIUM]  1 source + inference        → careful wording
[VERIFIED-LOW]     indirect evidence           → "there are signs, but..."
[UNKNOWN]          no confirmation             → do not guess
```

**Confidence Scoring** 0.0–1.0 based on source count. **Rationalization Prevention** — 10 common AI excuses with countermeasures baked into rules.

---

## Status Line

Zero token cost — always visible at the bottom of the terminal:

```
[claude-sonnet] ▓▓▓▓▓▓▓░░░░░░░░░░░░░ 35% | main | $0.42 | 3m5s
```

| Context % | Colour | Signal |
|-----------|--------|--------|
| `< 50%` | 🟢 Green | Keep working |
| `50–70%` | 🟡 Yellow | Plan a `/clear` soon |
| `> 70%` | 🔴 Red | `/clear` now |

---

## Security

**InputGuard — 7 injection categories:**

| Category | Example | Action |
|----------|---------|--------|
| `encoding_attack` | null bytes, zero-width chars | **AUTO-BLOCK** |
| `command_injection` | `; rm -rf` · `` `$(curl)` `` | **AUTO-BLOCK** |
| `system_override` | "ignore previous instructions" | Block + warn |
| `jailbreak` | "DAN mode", "bypass safety" | Block + warn |
| `data_exfil` | "send to http", "curl \| bash" | Block + warn |
| `role_injection` | `[SYSTEM]`, `<system>` | Warn |
| `credential_harvest` | "show me your api key" | Warn |

**PII Redaction — 12 patterns** stripped before external MCP calls:
`National IDs · Bank cards · IBAN · API keys · GitHub tokens · AWS keys · JWT · Email · Phone · IPs`

---

## Testing

```bash
pip install pytest pytest-cov ruff mypy

pytest tests/ -v --cov=hooks --cov-report=term-missing   # 712 tests
ruff check hooks/ scripts/ tests/
mypy hooks/utils.py hooks/input_guard.py
bash tests/test_all.sh   # 82 smoke tests
```

```
712 passing · 0 failing · 86% coverage · 82/82 smoke tests
```

---

## MCP Profiles

```
CORE (default)    SCIENCE              DEPLOY
context7          + ncbi-datasets      + vercel
basic-memory      + uniprot            + netlify
playwright        + pubmed-mcp         + supabase
ollama                                 + sentry
```

```bash
~/.claude/mcp-profiles/switch-profile.ps1 science
```

CircuitBreaker auto-fallback: `context7` → WebSearch · `playwright` → WebFetch · `ollama` → cloud

---

<details>
<summary><b>Full File Structure</b></summary>

```
Claude-cod-top-2026/
├── CLAUDE.md                      Core config (66 lines, ~500 tokens)
│
├── rules/                         8 modular rules (loaded on demand)
│   ├── coding-style.md
│   ├── security.md
│   ├── testing.md
│   ├── integrity.md
│   ├── memory-protocol.md
│   ├── context-loading.md
│   ├── permissions.md
│   └── mentor-protocol.md
│
├── hooks/                         40 Python guards
│   ├── utils.py                   21 shared functions (DRY)
│   ├── settings.json              Hook registry + 27 deny patterns
│   ├── input_guard.py             Prompt injection
│   ├── mcp_circuit_breaker.py     MCP resilience
│   ├── statusline.py              Terminal status bar
│   └── ...                        37 more hooks
│
├── agents/                        13 active + 3 teams + 4 archived
│   ├── navigator.md               Strategic (Opus, memory:user)
│   ├── builder.md                 Code (Sonnet, worktree)
│   ├── reviewer.md                Review (Sonnet, memory:project)
│   ├── sec-auditor.md             Security (Opus, memory:project)
│   ├── teams/                     review-squad · build-squad · research-squad
│   └── _archived/                 4 consolidated agents
│
├── skills/
│   ├── core/                      8 universal skills
│   └── extensions/                9 domain skills
│
├── assets/                        Visual assets
│   ├── banner.svg                 Hero banner (animated)
│   └── pipeline.svg               Hook execution pipeline diagram
│
├── tests/                         712 tests · 23 files
├── docs/                          Architecture · guides · anti-patterns
├── mcp-profiles/                  3 profiles (core/science/deploy)
└── .github/workflows/ci.yml       pytest + ruff + mypy + secrets scan
```

</details>

<details>
<summary><b>Documentation Index</b></summary>

| Document | Description |
|----------|------------|
| [Architecture](docs/architecture.md) | 6-layer system design |
| [Evidence Policy](docs/evidence-policy.md) | Anti-hallucination + Confidence Scoring |
| [Hooks Guide](docs/hooks-guide.md) | All 40 hooks with examples |
| [Skills Guide](docs/skills-guide.md) | Creating and managing skills |
| [Anti-Patterns](docs/anti-patterns.md) | 9 critical mistakes to avoid |
| [Troubleshooting](docs/troubleshooting.md) | 10-point diagnostic checklist |
| [CONTRIBUTING](CONTRIBUTING.md) | Contribution guidelines |
| [CHANGELOG](CHANGELOG.md) | Version history |

</details>

---

## Used in Production

This config runs on a live system (29K LOC, real users, real deploys):

- `pre_commit_guard` blocked accidental push to `main` during a hotfix
- `pattern_extractor` auto-logged debugging lessons from `fix:` commits
- `memory_guard` kept `activeContext.md` current across 3 deploy cycles

> Not a demo. Real system. Real incidents.

---

<p align="center">
  <img src="https://img.shields.io/badge/Built_with-Evidence%2C_not_hope-00f5ff?style=for-the-badge&labelColor=02020f" alt="Built with Evidence"/>
  &nbsp;&nbsp;
  <img src="https://img.shields.io/badge/0_tokens-hook_overhead-00ff9f?style=for-the-badge&labelColor=02020f" alt="Zero token overhead"/>
  &nbsp;&nbsp;
  <img src="https://img.shields.io/badge/40_hooks-always_on-ff2d78?style=for-the-badge&labelColor=02020f" alt="40 hooks always on"/>
</p>
