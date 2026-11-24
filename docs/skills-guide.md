# Skills Guide

## What are Skills

Skills are the Progressive Disclosure mechanism in Claude Code.
At startup only `name` + `description` are loaded (~150 tokens per installed skill on average, measured).
The full SKILL.md is read only when a trigger word fires.

`tokens:` in `skills/registry.yaml` is an approximate, informational estimate of
context-load size. It is not an execution budget, and nothing (router, hooks, loader)
reads it. Do not add `tokens:` to `SKILL.md` frontmatter.

## SKILL.md Format

```yaml
---
name: my-skill
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [REVIEWED: 2026-03-12]
  Skill description in 1-2 sentences.
  Triggers: keyword1, keyword2, keyword3.
---

# Skill Title

## When to Load
(activation conditions)

## Instructions
(specific actions; label each step's freedom: [Low] exact commands/regex where an
error is unacceptable, [Medium] heuristics/pseudocode, [High] principles for open-ended judgment)

## Anti-Patterns / Known Failure Modes
(what NOT to do; for each: how the model typically cuts the corner here, plus a
`WHY:` line with the incident or reason. A rule without its reason gets dropped
at the first edge case)
```

> **Status of the two conventions above (adopted 2026-09-19, untested).** Taken from a
> review of an external skill-synthesis prompt. One local A/B benchmark (1 source log,
> 4 diagnosis tasks) hit a ceiling: the base model solved every task with no skill at
> all, so the benchmark could not show that the labels or the section change outcomes.
> They are kept because they cost one line per step. Revisit if they do not survive real use.

## YAML Frontmatter

### Required Fields
- `name` — unique name (max 64 characters)
- `description` — description + triggers (max 1024 characters)

### Tool restriction: `allowed-tools`, not `tools`
Skills restrict tools with `allowed-tools`. `tools` is the field of subagent definitions
(`.claude/agents/*.md`), not of `SKILL.md` (Claude Code docs, via claude-code-guide;
34 of 186 local skills use `allowed-tools`). What the platform does with an unrecognized
field is not documented; do not rely on it being ignored.

### Lifecycle Markers (in description)
- `STATUS`: draft → confirmed → review → deprecated
- `CONFIDENCE`: low → medium → high
- `VALIDATED`: date of last verification

## CSO — Claude Search Optimization

**Critically important**: description must start with activation conditions ("Use when..."),
NOT with a workflow description.

Bad: "Step-by-step code review process with 2-stage verification..."
Good: "[STATUS: confirmed] Code review for financial applications. Triggers: audit, review, security."

**Why**: if description describes the workflow, Claude follows the description and skips SKILL.md.

## Lifecycle

1. **draft** — new skill, not tested
2. **confirmed** — tested, works stably
3. **review** — unused for 2+ months, requires verification
4. **deprecated** — outdated, scheduled for removal

Recommendation: check skills once a week, update VALIDATED for current ones.

## Directory Structure

```
skills/
├── core/                      ← installed by default (universal)
│   ├── routing-policy/
│   ├── brainstorming/
│   ├── tdd-workflow/
│   ├── git-worktrees/
│   ├── mentor-mode/
│   └── mcp-installer.md
│
├── extensions/                ← installed on demand (domain-specific)
│   ├── security-audit/        [finance]
│   ├── archcode-genomics/     [science]
│   ├── geoscan/               [science]
│   ├── notebooklm/            [productivity]
│   ├── suno-music/            [creative]
│   └── python-geodata.md      [science]
│
├── registry.yaml              ← central index of all skills
│
└── my-skill/                  ← standard skill layout
    ├── SKILL.md               # Main instructions (required)
    ├── references/            # Reference materials (optional)
    │   └── api_docs.md
    └── scripts/               # Utilities (optional)
        └── helper.py
```

## Core vs Extensions

**Core skills** are universal and installed automatically with standard/full profiles.
Any developer benefits from these regardless of domain.

**Extension skills** are domain-specific. During installation, users pick which
extensions to install. Extensions can also be managed after installation:

```bash
bash skill-manager.sh list              # show installed + available
bash skill-manager.sh search finance    # search by keyword
bash skill-manager.sh install notebooklm
bash skill-manager.sh remove suno-music
```

## Core Skills

### routing-policy
Task→skill→agent routing matrix. Determines optimal execution path.

### brainstorming
Socratic Design — 2-3 alternatives with trade-offs.
Hard gate: "design approved" before writing code.

### tdd-workflow
Test-Driven Development. RED→GREEN→REFACTOR cycle.

### git-worktrees
Isolated working copies for experiments and parallel work.

### mentor-mode
Extended pedagogical mode with analogies.

### mcp-installer
Step-by-step MCP server installation guide.

## Extension Skills

### security-audit `[finance]`
Security audit for financial applications. Regulatory compliance, fraud detection.

### archcode-genomics `[science]`
Chromatin extrusion simulation for variant pathogenicity analysis.
30318 ClinVar variants, 9 validated loci.

### geoscan `[science]`
Satellite gold prospecting. Sentinel-2 spectral indices, Isolation Forest.
AUC=YOUR_SCORE, Phase B complete.

