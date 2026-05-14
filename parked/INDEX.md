# Parked Experiments Index

Valid hypotheses, deprioritized for now. NOT falsified — just deferred.

**Difference from null_results/:**
- `null_results/` = REJECT (claim falsified, do not retry)
- `parked/` = ARCHIVE (claim valid or inconclusive, revisit when conditions change)

| ID | Date | Claim Slug | Why Parked | Revisit Trigger |
|---|---|---|---|---|
| — | — | — | — | No entries yet |

---

## How to Add

When experiment ends in ARCHIVE:
1. Copy `experiments/<id>/decision.md` to `parked/<id>-<slug>.md`
2. Add entry to this table with: why parked + what would trigger revival

## How to Use

Before starting a new experiment, grep both indexes:
```bash
grep -i "keyword" null_results/INDEX.md  # falsified — don't repeat
grep -i "keyword" parked/INDEX.md        # valid but deferred — might resume
```
