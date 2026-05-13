---
name: example-agent
description: Example agent showing best practices and full feature set. Copy this template to create new agents.
tools: Read, Edit, Write, Bash, Glob, Grep
model: sonnet
maxTurns: 15
isolation: worktree
effort: medium
permissionMode: acceptEdits
skills: []
memory: project
---

# Example Agent — Living Documentation

> **Purpose:** This is a **reference implementation** showing how to write agents in Claude Code v2.3+.
> Copy this file, modify frontmatter and content, test → you have a working agent.

---

## Frontmatter Explained

```yaml
name: example-agent
# REQUIRED. Used to invoke: Agent(example-agent, ...)
# Convention: lowercase-with-hyphens

description: Example agent showing best practices...
# REQUIRED. Shown in agent list and tool docs.
# Should answer: "When do I use this agent?"

tools: Read, Edit, Write, Bash, Glob, Grep
# REQUIRED. Which tools this agent can use.
# Available: Read, Edit, Write, Bash, Glob, Grep, WebFetch, WebSearch
# Principle: Give minimum needed tools (security + clarity)

model: sonnet
# OPTIONAL. Default: inherit from parent.
# Options: sonnet | opus | haiku
# Use opus for: complex reasoning, research, red-teaming
# Use sonnet for: most tasks (best speed/quality ratio)
# Use haiku for: simple tasks, high volume

maxTurns: 15
# OPTIONAL. Default: 10
# How many back-and-forth turns before agent stops
# Increase for: complex multi-step tasks
# Decrease for: simple focused tasks

isolation: worktree
# OPTIONAL. Default: none
# Options: worktree
# Use worktree when: agent writes code, experiments, large changes
# Skip worktree when: agent is read-only (reviewer, explorer)

effort: medium
# OPTIONAL. Informational only.
# Options: small | medium | large
# Helps users estimate task time

permissionMode: acceptEdits
# OPTIONAL. Default: ask
# Options: ask | acceptEdits | acceptAll
# acceptEdits = auto-approve Edit/Write (fast iteration)
# ask = prompt user for every tool (safe but slow)

skills: []
# OPTIONAL. List of skills to bundle with this agent.
# Example: skills: [routing-policy, security-audit]
# Skills auto-synced via scripts/sync-agent-skills.py

memory: project
# OPTIONAL. What memory scope to load.
# Options: user | project | local | none
# user = load user profile (for personalization)
# project = load project context (decisions, patterns)
# local = load only this agent's past runs
# none = start fresh (for isolation)
```

---

## Agent Body Structure

### Section 1: Project Context (ALWAYS FIRST)

Every agent should read project context before starting:

```markdown
## Project Context (read first)
Before starting your task, read the project's activeContext.md:
1. Look for `.claude/memory/activeContext.md` in current or parent directories
2. If found, read it to understand: current task, recent decisions, project conventions
3. Adapt your output to the project's stack and conventions
```

**Why:** Prevents agents from working in vacuum, respects project decisions.

### Section 2: Context Boundary (ISOLATION PROTOCOL)

Define what this agent receives and returns:

```markdown
## Context Boundary
- **Receives:** [What information this agent gets from orchestrator]
- **Returns:** [What information this agent sends back]
- **Must NOT receive:** [What information is intentionally hidden]
```

**Example (builder agent):**
```markdown
## Context Boundary
- **Receives:** Spec from architect, target file paths, coding standards
- **Returns:** Working code with `# WHY:` comments, linter/test output
- **Must NOT receive:** Business context beyond spec, other agents' reasoning
```

**Why:** Prevents context pollution, keeps agents focused.

### Section 3: Agent Identity

One-sentence identity statement:

```markdown
You are a [role] who [does what].
```

**Examples:**
- "You are a developer implementing solutions according to architect's plan."
- "You are a QA engineer with pedagogical focus."
- "You are a security auditor finding vulnerabilities before deployment."

**Why:** Sets tone and expectations for agent's behavior.

### Section 4: Standards & Conventions

Project-specific or agent-specific standards:

```markdown
Standards (always):
- Python 3.11+, type hints on all functions
- Docstrings in English for public methods
- structlog for logging (not print)
- Pydantic for input/output data
```

**Why:** Ensures consistent output across agent runs.

### Section 5: Process Steps

Clear numbered steps for what agent should do:

```markdown
Process:
1. Read the spec from orchestrator
2. Identify files to modify
3. Write implementation with `# WHY:` comments
4. Run linter: `ruff check --fix`
5. Run tests if they exist: `pytest -x`
6. Return: code changes + test output
```

**Why:** Reduces ambiguity, ensures agent doesn't skip steps.

### Section 6: Output Format (if applicable)

Template for agent's output:

```markdown
Output format:
## Summary
[1-2 sentences: what was done]

