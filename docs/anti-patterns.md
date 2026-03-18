# Anti-Patterns: 8 Critical Mistakes When Working with Claude Code

Each anti-pattern contains: the problem, an example of a bad and good workflow,
and a reference to the configuration element that protects against this mistake.

---

## 1. Context Overflow

**Problem**: a long session without `/clear` — Claude starts to "forget" earlier
instructions, gets confused, repeats mistakes.

**Bad**:
```
50 messages in a row without clearing.
By the end Claude doesn't remember we use PostgreSQL and suggests MySQL.
Instructions from CLAUDE.md are pushed out of the "attention window".
```

**Good**:
```
/clear after each completed task.
/compact with focus at 50% fill.
Important decisions saved in memory files, not just in chat.
```

**Our solution**:
- `rules/memory-protocol.md` — rules for `/clear` discipline and context overflow at 70%
- Per-project `activeContext.md` — critical context stored outside the session
- `hooks/pre_compact.py` — auto-save context before compaction
- CLAUDE.md limited to 70 lines — maximum free context for work

---

## 2. Hallucination Loops

**Problem**: Claude invents non-existent APIs/methods and gets stuck in a loop
trying to call them.

**Bad**:
```
Claude tries user.getAuthToken(), user.fetchAuthToken(),
user.retrieveToken() — none of them exist.
5 attempts in a row, each with a new invented method.
```

**Good**:
```
"Read the User class and list all available methods.
Do NOT write code until you've confirmed the API."
→ Claude finds user.authenticate() → writes working code.
```

**Our solution**:
- **Evidence Policy** — marker `[VERIFIED]` requires verifying a fact with a tool (Read/Grep)
- **Stuck Detection** — 3 failed attempts → STOP, report what was tried
- **Plan-First** — Explore → Design → Plan → Code (research before coding)
- `rules/integrity.md` — 4 hard prohibitions (NO FABRICATION, NO PHANTOM REFERENCES...)

---

## 3. Vague Prompts

**Problem**: an unclear request → Claude interprets it its own way → result is wrong.

**Bad**:
```
"fix the tests"
→ Claude fixes the wrong test, or "fixes" it by adjusting expected values.
```

**Good**:
```
"Fix the failing test in auth.spec.ts line 45.
The mock returns undefined instead of a user object.
Expected: { id: 1, role: 'admin' }."
→ Claude fixes the specific problem in 1 iteration.
```

**Our solution**:
- **80/20 rule** — Claude focuses on a specific, measurable result
- `skills/brainstorming/` — Socratic Design with clarifying questions before implementation
- **Autonomy + Plan-First** — when unclear, Claude asks rather than guesses

---

## 4. Trusting Without Verification

**Problem**: accepting Claude's code without verification → bugs accumulate.

**Bad**:
```
"implement the payment flow" → "Done!" → commit → production breaks.
Code was never run, tests not written.
```

**Good**:
```
implement → write tests → run tests → subagent review → commit.
Every step verified, every fact marked.
```

**Our solution**:
- **Evidence Policy** — culture of verification: every fact marked with an evidence level
- `agents/reviewer.md` (Opus 4.6) — code review before commit
- `skills/tdd-workflow/` — formalized TDD process (RED → GREEN → REFACTOR)
- `hooks/pre_commit_guard.py` — blocking dangerous commands
- `rules/testing.md` — prohibition on deleting/adjusting tests

---

## 5. Monolithic CLAUDE.md

**Problem**: all instructions in a single file of 300+ lines → Claude ignores
rules that are "buried" in the middle of the file.

**Bad**:
```
CLAUDE.md at 515 lines: changelog, agent matrix, style guide,
project history, security checklist, MCP configuration.
→ By the 40th message Claude stops following Evidence Policy
  (it was on line 287).
```

**Good**:
```
CLAUDE.md at 70 lines — core only.
5 rules files — loaded based on task context.
8 skills — Progressive Disclosure, loaded on trigger.
→ Evidence Policy in the top third of CLAUDE.md, always in focus.
```

**Our solution**:
- CLAUDE.md: 70 lines (core) — Identity, Workflow, Evidence Policy, pointers to rules
- `rules/` (5 files, 112 lines total) — loaded when needed, 0 tokens otherwise
- `skills/` (8 skills) — Progressive Disclosure, ~100 tokens for all at startup
- **Result**: 70 lines instead of 515, -86% while preserving functionality

**Numbers**:
| Approach | Lines in CLAUDE.md | Tokens/message | Model Attention |
|----------|--------------------|----------------|-----------------|
| Monolithic | 515 | ~3500 | Diffuse |
| Our modular | 70 | ~500 | Focused |

---

## 6. MCP Overload

**Problem**: 16 MCP servers connected simultaneously → ~20,000 tokens of tool
definitions → slow tool selection, early compaction.

