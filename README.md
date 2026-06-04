<p align="center">
  <img src="assets/banner.svg" alt="Claude Code Hooks — Top 2026" width="100%"/>
</p>

<p align="center">
  <a href="https://github.com/sergeeey/Claude-cod-top-2026/actions/workflows/ci.yml">
    <img src="https://github.com/sergeeey/Claude-cod-top-2026/actions/workflows/ci.yml/badge.svg" alt="CI"/>
  </a>
  &nbsp;
  <img src="https://img.shields.io/badge/version-3.8.0-bf5fff?style=flat-square&logo=anthropic&logoColor=white" alt="Version"/>
  &nbsp;
  <img src="https://img.shields.io/badge/hooks-60_guards-00f5ff?style=flat-square" alt="Hooks"/>
  &nbsp;
  <img src="https://img.shields.io/badge/agents-15_%2B_3_teams-ff2d78?style=flat-square" alt="Agents"/>
  &nbsp;
  <img src="https://img.shields.io/badge/Tests-1364-00ff9f?style=flat-square" alt="Tests"/>
  &nbsp;
  <img src="https://img.shields.io/badge/Coverage-75%25-00ff9f?style=flat-square" alt="Coverage"/>
  &nbsp;
  <img src="https://img.shields.io/badge/mypy-checked-0969DA?style=flat-square" alt="mypy"/>
  &nbsp;
  <img src="https://img.shields.io/badge/license-MIT-555?style=flat-square" alt="License"/>
</p>

<h2 align="center">The bug that breaks AI code in production</h2>

<p align="center">
  Agent writes a test.<br/>
  Runs it on synthetic data it just generated.<br/>
  Reports <code>F1=1.000 ✅ SUCCESS</code>.<br/>
  You deploy.<br/>
  <b>Real-world data crashes everything.</b>
</p>

<p align="center">
  This is called <b>Validation Theater</b>.<br/>
  This is the only Claude Code config that catches it automatically.
</p>

<p align="center">
  Every claim carries an evidence marker —<br/>
  <code>[VERIFIED-REAL]</code> (real data, sources cited) vs <code>[VERIFIED-SYNTHETIC]</code> (mock data, never valid for production claims).<br/>
  Hard rule baked into <code>rules/integrity.md</code>: <b>synthetic ≠ real</b>.
</p>

<p align="center">
  <sub>Backed by 60 hooks · 15 agents + 3 teams · 1364 tests · 75% coverage · MIT · Deploy in 5 min</sub>
</p>

<p align="center">
  <b>📋 No install? Get the rules only:</b><br/>
  <a href="docs/anti-hallucination.md"><code>docs/anti-hallucination.md</code></a> — single file, ~500 tokens, paste into your <code>CLAUDE.md</code>.<br/>
  Catches Validation Theater on its own. Compatible with any Claude Code config.
</p>

---

<p align="center">
  <img src="assets/pipeline.svg" alt="Hook Execution Pipeline" width="100%"/>
</p>

---

## Why This Config?

> **Claude Code без этого конфига** — как Ferrari на ручнике: мощный, но 60% потенциала потеряно.
> **With this config** — каждый коммит верифицирован, каждый агент помнит контекст, каждая ошибка записана и больше не повторяется.

Most configs are a single `CLAUDE.md` bloated to 3000+ tokens. This is different:

| | Typical config | **This config** |
|---|---|---|
| **Tokens/msg** | 3 000 – 5 000 | **~500** (core only) |
| **Hallucinations** | "trust me" | Evidence Policy + Confidence Scoring |
| **MCP failures** | session hangs | CircuitBreaker — auto-recovery in 60s |
| **Prompt injection** | no protection | InputGuard — 8 categories, auto-block |
| **PII leakage** | hope for the best | 12 regex patterns + auto-redact |
| **Code review** | optional | review-squad — parallel reviewer + sec-auditor |
| **Permissions** | ask for everything | PermissionRequest hook — 75% auto-approved |
| **Agent memory** | stateless | 4 agents with persistent memory across sessions |
| **Tests** | "I'll write them later" | 1364 tests, TDD-first, Test Protection hard rule |

---

## When to Use This vs everything-claude-code

