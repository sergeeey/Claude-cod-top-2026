# Diagnostic matrix, dependency invalidation and privacy gate

## Evidence-based report

For each of the ten named axes in SKILL.md include `status`, `evidence`, `coverage`, `risk` and `action`. No aggregate rating. `PASS` needs a relevant executed or inspected test. `PARTIAL` means some checks supported and some gaps remain. `FAIL` requires an observed violated contract. `UNKNOWN` means no trustworthy verdict. `N/A` may annotate inapplicable subchecks, never masquerade as passed tests.

## Illustrative dependency binding (not a mandatory new file format)

```yaml
id: K-17
claim: 'Result X was verified under the listed inputs'
depends_on:
  code:
    path: parser.py
    sha256: '<recorded content hash>'
    revision: abc123
  dataset:
    id: D
    version: v4
  test_run:
    id: T-19
    environment: '<recorded environment>'
verification_state: VERIFIED
claim_truth_state: UNRESOLVED
stale_if:
  - parser.py
  - D@v4
```

When `parser.py` differs from the recorded hash, **only** `verification_state` of K-17's dependent run becomes `RECHECK_REQUIRED` (or equivalent). Do not assert `claim_truth_state: FALSE`. Compute changes transitively where dependencies are known; list opaque edges as `UNKNOWN`. A subsequent re-run must have its own ID, timestamp, exact command, exit code and inputs; never overwrite history to hide invalidation.

## Privacy gate

Draw or tabulate `source -> reader/processor -> cache or destination -> permission/evidence`. Inspect local/project/global hooks, shared memories, Obsidian or vault sync, vector indices, cloud connectors and remotes that **actually exist**. For each crossing of a project boundary record whether it is intended, approved and technically isolated. Treat unconfirmed permissions as `UNKNOWN` and observed unauthorised crossing as `FAIL` with a blocking recommendation. No active exfiltration probes and no production injection.

## Anti-overengineering test

For each proposed component prove a specific observed defect, measurable benefit, smallest alternative, ongoing maintenance cost, rollback and failure mode. If these are absent, recommend `KEEP` or bounded `UNKNOWN`, not new tools.
