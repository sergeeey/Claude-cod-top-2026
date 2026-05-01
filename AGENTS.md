<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **Claude-cod-top-2026** (2586 symbols, 5616 relationships, 47 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/Claude-cod-top-2026/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/Claude-cod-top-2026/context` | Codebase overview, check index freshness |
| `gitnexus://repo/Claude-cod-top-2026/clusters` | All functional areas |
| `gitnexus://repo/Claude-cod-top-2026/processes` | All execution flows |
| `gitnexus://repo/Claude-cod-top-2026/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

---

## Project Agent Rules — Claude-cod-top-2026

> This section covers project-specific rules for all AI agents (Claude Code subagents, Dispatch, Codex, etc.).
> GitNexus impact rules above take priority for all code edits.

### Read First (every agent, in order)

1. `.claude/memory/activeContext.md` — current branch, last commit, pending tasks
2. `.claude/memory/decisions.md` — ADRs already decided (do not contradict)
3. This file — do not repeat known anti-patterns listed below

### Project Structure

```
hooks/         49 Python hooks + utils.py + learning_tips.py (27 events in settings.json)
agents/        14 agent definitions + 3 squad teams (build / review / research)
skills/        32 skills — core/ (9) + extensions/ (23)
tests/         37 test files — pytest + bash smoke (1093 passing as of 2026-04-26)
rules/         9 markdown rules
mcp-profiles/  3 profiles: core / deploy / science
scripts/       inbox_review.py, populate_vault.py, skill-manager.sh
install.sh     One-command installer for other projects
```

### Development Commands

```bash
python -m pytest tests/ -x -q --tb=short          # full suite
python -m pytest tests/<file>.py -v               # single file
ruff check hooks/ && mypy hooks/ --ignore-missing-imports
python -m pytest tests/ --cov=hooks --cov-report=term-missing
bash tests/smoke_skills.sh && bash tests/smoke_hooks.sh
cp -r skills/extensions/<name> ~/.claude/skills/extensions/<name>  # install skill globally
```

Coverage: ≥86% local/Windows · ≥65% CI/Linux

### Skill Routing

| Request type | Skill |
|---|---|
| Priority / signal vs noise | `snr` |
| Scientific hypothesis | `sci-hypothesis` |
| Git release notes | `changelog-gen` |
| OSINT / due diligence | `lead-research` |
| Meeting transcript | `meeting-insights` |
| Break an idea | `skeptic` |
| Weekly priorities | `tracy` |
| Cross-domain analysis | `analyst` |
| TDD / tests | `tdd-workflow` |
| Parallel agents | `agent-teams` |
| Context management | `context-engineering` |

### What Agents CANNOT Do (without explicit user confirmation)

- `git push` — never without user approval
- `git reset --hard`, `git rebase` — destructive git ops
- Delete or disable tests — fix CODE, not tests
- Edit `.env*`, secrets, production config
- Launch simulations, ML training, or heavy computation autonomously
- Modify `settings.json` without `update-config` skill

### New Skill Checklist

1. Create `skills/extensions/<name>/SKILL.md` with BSV header + YAML frontmatter
2. Register in `skills/registry.yaml`
3. Copy to `~/.claude/skills/extensions/<name>/`
4. No tests required for skills (SKILL.md only)

### Known Anti-Patterns — AVOID

- `[×3]` `datetime.utcnow()` mixed with timezone-aware datetimes → use `datetime.now(timezone.utc)`
- `[×2]` Coverage overclaim — README states metric without tool verification
- `[×2]` squash merge with 2+ commits → second commit lost; run `git log --oneline` on main after merge
- `[×2]` Forward-only workflow without integrity gates

### Evidence Policy

- `[VERIFIED]` — confirmed with tool (Read/Bash/pytest)
- `[INFERRED]` — logical chain from verified facts
- `[UNKNOWN]` — no confirmation. Never fabricate metrics or test results.

### Memory Protocol

Agents do NOT write to memory files directly — return results to orchestrator.
Exception: `tester` agent may append one line to `activeContext.md ## Test Status`.