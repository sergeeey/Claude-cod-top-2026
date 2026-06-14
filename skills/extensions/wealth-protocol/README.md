# Wealth Protocol Claude Code Skill

A validation-first Claude Code skill for diagnosing:

- specific knowledge;
- leverage stack;
- productized expertise;
- time-for-money leaks;
- testable market hypotheses.

## Install

Copy this folder into your repository:

```bash
mkdir -p .claude/skills
cp -R wealth-protocol-skill/.claude/skills/wealth-protocol .claude/skills/
```

The skill command is based on the directory name:

```bash
/wealth-protocol full
/wealth-protocol excavate
/wealth-protocol audit
/wealth-protocol productize
/wealth-protocol escape
/wealth-protocol validate
```

## Recommended Start

1. Fill `intake-template.md`.
2. Paste the filled intake into Claude Code.
3. Run:

```text
/wealth-protocol full
```

## Validation

Run:

```bash
bash .claude/skills/wealth-protocol/scripts/validate_skill.sh
```

Expected result:

```text
WEALTH_PROTOCOL_SKILL_VALIDATION: PASS
```

## Design Principle

This is not a wealth-promise generator. It is a falsification-first diagnostic system.

Every niche, product, market, business model, and projection is a hypothesis until validated externally.
