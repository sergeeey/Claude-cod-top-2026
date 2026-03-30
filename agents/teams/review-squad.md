---
name: review-squad
description: Parallel code review — quality + security simultaneously. 2x faster than sequential review.
lead: reviewer
teammates:
  - sec-auditor
strategy: parallel
---

## Purpose
Run code quality review and security audit in parallel.
Lead (reviewer) checks spec compliance + code quality + adversarial challenges.
Teammate (sec-auditor) checks PII exposure, injection vulnerabilities, secrets.

## When to Use
- Before merging any PR that touches auth, payment, or user data
- Before production deploys
- When routing-policy detects multi-file changes (3+ files)

## Coordination Protocol
1. Lead and teammate receive the same diff
2. Both run independently (parallel, no blocking)
3. Lead merges findings into single verdict:
   - If either agent finds BLOCKED → final verdict is BLOCKED
   - If either finds NEEDS FIXES → final verdict is NEEDS FIXES
   - READY only if both agree

## Token Budget
~1500-2000 tokens total (split between two agents)
