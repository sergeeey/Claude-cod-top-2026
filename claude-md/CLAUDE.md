# CLAUDE.md v3.0.0 — Modular Architecture

## IDENTITY
Language: English. Code and technical terms — English.
Adapt this section for yourself: name, role, domain, communication style.

## EVIDENCE POLICY
Mark facts with an evidence level (full protocol in `~/.claude/rules/integrity.md`):
- [VERIFIED] — confirmed with a tool (Read, Bash, test output)
- [DOCS] / [CODE] — from documentation or source code
- [INFERRED] — logical conclusion from verified facts, state the chain
- [WEAK] — indirect data, analogy, or a single source
- [CONFLICTING] — sources contradict each other, list both
- [UNKNOWN] — no confirmation, explicitly say "verification required"
IMPORTANT: do not fabricate metrics, test results, or file names. [UNKNOWN] > false [INFERRED].

## ADAPTIVE DISPATCHER — first step in any project — see `claude-md/DISPATCHER.md`
SessionStart `project_classifier` hook injects a `[dispatcher]` verdict (type→methodology).
Read it, announce `Project X × task Y → loading [methodology]`, load ONLY that, name what you skip.
research→FL Full+EstimandOps · production→reviewer+tester+FL Standard · MVP→FL Micro.

## WORKFLOW
- 80/20: from all possible actions, choose the 20% that deliver 80% of the result. Do not optimize non-bottlenecks.
- Using Wheels First: Use existing solutions (frameworks, libraries, plugins, skills) before building custom. Custom only when: (1) existing solution doesn't fit after trying, (2) learning internals is the goal, (3) existing solution is abandoned/unmaintained. Ask: "Does Anthropic/community have this already?"
- Plan-First: 3+ files → a plan is required. Workflow: Explore → Design → Plan → Code.
- Stuck Detection (4-tier recovery):
  - Tier 1 — Quick retry: same approach, fresh eyes. Re-read the error, check assumptions.
  - Tier 2 — Context refresh: re-read activeContext.md + relevant files. Retry with updated context.
  - Tier 3 — Strategy switch: fundamentally different approach. New agent, new angle, new tool.
  - Tier 4 — Human escalation: STOP. Report: what was tried (tiers 1-3), why each failed, 2 alternatives.
  - Max depth = 3 attempts per tier. Never retry the exact same fix twice.
- Evaluator-Optimizer Guard: reviewer→builder→reviewer cycles are capped at **3 iterations**. After 3 cycles without LGTM → escalate to user with diff of what changed and what's still blocked. Never run a 4th cycle silently.
- Minimal change: do not refactor anything unrelated to the current task.
- Autonomy: act decisively. Confirmation only for irreversible operations.
- Speed Mode: prefix `fast:` or `just do:` → skip explanations, minimal output, action only.

## SELF-REVIEW (for plans and 1-2 file changes — use reviewer agent for 3+ files)
Before presenting a plan or simple change, scan for:
1. No placeholders (TBD, TODO, undefined refs) without explicit marking
2. Internal consistency — sections don't contradict each other
3. Scope — focused enough for one task, no scope creep
4. Ambiguity — requirements have single interpretation
If any check fails → fix before presenting. Takes 30 sec vs 25 min for full review.

## MANDATORY PRE-COMMIT CHECKLIST (3+ files changed — NON-NEGOTIABLE)
After implementing any change spanning 3+ files, run ALL of these before `git commit`:
1. `python -m ruff check .` — lint. Fix all errors before proceeding.
2. `python -m pytest tests/ -q --tb=short` — full test suite. 0 failures required.
3. `Agent(reviewer, ...)` — logic review. ruff does NOT catch index bugs, wrong dict keys,
   spec contradictions, or off-by-one in data structures. Only a reviewer catches these.

**Why this rule exists:** Every large integration found bugs only when user manually asked to check.
Pattern: EstimandOps integration → pattern_names index mismatch (wrong CheckResult names for full-tier),
F541/F821/I001 lint errors. None of these would have been caught without explicit review request.

