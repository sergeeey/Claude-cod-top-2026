# False-PASS rate

## Why this exists

External comparison (RAAS-2026 reference architecture, 2026-07-21) named this as the single
cheapest, highest-value metric this repo was missing: reviewer and security-guard issue
LGTM/PASS verdicts constantly, but nothing measured how often those verdicts were later
proven wrong. We already had the raw material (git history + verdict text) without ever
computing it.

## How it works

- `hooks/verdict_logger.py` (SubagentStop hook) machine-logs every reviewer
  (`VERDICT: LGTM|NEEDS_WORK|BLOCK`) and security-guard (`Verdict: PASS|BLOCK`) verdict to
  `.claude/memory/verdict_log.jsonl`, tagged with the commit HEAD and files it was about.
  Schema: [`architecture/verdict-record.schema.json`](../architecture/verdict-record.schema.json).
- `scripts/false_pass_rate.py` cross-references PASS-class verdicts (LGTM, PASS) against
  LATER commits (default: within 30 days) whose message starts with `fix`/`revert`/`hotfix`
  AND whose changed files overlap the verdict's files. A match counts as a false pass.

```bash
python scripts/false_pass_rate.py            # human report
python scripts/false_pass_rate.py --json      # machine-readable
python scripts/false_pass_rate.py --window-days 14
```

## What the number means -- and doesn't

This is a **heuristic proxy, not proof of causation**. A `fix:` commit touching the same
file as an earlier LGTM could be unrelated follow-up work, not a correction of that specific
review. Treat a rising rate as a signal to go look at the actual diffs, not as a verdict on
the reviewer.

## Honest current status: bootstrap

The log starts empty the moment this ships. Below `MIN_RECORDS_FOR_RATE` (5) evaluable
PASS-class records, the script reports `status: INSUFFICIENT_DATA` and
`false_pass_rate: null` -- **never** a reassuring `0.0%`. An unmeasured system and a clean
one must never look the same in the report; that's exactly the kind of validation theater
`rules/skeptic-triggers.md` and `rules/integrity.md` exist to prevent. The rate becomes
meaningful only after enough real reviewer/security-guard cycles happen with this hook
active.

## Scope

Only reviewer and security-guard have a machine-parseable verdict format today. verifier,
sec-auditor, skeptic, and others are invisible to this log until they adopt an equally
strict, greppable verdict line -- silently skipped, not estimated as zero.
