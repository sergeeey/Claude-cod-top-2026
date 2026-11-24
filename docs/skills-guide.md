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


## Candidate hook prototype (`hooks/skill_candidates.py`, dormant) — 2026-11-24

Why it exists: asking the model to search did not happen (0 of 11 fresh sessions), so the decision
to look is moved to a `UserPromptSubmit` hook. The hook runs the local BM25 search on the user's
message and, only on a confident match, adds at most two advisory candidates. The model may use one,
combine them, ignore them or work without a skill. Registered as `class: dormant`: defined and
tested, wired nowhere. It is separate from `routing_floor_classifier` (safety tiers) and from
`keyword_router` (disabled live; it prints a `message` field, while `routing_floor_classifier`
uses the `additionalContext` channel that is known to reach the model; whether `message` does is
not verified here).

Behaviour: slash commands, short or continuation messages (fewer than five distinct content words)
and non-matches stay silent; each skill is offered once per session, so a later sub-task can still
surface a new skill; project scope and `skillOverrides` come from the search itself; a missing
script, bad input or any error gives no output and exit 0. Kill switch `SKILL_CANDIDATES=0`.
Experiment mode is off unless `SKILL_CANDIDATES_HOLDOUT=<p>` is set: that share of messages gets no
candidates (decided by a hash of session and message) and, if `SKILL_CANDIDATES_LOG=<path>` is set,
one counts-only JSON line per decision is appended (no message text).

To try it on one machine, add this entry under `UserPromptSubmit` in the settings file you choose
(the repository does not do it for you) and remove it to undo:
`{"hooks": [{"type": "command", "command": "python <home>/.claude/hooks/skill_candidates.py", "timeout": 5}]}`.
The hook needs `scripts/skill_search.py` next to `hooks/` (the same layout in the repository and
in `~/.claude`).

### What the other implementations taught (read from source, nothing run or installed)

| Project | Trigger | Index and query | Abstention | Repeats | Reused or rejected |
|---|---|---|---|---|---|
| skillseek | per-prompt hook plus model-called search tool | BM25-like over name/description, raw prompt | score floor and top-k in the hook; tool has none | per-session seen-set file | reused: per-prompt injection and seen-set; rejected: floors "calibrated for 1700 skills" with no data behind them, unpruned state files |
| skills-radar | model-called tools only | embeddings plus BM25, optional LLM query rewrite | none | none | rejected: model-initiated, no abstention, heavy stack (the same weakness we measured) |
| claude-skills-supercharged | per-prompt hook | LLM intent analysis against hand-written rules | two thresholds, caps per tier | state file, but suggested skills are never recorded, so they repeat | reused: two-tier idea only; rejected: a paid model call per prompt |
| agent-skills / skill-retrieval | per-turn hook (other runtime) | stdlib BM25 with precomputed weights | none (score above 0) | none | confirms stdlib BM25 is enough; rejected: no abstention, repeated injection |
| dsh-skillport | model-called tool | weighted field scoring | none | not needed | rejected: depends on the model noticing a need |

None of the quoted speed, accuracy or token-saving figures is backed by a benchmark in those
repositories. Our own design differs in the three places that matter: abstention with floors checked
against controls, once-per-session offers, and an experiment switch.

### Label quality (50 real messages, two independent annotators, blind to the model's choice)

| Check | Result |
|---|---|
| Model's own activation is among the independent annotators' skills | 6 of 40 (annotator A), 3 of 40 (B) |
| Annotators say a skill materially helps, among messages where the model activated one | 57% (A), 42% (B) |
| Annotators say a skill helps in sessions where the model used none | 0 of 10 (both) |
| Annotators agree on need or no need | 42 of 50; the same skill when both name one: 15 of 16 |

So the earlier 11% hit@5 was measured against labels that mostly are not what independent
annotators call the right skill (many were set by a `CLAUDE.md` rule, not by the message). Against
the annotators' labels (23 and 17 messages) lexical search puts a right skill in the top 5 for 29-35%
and in the top 10 for 41-48%. With the current floors it recommends on 12-13% of those and is wrong
on 1 of 27 and 2 of 33 messages that need no skill; 0 of 55 real messages from sessions with no skill
got a recommendation. Lowering the coverage floor raises recommendations but not correct ones (right
skill shown stays 12-13%), so the limit is retrieval vocabulary, not abstention. Limitations: both
annotators are models (a human sheet is the missing check), n is small, and the sample is enriched for
messages where the model activated a skill, so these numbers are not a rate over all messages.

### Free offline variants tested

| Variant | Result |
|---|---|
| Split a long message into sentences and merge searches | worse: hit@5 0.35 to 0.26 (A), 0.29 to 0.24 (B); more wrong recommendations |
| Include trigger phrases in the index | no change on this sample |
| Search the host name of a link instead of its path and ids (kept) | top-10 hit 0.43 to 0.48 (A), 0.35 to 0.41 (B); recommendations unchanged |
| Model-written short query | not better than the raw message (see above) |

Messages that were missed fall into two kinds: a bare link whose kind decides the skill (video,
repository), and a conversational request that depends on earlier context ("write the report on our
work"). The first is now partly covered. The second is not solved by lexical search.

### Native listing budget (this installation)

193 searchable user skills: descriptions plus `when_to_use` total 123,675 characters, median 503,
90th percentile 1,123, six longer than the 1,536 per-entry cap, against a list budget of roughly
30,000 characters. Names alone take about 3,500, leaving about 26,400, so every skill would fit only
at about 137 characters each; the shortest 85 skills fit as they are. Shortening to that size is a
rewrite of the library and is not proposed; the hook offers the same benefit for the few skills a
message points at, without touching the texts.

### The one experiment that decides whether to enable it

Question: does showing candidates change the outcome of real tasks? Design: take the messages where
both annotators name the same skill, extended to at least 40 by independent human labelling; replay
each task in a fresh isolated session twice, with the hook on and with `SKILL_CANDIDATES_HOLDOUT=1.0`
(same hook, candidates withheld); grade the final results blind with a rubric fixed in advance and
tests where the task has them. Primary outcome: rubric score difference with its MCID written before
the run; secondary: skill invoked, manual corrections, tokens, time, unneeded procedures. Cost: about
80 headless sessions, so it is not run here and needs your decision. A negative or null result (at
the stated MDE) keeps the hook dormant and the native listing as is. Do not read activation counts as
success.

### Observability of the chain, from existing records

| Link | Where it is visible |
|---|---|
| need | independent annotation (sample above) |
| search launched, candidates relevant | counts-only log in experiment mode; otherwise offline replay |
| exposure | the `[skill-candidates]` block is stored in the session transcript; grep for it |
| chosen and activated | the transcript's `Skill` tool calls, already read by `scripts/skill_usage_report.py` |
| quality and final result | the blind rubric in the experiment above; not available from logs |

An ignored recommendation is not counted as wrong, and an activation is not counted as useful.