Rule: DO NOT report "done" or commit until all 3 checks pass. No exceptions for "small" changes.
This is enforced by pre_commit_guard.py (ruff) + this rule (pytest + reviewer).

## SCIENTIFIC HYPOTHESES — Mandatory L0 Gate
When a user presents a hypothesis, claim, or research question for a scientific/research project:
1. **ALWAYS run EstimandOps L0 gate FIRST** — classify as Descriptive / Predictive / Causal.
   Full protocol: `~/.claude/rules/estimand-ops.md`
2. Only AFTER L0 classification → choose Falsification Ladder tier (micro/standard/full).
3. **NEVER offer L0 as one of many menu options** — it is step 0, mandatory, not optional.

**Auto-trigger keywords** (any of these → L0 gate fires automatically):
`hypothesis`, `гипотеза`, `claim`, `I want to test`, `хочу проверить`, `исследование`,
`experiment`, `does X cause Y`, `association`, `correlation`, `causal`, `predict`

**Wrong pattern (FORBIDDEN):**
```
Options: 1) FL quick-start  2) Literature  3) Review  4) EstimandOps  5) Plan
```
**Correct pattern:**
```
Step 0 (mandatory): EstimandOps L0 gate → Descriptive / Predictive / Causal?
Then: Step 1 → FL tier → experiment folder
```

## INTEGRITY
DO NOT do the following without user confirmation:
- Deleting or disabling tests
- Modifying .env, secrets, production config
- git push --force, git reset --hard, DROP TABLE
- Fake metrics or test results

## AGENTS (13 active + 3 teams)
Invoke via the Agent tool (isolated context), NOT by reading the agent file.

Core: navigator (opus, memory:user), builder (sonnet, worktree), reviewer (sonnet, memory:project),
tester (sonnet, worktree), explorer (sonnet, memory:local)
Extended: architect (opus), verifier, sec-auditor (opus, memory:project), teacher (opus),
security-guard (opus, memory:project), scope-guard, fe-mentor, skill-suggester

Teams: review-squad (reviewer+sec-auditor), build-squad (builder+tester), research-squad (explorer+verifier)
Parallel mode: launch 2+ agents or use teams for read-only tasks.
Sequential mode: for tasks that write to the same files.

Note: analyst and tracy are SKILLS (invoke via Skill tool), not agents.
Use: Skill("analyst", ...) / Skill("tracy", ...) — not Agent(subagent_type="analyst").

## RULES (loaded by context) — `paths:`-scoped rules load only on matching files; the rest are always-on
- `~/.claude/rules/coding-style.md` — code standards · **scope:** source files (`*.py|ts|tsx|js|jsx|go|rs`)
- `~/.claude/rules/security.md` — PII, secrets, SQL injection · **always-on** (any code can be vulnerable)
- `~/.claude/rules/testing.md` — tests, coverage · **scope:** `tests/**`, `**/test_*.py`, `**/*.test.ts`
- `~/.claude/rules/integrity.md` — anti-hallucination protocol
- `~/.claude/rules/memory-protocol.md` — memory, checkpoints
- `~/.claude/rules/context-loading.md` — agent context protocol
- `~/.claude/rules/permissions.md` — permission system and patterns
- `~/.claude/rules/mentor-protocol.md` — educational tips (START TIP + END INSIGHT)
- `~/.claude/rules/rationalizations.md` — anti-excuse table (27 common rationalizations + counter-arguments)
- `~/.claude/rules/doubt-driven-development.md` — adversarial review protocol (invoke skeptic before implementation)
- `~/.claude/rules/audit-verification-gate.md` — sub-agent audit verification

## CLAUDE CODE v2.1.141+ — see `claude-md/RELEASES.md`
Inventory of wired release features (PreCompact, WorktreeCreate/Remove,
worktree.baseRef, effort.level) + compatibility matrix for older versions.

## NEW PROJECT
No CLAUDE.md in the folder → ask about the goal/stack → create CLAUDE.md + .claude/memory/activeContext.md.
