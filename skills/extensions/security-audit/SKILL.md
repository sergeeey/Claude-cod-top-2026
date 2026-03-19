---
name: security-audit
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-13]
  MUST CHECK before any commit touching auth, payments, PII, user data, SQL, .env.
  USE for financial applications, compliance, fraud detection.
  Triggers: security, audit, ARRFR, fraud, injection,
  XSS, PII, IIN, compliance, auth, payment, vulnerability, PCI.
  ESPECIALLY when tempted to skip security review for "internal" code.
---

# Security Audit Skill

## Domain
Financial organizations, Kazakhstan regulatory compliance, ARRFR compliance, fraud detection.

## Security Checklist (before production deploy)

### 1. PII Protection
- [ ] IIN — 12 digits, format YYMMDDGXXXXX — NEVER in logs as plain text
- [ ] BIN — 12 digits, legal entities — mask in output
- [ ] Bank account details — only last 4 digits in UI
- [ ] Email/phone — mask in logs (ivan@*****.kz, +7 7** *** **12)

### 2. Authentication & Authorization
- [ ] JWT tokens: refresh rotation, short-lived access (15 min)
- [ ] Rate limiting on auth endpoints (5 attempts / 15 min)
- [ ] IP whitelisting for admin endpoints
- [ ] 2FA for operations above threshold (configurable)

### 3. Data Layer
- [ ] SQL: ONLY parameterized queries (SQLAlchemy ORM or text() with bindparams)
- [ ] NoSQL: input data — Pydantic validation BEFORE writing
- [ ] Encryption at rest for PII fields (AES-256)
- [ ] Audit log for all CRUD operations involving PII

### 4. ARRFR Compliance (Kazakhstan)
- [ ] Data storage — only within KZ territory (or approved cloud regions)
- [ ] PII retention period — per Kazakhstan personal data law
- [ ] Processing consent — tracked in DB with timestamp
- [ ] Right to erasure — data erasure endpoint implemented

### 5. Fraud Detection Patterns
- **Velocity check:** > 3 applications from one IP per hour → flag
- **IIN deduplication:** one IIN = one client, cross-check across all products
- **Device fingerprint:** fingerprint collision + different IINs → high risk
- **Geo-anomaly:** application from region different from IIN registration → medium risk

## Criminal Code KZ (relevant articles)
- Art. 190 — Fraud
- Art. 210 — Illegal loan acquisition
- Art. 213 — Money laundering (AML)

## Tools
- `reviewer` agent — code review before commit
- `redact.py` hook — auto-cleanup of PII before external MCP
- `ruff` — static analysis of Python code
