# Hooks Design

These hooks are design proposals only. They are not installed by this package.

Claude Code supports hooks in skill or agent frontmatter, scoped to the active component lifecycle. Do not enable hooks without reviewing the repository's current settings and user approval.

## Hook 1 — Pre-output Safety Gate

Purpose:
Block or flag outputs that contain:
- guaranteed income;
- unsupported market claims;
- unlabeled revenue projections;
- recommendations without validation;
- financial advice.

Pseudo-check:

```bash
grep -Eiq "guarantee|guaranteed income|risk-free|certain profit|will make \$" "$OUTPUT_FILE" && exit 2
```

Fail action:
- rewrite output with `<hypothesis>`, `<unknown>`, validation plan, and not financial advice disclaimer.

## Hook 2 — Validation Completeness Stop Hook

Purpose:
Before final response, ensure the output contains:
- `hypothesis`;
- `success_metric` or `metric`;
- `kill_criterion` or `kill criterion`;
- `not financial advice` when money is discussed.

Pseudo-policy:

```text
If output contains business model, product, revenue, projection, niche, or market:
  require:
    - evidence label
    - validation test
    - metric
    - kill criterion
    - no guarantee
```

## Hook 3 — UserPromptSubmit Router

Purpose:
If user asks about niche, monetization, leverage, productized expertise, or escaping hourly work, suggest:

```text
/wealth-protocol full
```

Do not auto-run without user intent.

## Hook 4 — Anti-Fabrication

Purpose:
Reject outputs that invent:
- market size;
- conversion rates;
- audience size;
- buyer demand;
- revenue forecasts.

Allowed:
- scenario math explicitly labeled as hypothetical.

## Recommended Installation Policy

Do not install hooks until:
1. the skill passes 8 golden cases;
2. the skill passes 12 red-team cases;
3. user approves writing to Claude settings;
4. rollback path is documented.
