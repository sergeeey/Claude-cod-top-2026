# CLAUDE.md v11.1 — Modular Architecture

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

## WORKFLOW
- 80/20: from all possible actions, choose the 20% that deliver 80% of the result. Do not optimize non-bottlenecks.
- Plan-First: 3+ files → a plan is required. Workflow: Explore → Design → Plan → Code.
- Stuck Detection: 3 failed attempts → STOP. Report what was tried, propose an alternative.
- Minimal change: do not refactor anything unrelated to the current task.
- Autonomy: act decisively. Confirmation only for irreversible operations.

## INTEGRITY
DO NOT do the following without user confirmation:
- Deleting or disabling tests
- Modifying .env, secrets, production config
- git push --force, git reset --hard, DROP TABLE
- Fake metrics or test results

## AGENTS (5 core + 8 extended)
Invoke via the Agent tool (isolated context), NOT by reading the agent file.

Core (loaded by default):
- `navigator` (opus) — architecture, planning, session start
- `builder` (sonnet) — code generation from specification
- `reviewer` (opus) — code review, bug hunting
- `tester` (sonnet) — test generation and execution
- `explorer` (sonnet) — codebase search

Extended (available for explicit invocation):
architect, verifier, security-guard, sec-auditor, scope-guard, teacher, fe-mentor, skill-suggester

Parallel mode: launch 2+ agents in one message for read-only tasks (review + security audit).
Sequential mode: for tasks that write to the same files.

## RULES (loaded by context)
- `~/.claude/rules/coding-style.md` — code standards
- `~/.claude/rules/security.md` — PII, secrets, SQL injection
- `~/.claude/rules/testing.md` — tests, coverage
- `~/.claude/rules/integrity.md` — anti-hallucination protocol
- `~/.claude/rules/memory-protocol.md` — memory, checkpoints

## NEW PROJECT
No CLAUDE.md in the folder → ask about the goal/stack → create CLAUDE.md + .claude/memory/activeContext.md.
