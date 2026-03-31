# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/).
## [3.1.0] - 2026-03-31

### Added — Power Modes (inspired by oh-my-claudecode)
- **5 magic keywords** in `keyword_router.py`: `ralph` (persistent), `autopilot` (full autonomy), `ultrawork` (max parallelism), `deep` (thorough analysis), `quick` (speed mode)
- **Russian aliases**: `быстро` → quick, `авто` → autopilot; shorthand `ulw` → ultrawork
- **Additive routing** — power modes fall through to skill suggestions (e.g. `ralph security` activates both)
- **`PowerMode` dataclass** — frozen, type-safe, keeps name + instruction co-located

### Added — Doctor Diagnostic Tool
- **`scripts/doctor.py`** — 11-check configuration audit (Python version, settings.json, hook files, syntax, MCP, memory, CLAUDE.md, agents, skills, ruff, pytest)
- Smart path resolution — works from repo root and installed `~/.claude/` location
- Clean terminal report with ✅/⚠️/❌ scoring and actionable fix suggestions
- Exit codes: 0 = all green, 1 = errors, 2 = warnings only

## [3.0.0] - 2026-03-30

### Added — Hook System Upgrade (Phase 1)
- **Async hooks** — `async_wrapper.py` enables non-blocking execution; `post_format`, `pattern_extractor`, `session_save`, `webhook_notify` now run in background
- **`security_verify.py`** — PreToolUse hook auto-warns on sensitive file edits (.env, auth, payment, secret, migration, crypto)
- **`webhook_notify.py`** — HTTP POST to Slack/Telegram on session events; SSRF-protected (blocks localhost, private IPs, file:// scheme); auto-redacts secrets in payloads
- **`permission_policy.py`** — PermissionRequest hook auto-approves Read/Glob/Grep/safe-bash, auto-denies 39 dangerous patterns, chain-operator bypass protection (&&, ||, ;, |)
- **`env_reload.py`** — FileChanged hook watches .env/.envrc; safe parsing via `shlex.quote()` + regex validation (blocks command injection)
- **`direnv_loader.py`** — CwdChanged hook loads directory-specific .env with path traversal protection
- **`agent_lifecycle.py`** — SubagentStart/Stop hook injects project context + audit logging; explicit --start/--stop flags (no fragile payload heuristics)
- **`config_audit.py`** — ConfigChange hook writes append-only JSON audit trail to ~/.claude/logs/
- **`team_rebalance.py`** — TeammateIdle hook logs idle events + notifies orchestrator for task redistribution
- **7 new hook events**: PermissionRequest, FileChanged, CwdChanged, SubagentStart, SubagentStop, ConfigChange, TeammateIdle

### Added — Agent System Upgrade (Phase 2)
- **Persistent agent memory** — `reviewer` (memory:project), `sec-auditor` (memory:project), `navigator` (memory:user), `explorer` (memory:local)
- **Worktree isolation** — `builder` and `tester` operate in isolated git worktrees (auto-cleanup)
- **Agent Teams** — 3 team configurations:
  - `review-squad`: reviewer + sec-auditor (parallel code review + security audit)
  - `build-squad`: builder + tester (parallel implementation + tests in separate worktrees)
  - `research-squad`: explorer + verifier (sequential search + claim verification)
- **Restricted agent spawning** — `navigator` can only spawn builder/reviewer/tester; `architect` can only spawn builder
- **`agent-teams` skill** — orchestration patterns, SendMessage protocols, conflict resolution, token budget management

### Added — Skills Upgrade (Phase 3)
- **Shell preprocessing** in 3 core skills: `routing-policy` (git status/diff), `tdd-workflow` (pytest --co), `reference-registry` (cat references.md)
- **Path-based activation** for 3 extension skills: `security-audit` (**/*auth*, **/*payment*), `archcode-genomics` (**/*variant*, **/*vcf*), `geoscan` (**/*sentinel*, **/*raster*)
- **Effort levels** — `effort: max` for security-audit, archcode-genomics, geoscan
- **Skills registry v2.0** — added agent-teams to core skills

### Added — Advanced Permissions (Phase 4)
- **31 deny rules** (was 21) — added: Edit test files, Edit/Write .env, docker rm, kubectl delete, alternate test naming patterns
- **`rules/permissions.md`** — compound approval documentation, glob pattern syntax

### Added — Infrastructure (Phase 5)
- **CLAUDE.md v3.0.0** — 66 lines (was 90); MENTOR PROTOCOL extracted to `rules/mentor-protocol.md`
- **8 rules** (was 6) — added `permissions.md` and `mentor-protocol.md`

### Changed
- **utils.py** — 5 new functions: `parse_env_file_safe()` (safe .env parsing with shlex.quote), `is_safe_path()` (path traversal protection), `is_sensitive_file()` (centralized detection), `send_webhook()` (fire-and-forget HTTP), `log_audit_event()` (audit logging)
- **settings.json** — 14 hook events (was 7), 29 hook entries (was 18), 31 deny rules (was 21)
- **reviewer.md** — model kept as sonnet; added memory:project
- **sec-auditor.md** — added memory:project
- **Spinner tips** — 6 new tips for v3.0.0 features

### Security
- **CRITICAL fix**: env_reload.py and direnv_loader.py — command injection via .env values blocked with regex + shlex.quote()
- **CRITICAL fix**: permission_policy.py — chain operator bypass (cat foo && rm -rf) blocked by checking &&/||/;/| BEFORE prefix matching
- **HIGH fix**: webhook_notify.py — SSRF blocked (localhost, private IPs, file:// scheme, AWS metadata 169.254.x)
- **HIGH fix**: direnv_loader.py — path traversal blocked with is_safe_path() home-directory boundary
- **HIGH fix**: permission_policy.py — expanded DANGEROUS_PATTERNS from 18 to 39 (added sudo, mkfs, dd, eval, python -c, base64, powershell -enc, etc.)
- **HIGH fix**: settings.json — added Edit(.env*), Edit(**/*_test.py), Edit(**/*tests.py) deny rules
- **HIGH fix**: security_verify.py — removed duplicate SENSITIVE_PATTERNS, imports from utils.py (DRY)
- **MEDIUM fix**: agent_lifecycle.py — replaced fragile payload heuristic with explicit --start/--stop CLI flags

---


---

## [2.4.0] - 2026-03-30

### Fixed
- **`is_failed_commit()` false positives** — "error:" pattern now matches only at line start, preventing false positives on commit messages like "fix: improve error: handling"
- **Ghost `notification` hook in README** — replaced with actual `keyword_router` and `thinking_level` hooks
- **Version drift** — README, CLAUDE.md, badges all synced to v2.4.0 (were stuck at v2.0.0)
- **Metrics desync** — test count (377→394), hook count (17→18), rules count (5→6), skills count (12→15) all corrected across README and architecture diagram
- **`post_format.py` silent failures** — now catches `FileNotFoundError` when ruff/prettier not installed
- **Inline `import time`** in `plan_mode_guard.py` — moved to top-level
- **Comment numbering skip** in `pre_compact.py` — step 5→4

### Changed
- **Circuit breaker constants** (`FAILURE_THRESHOLD`, `STATE_FILE`) extracted to `utils.py` as single source of truth
- **CLAUDE.md** (in-repo) now lists all 6 rules including `context-loading.md`
- **utils.py** — `is_failed_commit()` rewritten with line-by-line matching for precision

---

## [2.3.0] - 2026-03-28

### Added
- **Gotchas sections** in 11 SKILL.md files — self-learning failure points per skill
- **Thinking-level hook** (`hooks/thinking_level.py`) — auto-suggests `/think ultrathink` for complex tasks
- **Memory templates** — `spec.template.md` and `execution.template.md` for git-native agent memory
- **Memory hygiene** — dedup patterns + trim old entries in pre_compact.py

### Changed
- STUCK DETECTION upgraded to **4-tier crash recovery** (quick retry → context refresh → strategy switch → human escalation)
- Hooks: 16 → 18 (keyword_router + thinking_level)

---

## [2.2.0] - 2026-03-28

### Added
- **CONTEXT LOADING protocol** (`rules/context-loading.md`) — agents read shared state before working; graceful degradation if missing
- **Context Boundary** sections in all 9 agents — formal isolation: what to receive, return, and exclude
- **Deep Interview** (Phase 0) in brainstorming skill — ambiguity gating with weighted scoring, max 3 question rounds
- **Self-review checklist** in CLAUDE.md — 30-sec inline check for plans and 1-2 file changes
- **Keyword router hook** (`hooks/keyword_router.py`) — magic keywords auto-suggest skills (tdd→tdd-workflow, security→security-audit)
- **Skill execution layers** in routing-policy — SAFETY→QUALITY→EXECUTION→ENHANCEMENT priority order
- **Affected-only CI** — detect changed areas, run targeted test subsets before full suite
- **last30days skill** (`skills/extensions/last30days.md`) — stub for external deep research skill (10+ platforms)
- **Research pipeline** (`skills/extensions/research-pipeline/`) — [EXPERIMENTAL] multi-agent asyncio pipeline
- **Progressive compression** in pre_compact.py — preserves critical sections (errors, decisions) during context compression

### Changed
- Rules: 5 → 6 (added context-loading)
- Extensions: 6 → 8 (added last30days, research-pipeline)
- Tests: 377 → 394 (progressive compression tests)
- STUCK DETECTION upgraded to probabilistic debugging (fix→pivot→stop, max depth 3)
- install.sh: `--profile=full` now clones last30days-skill automatically

---

## [2.1.0] - 2026-03-27

### Added
- **Status Line** (`hooks/statusline.py`) — persistent bar showing model, context %, git branch, cost, duration. Color-coded: green <50%, yellow 50-70%, red >70%. Zero token cost.
- **Notification hook** — audio beep (800Hz, 300ms) when Claude finishes and waits for input. Configured in settings.json under `Notification` event.
- **`autoUpdatesChannel: "stable"`** — default update channel now skips releases with regressions (~1 week delay vs `latest`).
- **Tips section in README** — `/btw` command for side questions, stable channel recommendation, notification hook.

### Changed
- Hook count: 16 → 17 (added Notification)
- README updated with Status Line section, Tips & Recommended Settings

---

## [2.0.0] - 2026-03-19

### Added
- **hooks/utils.py** — 13 shared functions, DRY refactoring (~200 LOC duplication removed)
- **7 new test files** — test_pre_commit_guard, test_checkpoint_guard, test_memory_guard, test_plan_mode_guard, test_session_hooks, test_circuit_breaker_post, test_session_start
- **mypy strict** type checking in CI pipeline
- Agent archival system (`agents/_archived/`)

### Changed
- **v13.0 README** — full rewrite with architecture visualization, updated metrics
- **Agent consolidation** — 13 → 9 active agents (security-guard merged into sec-auditor, scope-guard replaced by drift_guard hook, fe-mentor and skill-suggester archived)
- **Coverage** — 56% → 82% (295 tests, was 120)
- **Python target** — 3.8 → 3.11 (matches CI matrix)
- **MCP profiles** — parametrized paths ($HOME instead of hardcoded)

### Security
- **11 findings sanitized** — removed local file paths, Zenodo DOI, Sentry UUID, zone IDs, project names, personal name from all public files
- Hardcoded `/c/Users/serge/` replaced with `$HOME/` in settings.json and mcp-profiles

### Fixed
- `plan_mode_guard.py` — restored missing `import json` (NameError regression)
- Dead `import json` removed from 4 hooks after DRY refactoring
- `emit_hook_result()` adopted in pre_commit_guard, pattern_extractor, post_commit_memory
- Ruff lint: unused imports, import sorting, line length violations

---

## [1.4.0] - 2026-03-14

### Changed
- **Full English translation** — all 60+ markdown files translated from Russian to English
- Removed `README.en.md` — `README.md` is now English-only
- Removed "103% coverage" overclaim from audit section
- Added "Who This Config is NOT For" section to README — honest positioning vs Superpowers/marketplace configs
- Default install profile changed from `standard` to `minimal` — lower barrier to entry
- Hooks count updated 12 → 14 in all references
- Install.sh profile descriptions translated to English

---

## [1.3.0] - 2026-03-13

### Added
- **Eval Framework** (`tests/eval/`) — 6 test cases (TC-001..TC-006) with objective assertions for config behavior
  - TC-001: Evidence Markers Presence
  - TC-002: No Fabrication Without Read
  - TC-003: TDD Test-First Order
  - TC-004: PII Redaction Hook
  - TC-005: Dangerous Command Blocking
  - TC-006: Adversarial Evidence Bypass
- **run_eval.sh** — headless eval runner via `claude -p`, generates timestamped reports
- **Nexus-lite** (Auto-Recording Decisions) — `post_commit_memory.py` auto-extracts architectural decisions from commit prefixes (`arch:`, `decision:`, `security:`, `pattern:`) into `decisions.md`

### Changed
- `post_commit_memory.py` — extended with decision extraction and auto-recording

---

## [1.2.0] - 2026-03-13

### Added
- **InputGuard hook** — prompt injection detection for MCP servers (7 categories, HIGH auto-block)
- **CircuitBreaker hook** — MCP resilience (CLOSED→OPEN→HALF_OPEN), fallback suggestions
- **CircuitBreaker PostToolUse** — records MCP failures/successes, completes resilience cycle
- **DoubterAgent (Pass 3)** — adversarial validation in reviewer agent (ACCEPT/CHALLENGE/REJECT)
- **Confidence Scoring** — quantified evidence levels (HIGH/MEDIUM/LOW/SPECULATIVE) in integrity.md
- Cross-repo analysis: cross-project pattern analysis integrated
- NotebookLM knowledge base audit: verified against 50+ sources from 2026 AI engineering corpus

### Changed
- `settings.json` — new `mcp__*` matcher for InputGuard + CircuitBreaker (runs before locality guard)
- `integrity.md` — added Confidence Scoring section with evidence-weighted rules
- `testing.md` — coverage threshold raised to ≥80% (production), added pre-commit coverage gate

---

## [1.1.0] - 2026-03-13

### Added
- **`--link` mode** in install.sh — symlinks instead of copies, auto-update via `git pull`
- **Windows symlink check** — validates Developer Mode before creating symlinks
- **Auto-update hook** — SessionStart runs `git pull --ff-only` for linked installs
- **CLI arguments** — `bash install.sh [--link] [minimal|standard|full] [--help]`
- **OSS infrastructure** — CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, CHANGELOG.md
- **GitHub templates** — issue templates (bug/feature), PR template
- **README.en.md** — English documentation (removed in v1.4.0, README.md is now English-only)
- **Smoke tests** — test_install.sh, test_hooks.sh, test_skills.sh

### Fixed
- `safe_link` crash when destination is a directory
- `backup_file` no-op on directories (was calling `cp` without `-r`)
- Dead code: `--quiet` flag conflicted with stdout check in session_start.py
- Unused `import os` in session_start.py
- Silent ignore of unknown CLI arguments
- Version mismatch (`v11.0` in README comparison table)

## [1.0.0] - 2026-03-13

### Added
- **Evidence Policy** — 8 markers ([VERIFIED], [DOCS], [CODE], [INFERRED], [WEAK], [CONFLICTING], [UNKNOWN], [MEMORY])
- **CLAUDE.md v11.0** — modular architecture, ~52 lines, token-optimized
- **11 hooks** — deterministic behavioral guards (read_before_edit, pre_commit_guard, mcp_locality_guard, session_start, pii_redact, etc.)
- **10 skills** — domain knowledge loaded on-trigger (tdd-workflow, security-audit, routing-policy, brainstorming, mentor-mode, suno-music, geoscan, archcode-genomics, git-worktrees, notebooklm)
- **13 agents** — 5 core (navigator, builder, reviewer, tester, explorer) + 8 extended
- **5 rules** — coding-style, security, testing, integrity, memory-protocol
- **3 MCP profiles** — core, science, deploy with switch script
- **PII redaction** — automatic masking of national IDs, phone, email before external MCP
- **install.sh** — interactive installer with 3 profiles, backup, conflict resolution
- **Routing Policy** — task→skill→agent→tools decision matrix with 5 Hard Guards
- **TDD Workflow** — RED→GREEN→REFACTOR enforcement with rationalization prevention
- **Session memory** — activeContext.md auto-loaded at start, updated at commits
- **80/20 principle** — embedded in navigator, scope-guard, brainstorming, CLAUDE.md
- **Documentation** — architecture, evidence-policy, hooks-guide, skills-guide, mcp-profiles, anti-patterns, troubleshooting, 3 session examples

## [0.1.0] - 2026-03-12

### Added
- Initial repository structure
- Basic CLAUDE.md configuration
- Memory bank templates
