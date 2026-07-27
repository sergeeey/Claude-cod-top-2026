# Prompt Delta

## v0.1.0 — Initial Reference Skill

Date: 2026-06-12

### Added

- `SKILL.md` with 6 modes:
  - excavate;
  - audit;
  - productize;
  - escape;
  - full;
  - validate.
- Validation-first operating workflow.
- Evidence tags: fact, inference, hypothesis, unknown, risk, metric, gate, action.
- No financial advice / no guaranteed income rule.
- Scoring rubric.
- Intake template.
- Golden cases.
- Red-team cases.
- Hooks design.
- Subagent design.
- Validation script.
- `/goal` completion condition.

### Design Decisions

1. Business outputs are treated as hypotheses.
2. The skill asks for missing data only when it blocks useful progress.
3. Productization requires a named method or artifact.
4. Retainers with mandatory live calls are classified as Time Rented.
5. Validation must include metric and kill criterion.

### Known Limits

- No real buyer validation has been performed.
- Golden cases are initial synthetic regression cases.
- Hooks are not installed automatically.
- Subagents are templates only.
- Scoring thresholds require calibration.

### Next Delta Candidates

- Add 50 real golden cases.
- Add promptfoo config.
- Add JSON output schema for machine parsing.
- Add active hooks after user approval.
- Add `.claude/agents/*.md` subagent files.
