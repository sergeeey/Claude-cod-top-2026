# AI Claim Hygiene — Portable Standard

A framework-agnostic protocol for enforcing evidence discipline in AI-assisted work.
Works with Claude Code, OpenCode, Codex, Cursor, or any AI coding assistant.

## The core problem

AI agents produce confident-sounding output. Without enforcement, claims propagate:

```
agent says [VERIFIED] → orchestrator repeats [VERIFIED] → user believes [VERIFIED]
```

The actual evidence level was never checked.

## Evidence markers (apply to any claim an AI makes)

| Marker | Meaning | Valid for |
|--------|---------|-----------|
| `[VERIFIED-REAL]` | Confirmed with real-world data — external URL, production file, or live API cited | Validation claims, production decisions |
| `[VERIFIED-SYNTHETIC]` | Confirmed with synthetic or mock data | Unit tests only |
| `[VERIFIED-INLINE]` | Quick spot-check, low confidence | Sanity checks only |
| `[NEEDS-REAL-DATA]` | Claim cannot be verified without real-world source | Blocked until real data provided |
| `[INFERRED]` | Logical conclusion from verified facts — chain stated | Intermediate reasoning |
| `[UNKNOWN]` | No confirmation available | Explicit uncertainty |

**Hard rule:** `[VERIFIED-SYNTHETIC]` is never valid for production claims or hypothesis validation.
A validator that embeds its own answer is not a validator.

## The Validation Theater pattern

Validation Theater occurs when:
1. Agent creates test data in the same session
2. Agent tests on that data
3. Agent reports `F1=1.000` or `100% SUCCESS`
4. No external source is cited

Detection checklist:

| Red flag | Check |
|----------|-------|
| Test file created this session | Was the dataset pre-existing? |
| F1=1.000 or round 100% | Real metrics are messy — perfect = suspicious |
| No external URL in evidence | Where is the real-world source? |
| "Ready for production" on synthetic | Synthetic ≠ production |

## The audit gate

Before accepting any HIGH or MEDIUM confidence claim from an agent:

| Claim type | Required verification |
|------------|----------------------|
| Wrong formula / wrong result | Run relevant test — if passes, downgrade to HYPOTHESIS |
| "All tests passed" | Check: were tests pre-existing or created this session? |
| High accuracy metric | Check: real data or synthetic? External source cited? |
| "No issues found" | Spot-check 3 random items with an independent tool |

Agent's `[VERIFIED]` = your `[INFERRED]` until you confirm with a tool.

## Scope discipline

Before claiming "X is clean / works / passes":
**The scope you verified must equal the scope you claim.**

Examples of scope mismatch:
- Ran `mypy hooks/` → claimed "mypy clean" (whole repo had errors in `scripts/`)
- Counted tests locally → claimed CI count (CI environment differs)
- Tested on 5 examples → claimed "works on real data"

Self-check: *"Did I verify exactly what I'm claiming, or a subset?"*

## Minimal implementation (any AI assistant)

Add to your system prompt or CLAUDE.md:

```markdown
## Evidence Policy

All AI claims must carry evidence markers:
- [VERIFIED-REAL] — real-world data, source cited
- [VERIFIED-SYNTHETIC] — synthetic data (unit tests only, never for validation claims)
- [NEEDS-REAL-DATA] — claim blocked until real source provided
- [INFERRED] — logical conclusion, chain stated
- [UNKNOWN] — no confirmation

Hard rules:
1. Synthetic validation is not scientific validation.
2. Agent [VERIFIED] = [INFERRED] until confirmed with a tool.
3. Scope verified must equal scope claimed.
```

## Full implementation

For deterministic enforcement (Python hooks, CI gates, telemetry):
→ [Claude-cod-top-2026](https://github.com/sergeeey/Claude-cod-top-2026)

Includes:
- `hooks/validation_theater_guard.py` — flags synthetic claims (F1=1.000 + mock
  data) with a prominent stderr signal; a post-hoc detector, not a preventive
  block
- `rules/integrity.md` — full evidence policy
- `rules/audit-verification-gate.md` — HIGH/MEDIUM claim verification protocol
- `.github/workflows/ci.yml` — CI gates for metric drift

## Reference

- `rules/integrity.md` — evidence marker definitions
- `rules/audit-verification-gate.md` — verification protocol
- `rules/skeptic-triggers.md` — auto-trigger conditions
- `docs/anti-hallucination.md` — full anti-hallucination methodology
- `demo/validation-theater/` — worked example
