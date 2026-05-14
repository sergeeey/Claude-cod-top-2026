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
