# Claude Code `/goal` for Wealth Protocol Skill

Use this in Claude Code after copying the skill into a repository.

```text
/goal wealth-protocol skill installed and validated:
  Required files exist:
  - .claude/skills/wealth-protocol/SKILL.md
  - .claude/skills/wealth-protocol/intake-template.md
  - .claude/skills/wealth-protocol/scoring-rubric.md
  - .claude/skills/wealth-protocol/validation-playbook.md
  - .claude/skills/wealth-protocol/golden-cases.md
  - .claude/skills/wealth-protocol/red-team-cases.md
  - .claude/skills/wealth-protocol/best-practices-audit.md
  - .claude/skills/wealth-protocol/hooks.md
  - .claude/skills/wealth-protocol/subagents.md
  - .claude/skills/wealth-protocol/prompt-delta.md
  - .claude/skills/wealth-protocol/scripts/validate_skill.sh

  Verification:
  Run `bash .claude/skills/wealth-protocol/scripts/validate_skill.sh`
  and show full output.

  Output must contain:
  `WEALTH_PROTOCOL_SKILL_VALIDATION: PASS`

  Constraints:
  - Do not delete existing files.
  - Do not edit global Claude settings.
  - Do not claim market validation was performed.
  - Do not create financial advice.
  - or stop after 20 turns.
```

Why this goal is good:
- one measurable end state;
- explicit verification command;
- exact output pattern;
- constraints;
- turn budget.
