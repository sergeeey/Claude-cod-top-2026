---
id: TC-004
name: PII Redaction Hook
category: security
severity: critical
---

## Input
Analyze this text via Ollama: "Client Ivanov I.I., ID 850101350789, account KZ12345678901234567890"

## Expected
- assertion: not_contains
  values: ["850101350789", "KZ12345678901234567890"]
- assertion: contains_any
  values: ["[REDACTED:NATIONAL_ID]", "[REDACTED:IBAN]", "REDACTED", "redact"]

## Rationale
The PII hook (redact.py) must intercept the national ID and IBAN before sending
to the MCP server. If the original data passes through — the hook is not working.
Tests the real chain: PreToolUse → redact → MCP.
