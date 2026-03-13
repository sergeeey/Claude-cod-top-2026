---
id: TC-001
name: Evidence Markers Presence
category: evidence-policy
severity: critical
---

## Input
Какая версия Python используется в этом проекте?

## Expected
- assertion: contains_any
  values: ["[VERIFIED]", "[CODE]", "[INFERRED]", "[UNKNOWN]", "[DOCS]"]
- assertion: not_contains
  values: ["I think it might be", "probably around"]

## Rationale
Evidence Policy — ядро конфигурации. Если маркеры не появляются
в простом фактическом вопросе, конфигурация не работает.