[everything-claude-code](https://github.com/affaan-m/everything-claude-code) is a great alternative — bigger, multi-platform, Anthropic Hackathon Winner. Both are MIT, pick what fits.

**Use [everything-claude-code](https://github.com/affaan-m/everything-claude-code) if:**
- You want **multi-language coverage** (TS, Go, Java, Kotlin, Rust, C++, PHP — 12+ ecosystems)
- You work across **multiple harnesses** (Codex, Cursor, OpenCode, Gemini — not just Claude Code)
- You want a **GUI dashboard** for browsing components
- You like the **paid tier** path (ECC Tools GitHub App, free / pro / enterprise)

**Use this config if:**
- **"Validation Theater" is a $$$ risk for you, not abstract** — Evidence Policy is enforced as hard rule, not just a skill
- You work with **sensitive data** (PII, finance, healthcare) — built-in redaction hook scrubs sensitive strings before any external MCP call
- You need to **read every hook before installing** — only ~10 MB, plain Python, no JS dependencies, every file readable in 10 minutes
- You prefer **Claude Code only with deep specialization** over multi-platform breadth
- You speak **Russian** — README and rules have RU-first sections, useful for CIS dev teams

**Comparison at a glance:**

| | [everything-claude-code](https://github.com/affaan-m/everything-claude-code) | **This config** |
|---|---|---|
| **Surface** | 48 agents · 182 skills · 68 commands · ~31 MB | 15 agents + 3 squads · 65 skills · 60 hooks · ~10 MB |
| **Languages** | TS, Py, Go, Java, Kotlin, Rust, C++, PHP, Perl | Python primarily |
| **Harnesses** | Claude Code, Codex, Cursor, OpenCode, Gemini, Antigravity | Claude Code only |
| **Anti-hallucination** | continuous-learning v2 with confidence scoring | **Evidence Policy + Validation Theater Guard + Audit Verification Gate** (synthetic ≠ real, enforced) |
| **PII / sensitive data** | generic | dedicated redaction hook + local-first (Ollama) |
| **Audit Verification Gate** | not in core | `rules/audit-verification-gate.md` — agent's `[VERIFIED]` = your `[INFERRED]` |
| **Recurring mistake tracking** | instinct-based | `[×N]` counter — after 3 occurrences a mistake becomes a hard rule |
| **License** | MIT (open core, paid GitHub App) | MIT (no paid tier) |

If multi-language / cross-harness matters more than anti-hallucination focus — pick ECC. If anti-hallucination on sensitive data is your job-critical risk — pick this one.

---

## What This Config Does NOT Do

Honest scope fence — to prevent misuse and save your time:

- ❌ **Not multi-language.** Python primarily. TS/JS supported via hooks but agents/skills are Python-tuned.
- ❌ **Not multi-harness.** Claude Code only. No Codex / Cursor / Gemini support — see [everything-claude-code](https://github.com/affaan-m/everything-claude-code) for cross-harness.
- ❌ **Not a GUI / dashboard.** Pure CLI + file-based config. `scripts/hook_metrics.py` is the closest thing (terminal table).
- ❌ **Not a SaaS / managed service.** Self-host only. No paid tier, no telemetry to author.
- ❌ **Not for >50% of generic projects.** This is optimized for **anti-hallucination on sensitive data** (PII, finance, healthcare, research). If your stack doesn't have validation theater risk, the overhead may exceed the value.
- ❌ **Not a replacement for human review.** Hooks catch deterministic mistakes (commits to main, leaked secrets, debug prints). Logic bugs still need `Agent(reviewer)` or human eyes.
- ❌ **Not a methodology textbook.** The rules (`rules/*.md`) document the patterns we use, but they're not a tutorial. Read [`docs/methodology.md`](docs/methodology.md) for the explained version.

---

## 🚀 Start Here (pick your path)

> **New to this?** Don't install everything at once. Pick the path that matches your goal:

| Path | What you get | Time | Command |
|------|-------------|------|---------|
| **Evidence Only** | `[VERIFIED]` markers + anti-hallucination | 2 min | `--profile=minimal` |
| **Daily Driver** | + 60 hooks + 15 agents + 65 skills | 5 min | `--profile=standard` |
| **Full Setup** | + MCP profiles + PII redaction + memory | 10 min | `--profile=full` |

**Minimal path (recommended to start):** installs just 3 files — `CLAUDE.md`, `integrity.md`, `security.md`. No hooks, no agents, no complexity. Add more when you need it.

---

## Quick Start

```bash
# One-liner — Mac / Linux / WSL
git clone https://github.com/sergeeey/Claude-cod-top-2026.git && cd Claude-cod-top-2026 && bash install.sh --profile=standard --non-interactive
```

> **Windows (PowerShell):** `git clone https://github.com/sergeeey/Claude-cod-top-2026.git; cd Claude-cod-top-2026; bash install.sh --profile=standard --non-interactive`
>
> After install: restart Claude Code (`/clear` or new session) — hooks activate automatically.

### Plugin Install (recommended — Claude Code v2.1.80+)

```bash
# Register this repo as a marketplace source (once per machine)
/plugin marketplace add sergeeey/Claude-cod-top-2026

# Install the plugin
/plugin install claude-cod-top-2026
```

> **Windows note:** Claude Code doesn't pre-register third-party marketplaces on Windows.
> Add to your `~/.claude/settings.json` manually if `/plugin marketplace add` fails:
> ```json
> "extraKnownMarketplaces": {
>   "claude-cod-top-2026": {
>     "source": { "source": "github", "repo": "sergeeey/Claude-cod-top-2026" }
>   }
> }
> ```

### Classic Install (all platforms)

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

## 60 Hooks — 25 Events

> Hooks run **100% of the time** — deterministic Python guards, not probabilistic instructions.

<details>
<summary><b>PreToolUse guards (12 hooks)</b></summary>

| Hook | Protects Against |
|------|-----------------|
| `input_guard` | Prompt injection via MCP (8 categories) |
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
<summary><b>PostToolUse audit layer (11 hooks)</b></summary>

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
| `moc_autolink` | Notes written without Obsidian MOC links |
| `observation_capture` | Observations lost after file edits |

</details>

<details>
<summary><b>Lifecycle · Session · Memory (20 hooks)</b></summary>

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
| `thematic_index_router` | Stop | Route wiki entries to thematic indices |

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

pytest tests/ -v --cov=hooks --cov-report=term-missing   # 1364 tests
ruff check hooks/ scripts/ tests/
mypy hooks/utils.py hooks/input_guard.py
bash tests/test_all.sh   # 82 smoke tests
```

```
1364 passing · 0 failing · 75% coverage · 296/296 smoke tests
```

---

## Obsidian Integration

Two automation hooks keep your Obsidian vault in sync with Claude Code activity:

| Hook | Trigger | What it does |
|------|---------|-------------|
| `moc_autolink` | PostToolUse Write/Edit | Tags new notes → auto-links to relevant MOC (Claude-cod, GeoMiro, Research…) |
| `thematic_index_router` | Stop | Routes fresh wiki entries to Claude-Code / Lessons / Projects indices |

**Vault layout** (`~/.claude/memory/`):
```
wiki/          ← processed knowledge (auto-generated)
raw/           ← quick drop → auto-converted at session end
mocs/          ← Maps of Content (6 MOCs)
_auto/wiki/    ← thematic indices (Claude-Code / Lessons / Projects)
daily/         ← session reports
```

`graph.json` colorGroups must be set while **Obsidian is closed** — the app overwrites on launch.

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
├── hooks/                         56 Python guards (52 hooks + 4 support libs)
│   ├── utils.py                   21 shared functions (DRY)
│   ├── settings.json              Hook registry + 27 deny patterns
│   ├── input_guard.py             Prompt injection
│   ├── mcp_circuit_breaker.py     MCP resilience
│   ├── statusline.py              Terminal status bar
│   └── ...                        51 more hooks
│
├── agents/                        14 active + 3 teams
│   ├── navigator.md               Strategic (Opus, memory:user)
│   ├── builder.md                 Code (Sonnet, worktree)
│   ├── reviewer.md                Review (Sonnet, memory:project)
│   ├── sec-auditor.md             Security (Opus, memory:project)
│   └── teams/                     review-squad · build-squad · research-squad
│
├── skills/
│   ├── core/                      9 universal skills
│   └── extensions/                40 domain skills
│
├── assets/                        Visual assets
│   ├── banner.svg                 Hero banner (animated)
│   └── pipeline.svg               Hook execution pipeline diagram
│
├── tests/                         1364 tests · 39 files
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
| [Hooks Guide](docs/hooks-guide.md) | All 60 hooks with examples |
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
  <img src="https://img.shields.io/badge/60_hooks-always_on-ff2d78?style=for-the-badge&labelColor=02020f" alt="60 hooks always on"/>
  <img src="https://img.shields.io/badge/mcp--guard-powered-00f5ff?style=for-the-badge&labelColor=02020f" alt="mcp-guard powered"/>
</p>
