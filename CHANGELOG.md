# Changelog / История изменений

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/).

Все значимые изменения документируются здесь.
Формат: [Keep a Changelog](https://keepachangelog.com/).

---

## [1.2.0] - 2026-03-13

### Added / Добавлено
- **InputGuard hook** — prompt injection detection for MCP servers (7 categories, HIGH auto-block)
- **CircuitBreaker hook** — MCP resilience (CLOSED→OPEN→HALF_OPEN), fallback suggestions
- **CircuitBreaker PostToolUse** — records MCP failures/successes, completes resilience cycle
- **DoubterAgent (Pass 3)** — adversarial validation in reviewer agent (ACCEPT/CHALLENGE/REJECT)
- **Confidence Scoring** — quantified evidence levels (HIGH/MEDIUM/LOW/SPECULATIVE) in integrity.md
- Cross-repo analysis: patterns from VeriFind, ContextProof, 24-na-7, TERAG integrated
- NotebookLM knowledge base audit: verified 100% coverage of 2026 best practices

### Changed / Изменено
- `settings.json` — new `mcp__*` matcher for InputGuard + CircuitBreaker (runs before locality guard)
- `integrity.md` — added Confidence Scoring section with evidence-weighted rules
- `testing.md` — coverage threshold raised to ≥80% (production), added pre-commit coverage gate

---

## [1.1.0] - 2026-03-13

### Added / Добавлено
- **`--link` mode** in install.sh — symlinks instead of copies, auto-update via `git pull`
- **Windows symlink check** — validates Developer Mode before creating symlinks
- **Auto-update hook** — SessionStart runs `git pull --ff-only` for linked installs
- **CLI arguments** — `bash install.sh [--link] [minimal|standard|full] [--help]`
- **OSS infrastructure** — CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, CHANGELOG.md
- **GitHub templates** — issue templates (bug/feature), PR template
- **README.en.md** — English documentation for international audience
- **Smoke tests** — test_install.sh, test_hooks.sh, test_skills.sh

### Fixed / Исправлено
- `safe_link` crash when destination is a directory
- `backup_file` no-op on directories (was calling `cp` without `-r`)
- Dead code: `--quiet` flag conflicted with stdout check in session_start.py
- Unused `import os` in session_start.py
- Silent ignore of unknown CLI arguments
- Version mismatch (`v11.0` in README comparison table)

## [1.0.0] - 2026-03-13

### Added / Добавлено
- **Evidence Policy** — 8 markers ([VERIFIED], [DOCS], [CODE], [INFERRED], [WEAK], [CONFLICTING], [UNKNOWN], [MEMORY])
- **CLAUDE.md v11.0** — modular architecture, ~52 lines, token-optimized
- **11 hooks** — deterministic behavioral guards (read_before_edit, pre_commit_guard, mcp_locality_guard, session_start, pii_redact, etc.)
- **10 skills** — domain knowledge loaded on-trigger (tdd-workflow, security-audit, routing-policy, brainstorming, mentor-mode, suno-music, geoscan, archcode-genomics, git-worktrees, notebooklm)
- **13 agents** — 5 core (navigator, builder, reviewer, tester, explorer) + 8 extended
- **5 rules** — coding-style, security, testing, integrity, memory-protocol
- **3 MCP profiles** — core, science, deploy with switch script
- **PII redaction** — automatic masking of IIN, BIN, phone, email before external MCP
- **install.sh** — interactive installer with 3 profiles, backup, conflict resolution
- **Routing Policy** — task→skill→agent→tools decision matrix with 5 Hard Guards
- **TDD Workflow** — RED→GREEN→REFACTOR enforcement with rationalization prevention
- **Session memory** — activeContext.md auto-loaded at start, updated at commits
- **80/20 principle** — embedded in navigator, scope-guard, brainstorming, CLAUDE.md
- **Documentation** — architecture, evidence-policy, hooks-guide, skills-guide, mcp-profiles, anti-patterns, troubleshooting, 3 session examples

## [0.1.0] - 2026-03-12

### Added / Добавлено
- Initial repository structure
- Basic CLAUDE.md configuration
- Memory bank templates
