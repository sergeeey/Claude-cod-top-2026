# Output Templates

These templates mirror the output contracts in `SKILL.md`.

## Evidence Labels

Use:

```text
<fact>...</fact>
<inference>...</inference>
<hypothesis>...</hypothesis>
<unknown>...</unknown>
<risk>...</risk>
<metric>...</metric>
<gate>...</gate>
<action>...</action>
```

## Full Diagnostic Template

```markdown
## Wealth Protocol Full Diagnostic

### Executive Summary

### Environment Passport

### Asset Map
| Asset | Evidence | Leverage Type | Reusability | Buyer Relevance |
|---|---|---|---:|---|

### Specific Knowledge Thesis

### Leverage Audit
| Activity | Type | Hours/week | Revenue % | Score | Leak? |
|---|---|---:|---:|---:|---|

### Productized Asset Options
| Option | Buyer | Asset | Leverage | Feasibility | Validation Signal | Score |
|---|---|---|---:|---:|---:|---:|

### Time-for-Money Conversions
| Current Activity | Equity Asset | Effort | Leverage | Buyer | Test |
|---|---|---|---:|---|---|

### Risk Register
| Risk | Cause | Detection | Mitigation | Severity |
|---|---|---|---|---|

### Validation Plan

### 14-Day Sprint
| Day | Action | Output | Metric |
|---:|---|---|---|

### Decision
Status:
Next best step:
```

## Needs More Data Template

```markdown
## needs_more_data

I cannot produce a reliable Wealth Protocol diagnosis yet.

### Missing minimum inputs
1.
2.
3.

### What I can infer safely
...

### What I will not infer
...

### Fill this next
Use `intake-template.md`, sections:
- ...
```