### notebooklm `[productivity]`
Query Google NotebookLM notebooks. Browser automation, persistent auth.

### suno-music `[creative]`
Suno AI prompt engineering for EDM, hardstyle, hyperpop, rap-drill.

### python-geodata `[science]`
Python geospatial data processing patterns.

## How to Create a New Skill

1. Create directory: `skills/extensions/my-skill/` (or `skills/core/` if universal)
2. Create `SKILL.md` with YAML frontmatter
3. Set STATUS: draft, CONFIDENCE: low
4. Add entry to `skills/registry.yaml`
5. Test: verify that triggers fire
6. Update STATUS: confirmed after successful testing

## Finding a skill you did not know to ask for (`scripts/skill_search.py`)

The native listing always shows a skill's name, but a description only for the few skills that
fit its budget (about 45 of 250 on one measured install), and never a skill's body. A skill the
user never typed and whose name says nothing is therefore invisible. `scripts/skill_search.py` is
the second path: a plain lexical search (BM25) over name, description, `when_to_use`, trigger
phrases, headings and body of the skills that are really available. It is not a router and not an
index service: no daemon, no cache, no vectors, no network, nothing is written.

What it does and does not do:

- **Fresh by construction.** The index is rebuilt from the files on every call, so adding,
  editing, renaming or removing a skill is visible at once (about 0.4 s for 200 skills).
- **Only skills the model can invoke.** Backups (`*.bak*`, `*backup*`), `skills-disabled/`,
  folders starting with `_` or `.`, `disable-model-invocation: true`, and `skillOverrides` set to
  `off` or `user-invocable-only` are left out; unreadable files are skipped and counted.
- **Claude Code scopes.** Personal `<home>/skills` and project `<project>/.claude/skills` (the
  project directory and its parents up to the git root); a personal skill wins a name clash.
- **"Nothing fits" is a normal answer.** A candidate is shown only when its head fields (name,
  description, `when_to_use`, triggers, headings) cover enough of the query's rarest terms;
  otherwise the output says to do the task directly. A match found only in the body never counts.
- **Lexical, so phrase the task as an intent.** It finds a skill when the query shares terms (or
  stems) with it. A pasted conversation does not work and is condensed to its six rarest known
  terms; a short statement of what is needed does.

Integration point (proposed, not installed by this repository): the native listing stays the
fast path, and one line in the user's `CLAUDE.md` makes the search reachable even when no skill
description mentions it: *"If no listed skill fits a non-trivial task, run
`python <path>/skill_search.py "<the task in one short sentence>"` before deciding; an empty
result means do the task directly."* Query text passes through the same Bash command filters as
any other command.

### Does the running model help by writing the query? (measured, 2026-11-24)

The hypothesis was that the limit sits in turning the user's wording into a query. The model
already running writes a 2-4 word intent query for free (no extra model call). Offline test on
real human messages, frozen instruction, test split never used for tuning, labels weak (the
skill the model really activated in that session; many were activated by a rule in `CLAUDE.md`,
not by the message):

| split | variant | hit@5 | a skill recommended | controls with a recommendation |
|---|---|---|---|---|
| dev (22 relevant, 13 controls) | raw message | 0.14 | 0.14 | 0.00 |
| dev | model-written query | 0.09 | 0.36 | 0.08 |
| test (25 relevant, 20 controls) | raw message | 0.12 | 0.04 | 0.05 |
| test | model-written query | 0.08 | 0.40 | 0.20 |

Reading: a short query makes the script say "recommended" far more often, but not more often
correctly (hit@5 did not improve, false recommendations on messages that needed no skill went
up). With n=25 the intervals are wide, so this is "no benefit shown", not "proved harmful".
Writing the query is therefore not adopted by default.

To check any integration in ordinary work, count in your own session transcripts (aggregates only):
`[skill-search]` result lines, how many say "no confident match", and how often a `Skill` call
for a listed candidate follows within the next few turns. An integration is worth keeping only
if candidates are followed by a Skill call clearly more often than chance and the "no confident
match" share stays high on simple tasks. To switch off, delete the line from `CLAUDE.md`.


### Opt-in integration and Bash filters (checked 2026-11-24)

`scripts/skill_search_toggle.py` adds or removes one marked block in a `CLAUDE.md` you name (no
default target; preview unless `--apply`; a `.bak-skill-search` copy is written first; `--remove`
restores the file byte for byte). The block tells the model: the native list is the fast path;
search only for a non-trivial task needing a specialised capability when no listed skill fits;
never for chat, simple edits, continuations or when the user named a skill; at most once per task;
query = 2-4 content words from the current goal.

Bash filters (the installed `permission_policy`, `pre_commit_guard`, `checkpoint_guard`,
`agent_tool_scope_guard` and `pre_push_privacy_guard`, fed the exact command with ten different
queries): the call passes unchanged for ordinary queries, including words like "git commit",
"force push", "rebase", "release", "migration" and "secrets". It is denied only when the query
text contains a destructive shell phrase (a table-dropping statement or a recursive delete),
because the filters match command text, not intent. The block therefore tells the model to
paraphrase such a query; no hook was changed.
