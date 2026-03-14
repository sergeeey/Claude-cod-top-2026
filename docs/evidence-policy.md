# Evidence Policy — Protection Against Hallucinations

## Why

Without Evidence Policy Claude can confidently say "the problem is in the DB configuration" —
and you'll spend 30 minutes checking before discovering the problem is somewhere else.

With Evidence Policy the same answer looks like:
> [VERIFIED] test test_auth fails with ConnectionRefused (pytest output).
> [INFERRED] likely cause — PostgreSQL is not running, .env points to localhost:5432.
> [UNKNOWN] did not verify docker-compose presence.

You instantly see what was verified and what was not.

## 6 Markers

### [VERIFIED]
Verified with a tool: Read, Bash, pytest output, grep.
**The most reliable level.** Fact confirmed by direct observation.

### [DOCS]
From official documentation. Link or quote attached.
Reliable, but documentation may be outdated.

### [CODE]
From the project's source code. File was read, line is specified.
Reliable for the current state of the code.

### [INFERRED]
Logical conclusion from verified facts. Reasoning chain is specified.
May be inaccurate — verify if critical.

### [WEAK]
Indirect data, analogy, single source.
Requires confirmation before making decisions.

### [CONFLICTING]
Sources contradict each other. Both are listed.
Requires manual resolution.

### [UNKNOWN]
No confirmation. An honest "I don't know".
**Main rule: [UNKNOWN] is ALWAYS better than a false [INFERRED].**

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
