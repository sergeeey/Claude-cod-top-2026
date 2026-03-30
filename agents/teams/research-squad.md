---
name: research-squad
description: Sequential research — explore then verify. Find facts, then check them for hallucinations.
lead: explorer
teammates:
  - verifier
strategy: sequential
---

## Purpose
Two-phase research: first find information, then verify it.
Lead (explorer) searches the codebase and external sources.
Teammate (verifier) checks all claims for hallucinations.

## When to Use
- Investigating unfamiliar codebases
- Researching external APIs or libraries before integration
- When Evidence Policy requires [VERIFIED] markers on claims

## Coordination Protocol
1. Explorer searches and collects findings
2. Explorer passes findings to verifier via SendMessage
3. Verifier attempts to prove each claim WRONG (hallucination hypothesis)
4. Final output: only [VERIFIED] and [DOCS] claims survive

## Token Budget
~1000-1500 tokens total (explorer finds, verifier validates)
