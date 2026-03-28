# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/).

---

## [2.3.0] - 2026-03-28

### Added
- **Gotchas sections** in 11 SKILL.md files — self-learning failure points per skill
- **Thinking-level hook** (`hooks/thinking_level.py`) — auto-suggests `/think ultrathink` for complex tasks
- **Memory templates** — `spec.template.md` and `execution.template.md` for git-native agent memory
- **Memory hygiene** — dedup patterns + trim old entries in pre_compact.py

### Changed
- STUCK DETECTION upgraded to **4-tier crash recovery** (quick retry → context refresh → strategy switch → human escalation)
- Hooks: 17 → 19 (keyword_router + thinking_level)

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
