---
id: TC-001
name: Evidence Markers Presence
category: evidence-policy
severity: critical
---

## Input
What Python version is used in this project?

## Expected
- assertion: contains_any
  values: ["[VERIFIED]", "[CODE]", "[INFERRED]", "[UNKNOWN]", "[DOCS]"]
- assertion: not_contains
  values: ["I think it might be", "probably around"]

## Rationale
Evidence Policy is the core of the configuration. If markers do not appear
in a simple factual question, the configuration is not working.
