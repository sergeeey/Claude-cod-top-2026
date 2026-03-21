# Security Rules

## Data protection
- PII (national IDs, card numbers, account numbers) → never in logs or output as plain text
- Secrets → env vars only, NEVER in code or commits
- SQL → ONLY parameterized queries, no string concatenation
- Input data → Pydantic validation BEFORE processing

## PII Policy
- When working with user data → prefer local inference (Ollama)
- PII must not leave the perimeter. If Ollama is unavailable → mask before sending to the cloud
- Redaction hook automatically scrubs PII before external MCP servers

## Before committing to production
- Run the `reviewer` agent for code review
- Check: no hardcoded secrets, SQL injection, XSS vectors
- For financial code: reviewer + manual security checklist are mandatory
