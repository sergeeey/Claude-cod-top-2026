# Claim

**Experiment ID:** `<YYYYMMDD-short-slug>`
**Date:** YYYY-MM-DD
**Author:** Claude / human
**Ladder tier:** micro / standard / full

## Falsifiable Statement

> [One sentence. Must be falsifiable — specify what would prove it WRONG.]

Example: "Adding rate-limit guard to mcp-bouncer reduces prompt injection bypass rate from X% to <5% on adversarial test suite."

## Falsification Criteria

What would FALSIFY this claim:
- [ ] bypass rate remains above 5% after change
- [ ] positive control fails (known-good input rejected)
- [ ] performance regression >10% on baseline

## Success Criteria

What would CONFIRM this claim:
- [ ] bypass rate <5% on adversarial suite
- [ ] positive control passes
- [ ] no regression on baseline

## Related

- Prior null results: (grep null_results/INDEX.md for related keywords)
- Linked PR/issue:
