# Configuration Architecture

## 6 Loading Layers

### Layer 1: CLAUDE.md (Red Zone)
**Cost**: paid on EVERY message; the shipped `claude-md/CLAUDE.md` template is ~2.1k tokens (125 lines, 8.5 KB; estimated as bytes/4).
**Rule**: keep it short (the shipped template is 125 lines). Everything not always needed goes into rules or skills.

Contains:
- Identity (who you are, language, style)
- Workflow (80/20, Plan-First, Stuck Detection)
- Self-Review (4-point checklist for plans and 1-2 file changes)
- Integrity (confirmation required for irreversible operations)
- Agents (13 active: 5 core + 8 extended, plus 3 teams)
- Evidence Policy (short version)
- Pointers to the modular rules

### Layer 2: Rules (Yellow Zone)
**Cost**: always-on unless a rule is `paths:`-scoped (five are: `coding-style`, `testing`, `falsification-ladder`, `research-methodology`, `meta-loop`); ~28.5k tokens always-on if all 21 are installed (`minimal` profile: 2 rules ≈ 2k), estimated as bytes/4.

| File | Lines (historical) | Relevant when (only `paths:`-scoped rules actually load on demand) |
|------|-------|--------------|
| coding-style.md | 20 | Writing/editing code |
| security.md | 17 | Working with data, API, deployment |
| testing.md | 12 | Tests, pytest, coverage |
| integrity.md | 68 | Factual claims, recommendations |
| memory-protocol.md | 45 | Git commit, end of session, checkpoint |
| context-loading.md | 74 | Agent invocation (shared state protocol) |
| permissions.md | 34 | Permission decisions (auto-allow/deny/ask) |
| mentor-protocol.md | 27 | Educational content (organic mode v2) |

### Layer 3: Skills (Green Zone)
**Cost**: ~150 tokens per installed skill (name + description only; measured average of 621 characters over the 99 of 135 shipped SKILL.md files whose frontmatter parses as YAML, estimated as chars/4 — the loader may truncate long descriptions). SKILL.md is loaded on trigger.

Each skill has YAML frontmatter with lifecycle:
- `STATUS`: draft → confirmed → review → deprecated
- `CONFIDENCE`: low → medium → high
- `VALIDATED`: date of last verification

### Layer 4: Agents (Green Zone)
**Cost**: agent names and descriptions are listed in the Agent tool's description on every message; an agent's full definition is read only when it is called.

13 agents (+ 3 teams) cover: architecture, code, review, tests, search, security, learning, verification.

### Layer 5: Hooks (Free Zone)
**Cost**: 0 tokens. Executed as OS processes, consume no context.

103 hooks across 25 event types = deterministic automation: every registered hook fires
100% of the time (unlike instructions in CLAUDE.md, which the model can choose to ignore).
**Firing is not the same as blocking** — only the hooks classed PREVENT (and only on their
`PreToolUse` leg) can actually deny a tool call; most fire, observe or warn, and never stop
anything. The counts are in the generated `docs/hook-control-matrix.md`, which also has the full
PREVENT/WARN/OBSERVE/Dormant/Library breakdown.

### Layer 6: MCP Profiles (Management)
Each MCP server adds ~1000-2000 tokens of tool definitions.
Profiles allow connecting only the servers needed.

## Progressive Disclosure Principle

```
Message 1: CLAUDE.md loaded (~2.1k tokens)
Message 2: User writes code → rules/coding-style.md (~330 tokens)
Message 3: Mentions tests → rules/testing.md (~870 tokens)
Message 4: Trigger "audit" → skills/security-audit/SKILL.md (~920 tokens)
```

Without Progressive Disclosure every shipped rule and skill would load immediately — skill metadata alone is ~15k tokens (measured over 99 of 135 skills; ~21k extrapolated to all 135), plus the rule bodies. Five rules are `paths:`-scoped (`coding-style`, `testing`, and since 2026-09-25 `falsification-ladder`, `research-methodology`, `meta-loop`); the other 16 are always-on, so rule loading is not zero-cost.

## Red Zone vs Green Zone

