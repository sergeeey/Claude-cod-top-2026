# Artifact Manifest (Full-Ladder Step 2)

**Experiment ID:** `<YYYYMMDD-short-slug>`

## What Was Built (Minimal Artifact)

Describe the smallest change built to test the hypothesis:

**Type:** code / config / prompt / data-pipeline / other

**Files changed:**
```
- path/to/file.py  (lines X-Y: what changed and why)
- path/to/other.py (lines A-B: what changed and why)
```

**Source diff:**
```diff
# Paste git diff here, or link to PR
```

## What Was NOT Built

Explicitly list what was deferred to keep this minimal:
- [feature/complexity intentionally excluded]

## Reversibility

- **Can this be reverted?** Yes / No
- **Revert command:** `git revert <hash>` or manual steps

## Artifact Checksum (optional, for reproducibility)

```
sha256: <hash of key output file if applicable>
```

## Freeze Record

_Filled AFTER the protocol commit from `claim.md` → `## Frozen Protocol`. Record it here in a later commit, never by rewriting the frozen commit._

| Item | Value |
|---|---|
| Protocol commit SHA | |
| Protocol commit date (UTC) | |
| Holdout labels sha256 (must match the file at run time) | |
| Holdout case count | |
| Amendments (new experiment IDs that replaced a frozen value) | none |

**Check before the decision:** the threshold in `decision.md` equals the threshold in the frozen commit, and the labels sha256 above still matches. Any mismatch → verdict is INVALID, not KEEP/REJECT.
