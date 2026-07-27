---
name: refine-project
description: >
  Цепочка: /orient → /atomize → /execution-enforcer → result. Запускаешь раз — получаешь готовый
  артефакт (commit / test / file), не отчёт. Целевой workflow для apex-style project refinement:
  понять → разобрать на атомы → найти bottleneck → executive change. Запрещает остановиться на
  markdown отчётах. Runs all 3 stages sequentially, passes contracts between them, enforces
  external artifact as exit condition. [STATUS: confirmed] [CONFIDENCE: high] [REVIEWED: 2026-07-23]
triggers:
  - /refine-project
  - /refine
  - "улучши проект"
  - "доведи до результата"
  - "end-to-end refinement"
  - project refinement chain
  - "не отчёт а артефакт"
not_for:
  - single-step audit only → use /atomize alone
  - project briefing only → use /orient
  - exploration without commitment to a change
---

# refine-project — Chain Orchestrator Skill

## Purpose

Three-stage pipeline that converts a messy project state into one verified external artifact.
Does NOT stop at reports. Does NOT produce 30-step roadmaps. Produces one commit, one test file,
or one fixed file — then exits.

```
/orient  →  /atomize --scan  →  /execution-enforcer
  |               |                      |
  5-line        7 atoms +          builder runs /goal
  briefing      1 /goal            artifact verified
```

---

## HARD RULES

- MUST complete all 3 stages or explicitly fail with stage name and reason
- MUST produce at least 1 external artifact at the end: commit SHA, test file path, or edited file path
- If any stage fails — report which stage failed, do not silently skip to next
- "Artifact" means verifiable by a shell command (git log, pytest, ls) — not a markdown section
- Token budget: ~25–40 turns total across all stages
- Do NOT write an audit report and call it done
- Do NOT stop at Stage 2 bottleneck list — that is input to Stage 3, not the output

---

## Stage Contracts

Each stage has a defined input and output. Passing the contract forward is mandatory.

### Stage 1 Contract — Orient

**Input:** current working directory, any args passed to /refine-project  
**Actions:**
- Read CLAUDE.md (project root)
- Read `.claude/memory/activeContext.md` if exists
- Run `git log --oneline -10`
- Run `git status --short`

**Output (5-line briefing):**
```
Project: <name>
Branch: <branch> | Last commit: <sha> <message>
Focus: <current focus from activeContext or "unknown">
Open issues: <count> uncommitted changes / <count> failing tests if detectable
Next: Stage 2
```

**Gate:** If no CLAUDE.md and no git repo detected → ABORT. Report:
```
[ABORT] Stage 1: No project detected at <path>. Pass an explicit path or cd into project first.
```

---

### Stage 2 Contract — Atomize

**Input:** Stage 1 briefing (project name, current focus, branch)  
**Actions (15-min scan mode):**
- Identify 7 work atoms: small, independently completable units of improvement
- Each atom: one sentence, one owner (code/test/doc/config), estimated effort ≤30 min
- Score each atom: importance (1–5) × feasibility (1–5) = priority score
- Select top 3 bottlenecks (highest-priority atoms blocking progress)
- From the top bottleneck, draft one /goal command

**Output:**
```
Atoms (7):
1. [score] <atom description> — <file or area> — <effort>
2. ...
...

Bottlenecks (top 3):
B1: <atom#> — <why it blocks>
B2: <atom#> — <why it blocks>
B3: <atom#> — <why it blocks>

/goal for Stage 3:
/goal <END STATE verifiable by command>. Run <COMMAND> and show full output.
Output must contain: <EXPECTED STRING>. Do NOT <CONSTRAINT>. or stop after 15 turns.
```

**Gate:** If no clear bottleneck is identifiable (all scores equal or project is empty):
- Use the atom with the highest importance score as fallback
- Annotate: `[FALLBACK: no clear bottleneck — using top-importance atom]`

---

### Stage 3 Contract — Enforce

**Input:** /goal from Stage 2  
**Actions:**
- Execute the /goal via builder agent or inline execution
- On success: capture artifact (commit SHA / test file path / file path)
- Run verify command and show full output

**Output:**
```
Enforce result:
  Status: SUCCESS | FAILED
  Artifact: <commit_sha | /path/to/test_file | /path/to/file>
  Verify: <command that proves artifact exists>
  Output: <first 20 lines of verify command output>
```

**Gate — artifact verification:**
- commit: `git log --oneline -1` must show new SHA different from Stage 1
- test file: `pytest <file> -q` must exit 0
- file: `ls -la <path>` must show file, `git diff --stat` must show change

**Gate — FAILED output (do NOT suppress):**
```
[FAILED] Stage 3: <reason>
Attempted /goal: <goal text>
Failure point: <what step broke>
Partial work: <what was completed>
Next manual step: <one action user can take>
```

---

## Full Output Format

