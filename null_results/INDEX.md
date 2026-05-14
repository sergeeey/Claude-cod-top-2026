# Null Results Index

Rejected and archived hypotheses. Read before starting work in related areas.
**Purpose:** Prevent agents from re-attempting already-falsified approaches.

| ID | Date | Claim Slug | Verdict | Why (10 words max) |
|---|---|---|---|---|
| — | — | — | — | No entries yet |

---

## How to Add an Entry

When experiment ends in REJECT or ARCHIVE:

1. Copy `experiments/<id>/decision.md` to `null_results/<id>-<slug>.md`
2. Add one line to this table:
   ```
   | 20260514-my-idea | 2026-05-14 | my-idea | REJECT | LLM hallucinated controls, F1=0 on real data |
   ```

## How to Use This Index

Before starting work on a topic:
```bash
grep -i "keyword" null_results/INDEX.md
```

If related null result found → read the full `null_results/<id>.md` before proceeding.
Do NOT repeat an approach that was REJECT without documenting why this time is different.
