---
name: security-audit
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-13]
  MUST CHECK before any commit touching auth, payments, PII, user data, SQL, .env.
  USE for financial applications, compliance, fraud detection.
  Triggers: security, audit, fraud, injection,
  XSS, PII, compliance, auth, payment, vulnerability, PCI.
  ESPECIALLY when tempted to skip security review for "internal" code.
---

# Security Audit Skill

## Domain
Financial organizations, regulatory compliance, fraud detection.
Adapt the checklists below to your region's regulations and PII formats.

## Security Checklist (before production deploy)

### 1. PII Protection
- [ ] National ID — NEVER in logs as plain text
- [ ] Legal entity ID — mask in output
- [ ] Bank account details — only last 4 digits in UI
- [ ] Email/phone — mask in logs (ivan@*****.com, +X XXX *** **12)

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

### 4. Regulatory Compliance (adapt to your jurisdiction)
- [ ] Data storage — comply with data residency requirements
- [ ] PII retention period — per local personal data law
- [ ] Processing consent — tracked in DB with timestamp
- [ ] Right to erasure — data erasure endpoint implemented

### 5. Fraud Detection Patterns
- **Velocity check:** > 3 applications from one IP per hour → flag
- **ID deduplication:** one national ID = one client, cross-check across all products
- **Device fingerprint:** fingerprint collision + different IDs → high risk
- **Geo-anomaly:** application from unexpected region → medium risk

## Tools
- `reviewer` agent — code review before commit
- `redact.py` hook — auto-cleanup of PII before external MCP
- `ruff` — static analysis of Python code