| Zone | What | Cost | Rule |
|------|------|------|------|
| Red | CLAUDE.md | ~2.1k tok/msg | Minimum lines, maximum impact |
| Yellow | Rules | always-on unless `paths:`-scoped (5 of 21); ~28.5k tok always-on if all installed | See `claude-md/CLAUDE.md` § RULES |
| Green | Skills, Agents | skill metadata always (~150 tok each); skill body on trigger (~2.5k avg) | On trigger/call |
| Free | Hooks, Scripts | 0 tok | Always execute, cost no tokens |

## Development strategy and measurement principles (owner decision, 2026-11-25)

This section keeps the evolution plan next to the architecture it governs; it adds no component. The
measured starting point is `docs/baselines/2026-11-25-measurement-baseline.md`, the comparison set is
`tests/eval/e2e-regression-set.md`, the ownership model is in `docs/GLOBAL_VS_PROJECT_OVERLAY.md` and the
contribution rule is `PRODUCT_CONSTITUTION.md` § 11.

### Order of modernization

1. Skills and context engineering. Discovery of competences and the management of context are one
   problem: measure the loaded volume of each component (skill listing, search hints, CLAUDE.md and
   rules, memory, MCP and tool descriptions, project context, loaded skill instructions) and keep
   loaded volume separate from proven influence on results.
2. Verification as the measuring foundation: reuse existing tests, gates, schemas and evals; a small
   representative set of real tasks with objectively checkable outcomes.
3. Hooks and rules.
4. A consistent choice among skills, agents, MCP servers and tools. Native Claude Code mechanisms are
   examined first; no separate search engine or router per resource type; only improvements with
   confirmed applicability are extended to other types. A common selection policy does not require one
   program component.
5. Memory and self-healing.
6. Self-optimization.
Stages are not started all at once. The current priority is the skill library, context measurement and
objective acceptance criteria. Before each stage: a short sufficiency check of the existing solution,
a quality criterion, a measurement of the current state, the significant constraints; intervene only
when the need is justified.

### Result states and what counts as evidence

Outcomes are recorded as confirmed, partly confirmed, defect found, insufficient evidence, or needs
independent or human check. A model checking its own work is not independent evidence; preferred
checks are external tests, reproducible computations, real artifacts and objective criteria. Ordinary
tasks get an independent check on roughly 5-10% of runs where a suitable method exists; for critical
tasks the depth follows the consequence of an error, not a random sample. Model agreement is not human
verification.

### Metrics that must not become goals

Skill activation counts, Hit@k, the number of passed checks and fewer hook blocks are intermediate
signals. A change is judged by end quality, reliability, autonomy, cost and the guards in the
regression set, and an intermediate gain bought with a worse result is a regression. Immutable
criteria and held-out tasks are kept; held-out ground truth stays outside the repository.

### Controlled change

observation, hypothesis, isolated check, independent assessment, decision, integration, repeated
observation. A change fixes first: the library and corpus version, the algorithm and parameters, the
sample and the held-out part, success criteria, limits, the resource budget and the stopping rule; no
more than three competing hypotheses per cycle, always including "the existing mechanism is
sufficient or the shortfall is a measurement artifact"; one main distinguishing experiment per cycle.
While a trial is running (currently `skill_candidates`, until 2026-12-02) the observed configuration,
corpus and parameters are not changed; any unavoidable change is recorded with time, nature and
version and the periods are not pooled. Changes to the working configuration need the owner's consent;
irreversible, high-risk and paid actions stay outside autonomy without explicit permission.

### Memory quality

Knowledge entries distinguish confirmed knowledge, working hypotheses, unconfirmed observations, and
refuted or outdated conclusions, using the metadata the vault already requires (`source`, `checked`,
`evidence`, `evidence_scope`, `status`). A significant entry also records the conditions of
applicability and a criterion for review. Unconfirmed conclusions are not fixed in mandatory rules or
automatic policies, and refuted solutions are marked so they are not reused.

### Cross-cutting requirements

Security and trust in external components, protection against malicious instructions, token, time and
compute budgets, number of user interventions, observability, configuration versioning,
reproducibility and reversibility. Use the existing mechanisms (git, tests, logs, snapshots) for all of
them; a new measuring infrastructure is not created for its own sake.