## Changes
- File 1: [what changed]
- File 2: [what changed]

## Tests
[pytest output or "No tests found"]

## Next Steps
[What orchestrator should do next]
```

**Why:** Structured output = easier to parse by orchestrator.

### Section 7: Constraints & Anti-Patterns

What agent should NOT do:

```markdown
Constraints:
- Never write stubs without explicit instruction
- Never skip tests if test file exists
- Never commit secrets or hardcoded credentials
- Never refactor code unrelated to the task

Anti-patterns to avoid:
- ❌ "This looks good" without running tests
- ❌ Implementing features not in spec (scope creep)
- ❌ Copy-pasting code without understanding
```

**Why:** Prevents common mistakes, sets boundaries.

---

## Example Agent Invocations

### Basic Invocation
```markdown
Agent(example-agent, description="Short task description", prompt="Full task details here")
```

### With Worktree Isolation
```markdown
Agent(
  example-agent,
  isolation="worktree",
  description="Experimental refactor",
  prompt="Try async refactor of auth module. If it works, great. If not, discard worktree."
)
```

### Parallel Agents (same type)
```markdown
Agent(example-agent, description="Module A", prompt="Implement module A")
Agent(example-agent, description="Module B", prompt="Implement module B")
# Both run in parallel, different worktrees
```

### Background Execution
```markdown
Agent(
  example-agent,
  run_in_background=true,
  description="Long-running analysis",
  prompt="Analyze 1000 files for patterns. Notify when done."
)
# You'll be notified when agent finishes (don't poll)
```

---

## Agent Testing Checklist

Before deploying a new agent:

- [ ] Frontmatter valid (name, description, tools all present)
- [ ] Project Context section exists (reads activeContext.md)
- [ ] Context Boundary defined (receives/returns/must-not-receive)
- [ ] Identity statement clear (1 sentence role)
- [ ] Process steps numbered and clear
- [ ] Constraints listed (what NOT to do)
- [ ] Test with simple task (happy path)
- [ ] Test with complex task (multi-step)
- [ ] Test with invalid input (error handling)
- [ ] Test isolation mode (if using worktree)
- [ ] Document in agents/README.md

---

## Integration With Other Patterns

### Pattern 1: Skill Propagation
If agent uses skills, declare in frontmatter:
```yaml
skills: [routing-policy, security-audit]
```

Then run sync:
```bash
python scripts/sync-agent-skills.py
```

Skills copied to `agents/example-agent/bundled-skills/`.

### Pattern 2: Doubt-Driven Development
For architecture/hypothesis agents, invoke skeptic:
```markdown
## Process
1. Propose solution
2. Invoke skeptic: Agent(skeptic, prompt="Red-team this: [proposal]")
3. Address skeptic concerns
4. Document decision in ADR
```

### Pattern 3: Validation Tooling
Before deploying agent updates:
```bash
# Check if agent file valid
python scripts/validate-agents.py --agent example-agent

# Check if bundled skills in sync
python scripts/sync-agent-skills.py --check --agent example-agent
```

---

## Real-World Example: Builder Agent

See `agents/builder.md` for production example:
- Uses `isolation: worktree` (writes code)
- `tools: Read, Edit, Write, Bash, Glob` (minimal set)
- `permissionMode: acceptEdits` (fast iteration)
- Clear process: read spec → write code → lint → test
- Constraints: never write stubs, never skip tests

**Result:** Used in 100+ tasks, 95% success rate, 0 security incidents.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-05-11 | Initial version (v2.3 agent protocol) |
| | Added frontmatter annotations |
| | Added testing checklist |
| | Added integration patterns |

---

**Status:** ACTIVE — use as template for new agents  
**Protocol version:** v2.3  
**Next review:** When agent protocol changes (v2.4+)  
**Maintainer:** Auto-updated with breaking changes

---

## References
- Agent tool documentation: see system instructions
- Existing agents: `agents/builder.md`, `agents/tester.md`, `agents/skeptic.md`
- Agent teams: `agents/teams/build-squad.md`, `agents/teams/review-squad.md`
- Skill propagation: `scripts/sync-agent-skills.py`
- Validation: `scripts/validate-agents.py` (TODO)
