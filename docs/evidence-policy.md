# Evidence Policy — Protection Against Hallucinations

## Why

Without Evidence Policy Claude can confidently say "the problem is in the DB configuration" —
and you'll spend 30 minutes checking before discovering the problem is somewhere else.

With Evidence Policy the same answer looks like:
> [VERIFIED] test test_auth fails with ConnectionRefused (pytest output).
> [INFERRED] likely cause — PostgreSQL is not running, .env points to localhost:5432.
> [UNKNOWN] did not verify docker-compose presence.

You instantly see what was verified and what was not.

## Markers — Three Families

### Base Markers (use always)

| Marker | Meaning |
|---|---|
| `[VERIFIED]` | Confirmed with a tool: Read, Bash, pytest, grep. Most reliable. |
| `[DOCS]` | From official documentation. May be outdated — link required. |
| `[CODE]` | From project source code. File read, line specified. |
| `[INFERRED]` | Logical conclusion from verified facts. State the reasoning chain. |
| `[WEAK]` | Indirect data, analogy, single source. Needs confirmation. |
| `[CONFLICTING]` | Sources contradict each other. Both listed. Needs manual resolution. |
| `[UNKNOWN]` | No confirmation. **Always better than a false [INFERRED].** |
| `[MEMORY]` | From past experience. May be inaccurate — re-verify if critical. |

### Data-Type Variants (for validation claims)

Use these instead of plain `[VERIFIED]` when data source matters:

| Marker | Meaning |
|---|---|
| `[VERIFIED-REAL]` | Tested on real-world data. Sources cited (URLs, file paths, dataset names). Required for hypothesis validation and submission claims. |
| `[VERIFIED-SYNTHETIC]` | Tested on synthetic/mock data. Valid for unit tests. **NOT valid** for production validation claims or hypothesis confirmation. |
| `[VERIFIED-INLINE]` | Quick inline sanity check. Low confidence — not for production claims. |

**Rule:** Hypothesis validation MUST use `[VERIFIED-REAL]`. `[VERIFIED-SYNTHETIC]` on a validation claim = validation theater.

### Confidence Variants (for evidence scoring)

Add confidence level when source count matters:

| Marker | Meaning | Sources required |
|---|---|---|
| `[VERIFIED-HIGH]` | ≥2 independent sources confirmed. Can be used as fact. | ≥2 |
| `[VERIFIED-MEDIUM]` | 1 source + logical inference. Use careful wording. | 1 |
| `[VERIFIED-LOW]` | Indirect data. State "there are signs, but not confirmed". | 0 |

**Canonical source:** `~/.claude/rules/integrity.md`  
**Enforced by:** `hooks/evidence_guard.py` (recognises all three families)

## What to Mark

- Numbers, versions, limits
- URLs, file paths
- Config options, CLI flags
- Security recommendations
- Test results, metrics

## What NOT to Mark

- Common knowledge (Python is an interpreted language)
- Logical reasoning (if A and B, then C)
- Written code (code itself is not a factual claim)

## 4 Hard Prohibitions

1. **NO FABRICATION** — do not invent metrics, results, versions, URLs
2. **NO PHANTOM REFERENCES** — do not reference files without verifying them
3. **NO UNGROUNDED RECOMMENDATIONS** — "best practice" without a source
4. **NO CONFIDENCE WITHOUT EVIDENCE** — numbers/limits "from memory"

## Red Flags → STOP and Verify

- Generating a URL → verify it exists
- Package version → verify in registry
- Config option → verify in docs
- "Always/Never" → add nuance
- "Best practice" without a source → explain WHY

## Example in Action

**Without Evidence Policy:**
> "Redis cache is misconfigured, need to increase maxmemory to 2GB."

**With Evidence Policy:**
> [VERIFIED] Redis is using 1.8GB out of 2GB (redis-cli INFO memory).
> [CODE] maxmemory is set to 2gb (redis.conf:47).
> [INFERRED] eviction is already occurring → need to either increase the limit
> or optimize keys (TTL).
> [UNKNOWN] did not check usage pattern — some keys may be stale.
