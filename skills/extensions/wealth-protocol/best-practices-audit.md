# Best-Practices Audit

## Source Basis

This skill implements these principles:

1. Claude Code skills require a `SKILL.md` file with YAML frontmatter and markdown instructions.
2. The directory name becomes the command name.
3. Supporting files should keep `SKILL.md` focused and provide detailed templates/examples.
4. Reference-grade prompts should start with environment classification, then strategy selection, blueprint, quality gates, evaluation, versioning, and monitoring.
5. Complex business hypotheses must be decomposed into facts, assumptions, risks, unknowns, and falsifiable hypotheses.
6. A production-grade workflow needs golden cases, red-team cases, prompt delta, and evidence-based quality gates.
7. `/goal` verification should use measurable end states, explicit commands, constraints, and turn budget.

## Gap Analysis

| Area | Current Skill Design | Best Practice | Gap Closed |
|---|---|---|---|
| Skill activation | Directory `/wealth-protocol` + frontmatter | Clear command and description | Yes |
| Context management | Intake template + evidence tags | Environment before strategy | Yes |
| Hypothesis discipline | All outputs labeled as hypotheses until validation | Falsification-first | Yes |
| Safety | No guarantees, no investment advice | Financial safety gate | Yes |
| Evaluation | Golden cases + red-team cases | Regression testing | Partial, needs real runs |
| PromptOps | Prompt delta + validate script | Versioning and checks | Partial |
| Hooks | Design-only hooks file | Scoped safety automation | Not active by default |
| Subagents | Proposed subagents | Planner / executor / critic separation | Design only |
| Metrics | Scoring rubric | Measurable comparison | Yes |
| Anti-overbuilding | 7-day test before full build | Minimum viable validation | Yes |

## Known Limits

- The skill cannot perform real market validation by itself.
- Scores are qualitative until calibrated on real cases.
- Golden cases are synthetic and must be expanded with real user examples.
- Hooks are proposed, not installed.
- Subagents are design templates, not automatically created.

## Upgrade Path

| Stage | Target | Artifact |
|---|---|---|
| v0.1 | Usable local skill | current package |
| v0.2 | Run on 5 real users | eval notes + prompt delta |
| v0.3 | Add active hooks | repo settings with user approval |
| v0.4 | Add subagents | `.claude/agents/*.md` |
| v1.0 | Verified skill | 50 golden cases + 20 red-team pass log |