```markdown
## Refine Project — Result

### Stage 1: Orient
Project: <name>
Branch: <branch> | Last commit: <sha> <message>
Focus: <current focus>
Open issues: <summary>
Next: Stage 2

### Stage 2: Atomize
Atoms (7):
1. [score] <description> — <area> — <effort>
2. [score] <description> — <area> — <effort>
3. [score] <description> — <area> — <effort>
4. [score] <description> — <area> — <effort>
5. [score] <description> — <area> — <effort>
6. [score] <description> — <area> — <effort>
7. [score] <description> — <area> — <effort>

Bottlenecks:
B1: <atom> — <why blocks>
B2: <atom> — <why blocks>
B3: <atom> — <why blocks>

/goal used: <goal text>

### Stage 3: Enforce
Status: SUCCESS | FAILED
Artifact: <sha / path>
Verify: <command>
Output:
<first 20 lines>
```

---

## What NOT to produce

- Long markdown audit reports with numbered findings
- 30-step roadmaps or phased plans
- "Recommendations" sections without an executed action
- "This is mostly done" when artifact is missing
- Gold standard fantasies ("ideally the codebase would...")
- Stage 2 as final output — atoms are inputs, not results

---

## Usage Examples

```bash
# Basic — run on current directory
/refine-project

# With explicit focus override
/refine-project focus:test-coverage

# Dry-run Stage 1+2 only (no enforcement)
/refine-project --plan-only
```

`--plan-only` flag: skip Stage 3, output Stage 1+2 only. Use when user explicitly wants
to review the /goal before execution. Must be explicitly requested — default is full chain.

---

## Companion Skills (chain order)

| Stage | Skill | Mode |
|-------|-------|------|
| 1 | /orient | auto-read CLAUDE.md + git |
| 2 | /atomize | --scan (15-min version) |
| 3 | /execution-enforcer | /goal executor |

Each companion skill can be invoked standalone. /refine-project chains them
with contracts so output of each is structured input to the next.

---

## Failure Modes and Recovery

| Failure | Stage | Recovery |
|---------|-------|----------|
| No CLAUDE.md / no git repo | 1 | Abort, ask for path |
| All atoms trivial / score tied | 2 | Fallback to top-importance atom |
| /goal too vague to execute | 3 | Narrow scope, retry with smaller /goal |
| Builder hits permission prompt | 3 | Report blocker, show manual command |
| Tests fail after change | 3 | Report FAILED with diff, do not hide |
| Token budget exceeded | any | Save Stage N output, report cutoff stage |

---

## Acceptance Gate (must pass before declaring success)

Chain is considered SUCCESSFUL only if ALL the following are true:

- [ ] /atomize completed and produced exactly one /goal (not zero, not multiple)
- [ ] /execution-enforcer was invoked (not skipped)
- [ ] At least one external artifact exists: git commit SHA, new test file, non-markdown file, patch, or executed command with captured output
- [ ] Verify command from /goal was actually run (transcript shows execution)
- [ ] The artifact targets the #1 bottleneck identified in Stage 2 (not random change)
- [ ] No HARD RULES were violated (9 atoms max, 3 bottlenecks max, no fantasy 30-day gold plan)

### Anti-loopholes (close known bypass patterns)

These exploits were found by Ultracode P2 audit 2026-05-30:

**EXPLOIT 1 — Trivial markdown commit:** `git commit -m "..." notes.md` passes checkbox 3 (commit exists) AND bypasses "markdown ≠ artifact" rule (commit hash itself is non-markdown).
Fix: Commit must touch ≥1 non-markdown file in non-docs path. Verify via `git diff --name-only HEAD~1 HEAD | grep -v ".md$" | grep -v "^docs/"` returns ≥1 line.

**EXPLOIT 2 — Trivial executed command:** "Executed command with captured output" can be satisfied by `ls`, `echo`, `git status` saved to file.
Fix: Command output artifact must show state mutation: pytest with non-trivial assertions (≥1 line of test code with `assert` containing variable reference), OR file write that creates source code (≥10 lines of `.py/.ts/.sh/.yaml`), OR external API call with response saved.
Allowed verify commands list:
- `pytest tests/<file> -v` showing PASS with assertions
- `python -c "<actual code>"` showing computed result
- `curl <url>` saved with non-trivial response body
NOT allowed as sole artifact: `ls`, `pwd`, `echo`, `git status`, `cat README.md`.

**EXPLOIT 3 — Regression ignored:** Gate can report SUCCESS while test suite went red.
Fix: Add MANDATORY checkbox to Acceptance Gate:
- [ ] Test suite still green after artifact (run pytest/npm test; record exit code 0)
If tests were green before and red after → CHAIN FAILED regardless of other artifacts. Show diff of failing tests.

**Updated CHAIN FAILED template adds:**
- exploit_detected: <EXPLOIT 1/2/3 if applicable>
- tests_state: <green→green | green→red | red→red>

### Hard-fail condition

If artifact is missing OR markdown-only output OR verify command not run → output explicit failure:

```markdown
## CHAIN FAILED — audit theatre detected
Reason: <which gate failed>
What was produced: <list of markdown files only>
What was NOT produced: <commit/test/file>
Next action options:
1. Retry with smaller scope (one atom, not full project)
2. Hand off to builder agent with explicit /goal
3. Split #1 bottleneck into 2-3 smaller atoms
```

**NEVER report SUCCESS if only markdown reports exist. NEVER use "mostly done".**

---

## BSV

STATUS: confirmed | CONFIDENCE: high | VALIDATED: 2026-05-30
tokens: ~500 | effort: medium | language: Russian/English