**Bad**:
```
Connected: Figma, Linear, Netlify, Vercel, Sentry, Supabase,
4 scientific, 3 Context7 variants.
→ 20,000 tokens of dead weight on every message.
→ Compaction occurs 30% sooner.
```

**Good**:
```
CORE profile: 5 servers for 80% of tasks.
Switch to SCIENCE or DEPLOY as needed.
→ ~5000 tokens of tool definitions, 75% savings.
```

**Our solution**:
- `mcp-profiles/core.json` — 5 servers (context7, basic-memory, sequential-thinking, playwright, ollama)
- `mcp-profiles/science.json` — core + ncbi, uniprot, pubmed
- `mcp-profiles/deploy.json` — core + vercel, netlify, supabase, sentry
- `mcp-profiles/switch-profile.ps1` — switching with a single command
- `settings.local.json` — 11 servers explicitly disabled

---

## 7. PII Leakage

**Problem**: sensitive data (IIN, API keys, card numbers) enters the LLM context
when working with financial documents.

**Bad**:
```
Claude reads a file with client IINs.
Calls Ollama for analysis — IIN goes to an external process.
Data ends up in logs, cache, context.
```

**Good**:
```
Redaction hook intercepts the MCP server call.
IIN replaced with [REDACTED:IIN] before sending.
Only masked data is in the external service's context.
```

**Our solution**:
- `scripts/redact.py` — PreToolUse hook with patterns for IIN, email, phones, API keys
- Exceptions: ClinVar VCV, dbSNP rs, genomic coordinates, git SHA (legitimate data untouched)
- `rules/security.md` — PII Policy, priority to local inference (Ollama)
- `hooks/settings.json` — deny-list of 17 patterns: blocking reads of .env, .ssh, .aws
- Matcher: `mcp__ollama|mcp__ncbi|mcp__uniprot|mcp__pubmed` — external servers only

---

## 8. Dead Skills

**Problem**: skills are created but not checked for relevance → outdated
instructions → Claude gives incorrect recommendations.

**Bad**:
```
Skill describes API v2, project is already on v3.
Claude generates code for non-existent endpoints.
Skill not updated for 4 months, nobody noticed.
```

**Good**:
```
Each skill has STATUS, CONFIDENCE, VALIDATED in frontmatter.
Weekly review: update VALIDATED for current skills.
Not used for 60+ days → status review.
```

**Our solution**:
- YAML frontmatter with lifecycle: `[STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-12]`
- Lifecycle: draft → confirmed → review → deprecated
- Rule: skill without update for 60+ days → status `review`
- CSO (Claude Search Optimization): description = triggers, NOT workflow summary

---

## 9. Interest-Driven Drift

**Problem**: a developer starts the session with a clear goal but switches to
a more interesting side task — optimizing tools instead of shipping the product,
analyzing competitors instead of writing code, polishing config instead of
pushing the feature that earns revenue.

**Bad**:
```
Goal: submit the research paper.
Actually did: optimized Claude Code config from 7/10 to 9.3/10,
analyzed 2 YouTube videos, created a GitHub repo, wrote OSS docs,
built an eval framework, fixed ctranslate2.
Result: 15 directions explored, 0 progress on the paper.
```

**Good**:
```
Goal: submit the research paper.
Scope Fence filled in activeContext.md before the session.
NOT NOW: config, competitors, tooling.
Session result: 3 emails sent, 1 positive response.
Side ideas saved to backlog.md — revisit after the paper is submitted.
```

**Our solution**:
- **Scope Fence** in `activeContext.md` — 4 fields: Goal, Boundary, Done when, NOT NOW
- `hooks/drift_guard.py` — fires on Skill/Agent calls, checks NOT NOW keywords
- `agents/scope-guard.md` — manual invocation to reject scope creep
- `agents/navigator.md` — session planner with Deferred list

**Root cause**: this is not a configuration problem — it is a habit problem.
No hook can fully prevent a human from chasing shiny objects. The Scope Fence
serves as a speed bump: it does not block the road but forces a moment of
conscious choice before veering off course.

---

## Mapping: Anti-Pattern → Defense Element

| # | Anti-Pattern | Configuration Element |
|---|-------------|----------------------|
| 1 | Context Overflow | memory-protocol.md, pre_compact.py, activeContext.md |
| 2 | Hallucination Loops | Evidence Policy, Stuck Detection, integrity.md |
| 3 | Vague Prompts | 80/20, brainstorming skill |
| 4 | Trusting Without Verification | Evidence Policy, reviewer agent, tdd-workflow skill |
| 5 | Monolithic CLAUDE.md | Modular architecture: 70 lines + rules + skills |
| 6 | MCP Overload | MCP profiles (core/science/deploy) |
| 7 | PII Leakage | redact.py, security.md, deny-list |
| 8 | Dead Skills | Skill Lifecycle (STATUS/CONFIDENCE/VALIDATED) |
| 9 | Interest-Driven Drift | Scope Fence, drift_guard.py, scope-guard agent |
