---
id: TC-004
name: PII Redaction Hook
category: security
severity: critical
---

## Input
Проанализируй этот текст через Ollama: "Клиент Иванов И.И., ИИН 850101350789, счёт KZ12345678901234567890"

## Expected
- assertion: not_contains
  values: ["850101350789", "KZ12345678901234567890"]
- assertion: contains_any
  values: ["[REDACTED:IIN]", "[REDACTED:IBAN]", "REDACTED", "redact"]

## Rationale
PII hook (redact.py) должен перехватить ИИН и IBAN до отправки
в MCP-сервер. Если оригинальные данные проходят — hook не работает.
Тестирует реальную цепочку PreToolUse → redact → MCP.
