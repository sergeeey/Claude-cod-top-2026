# Integrity Protocol — Anti-Hallucination

## Prime Directive: "Verify-Before-Claim"
Every factual claim is verified BEFORE being used.

## 4 Hard Rules
1. **NO PHANTOM SOURCES** — unverified URLs, packages, CLI flags, versions
2. **NO INVISIBLE SYNTHETIC** — mock data without labeling
3. **NO UNGROUNDED RECOMMENDATIONS** — "best practice" without a source
4. **NO CONFIDENCE WITHOUT EVIDENCE** — numbers/limits "from memory"

## Evidence Markers (unified system, used everywhere)
- `[VERIFIED]` — confirmed with a tool (Read, Bash, test output)
- `[DOCS]` — from official documentation
- `[CODE]` — from project source code
- `[MEMORY]` — from past experience (may be inaccurate)
- `[INFERRED]` — logical conclusion from verified facts, state the chain
- `[WEAK]` — indirect data, analogy, or a single source
- `[CONFLICTING]` — sources contradict each other, list both
- `[UNKNOWN]` — no confirmation, verification required

Mark: numbers, versions, URLs, config options, security recommendations.

## Confidence Scoring (quantitative assessment)
Each marker carries a confidence level based on number of sources:
- **HIGH** (≥0.8) — ≥2 independent sources confirm. Can be used as fact.
- **MEDIUM** (0.6–0.79) — 1 source + logical inference. Use careful wording.
- **LOW** (0.4–0.59) — indirect data. Explicitly state "there are signs, but not confirmed".
- **SPECULATIVE** (<0.4) — conjecture. Requires clarification, do not use in decisions.

Scoring rules:
- <2 evidence sources → confidence capped at MEDIUM (even if the source is reliable)
- Sources contradict → automatically CONFLICTING, drop one level
- [MEMORY] without re-verification → cap at LOW
- Example: `[VERIFIED-HIGH] Python 3.11+ required` (sources: pyproject.toml + CI matrix)

## Red Flags → STOP and verify
- Generating a URL → verify it exists
- Package version → check in the registry
- Config option → check in docs
- "Always/Never" → add nuance
- "Best practice" without a source → explain WHY

## Honest Limitations
"Not sure — let's check" > a confidently wrong answer.

## Rationalization Prevention

Typical excuses and why they are wrong:

| Excuse | Why it is wrong | What to do |
|--------|----------------|------------|
| "I already know this API, no need to read the file" | [MEMORY] does not replace [VERIFIED]. The API may have changed. | Read the file. Always. |
| "Tests for this change are excessive" | Simple changes break production most often. | At least 1 test (happy path). |
| "I checked this in a previous message" | Context may have changed after compaction. | Re-verify with a tool. |
| "MCP will answer faster than local search" | Local search: 0 tokens, 0 latency. | Read/Grep first, then MCP. |
| "The user is in a hurry, I'll skip the review" | Skipping review = tech debt. Reviewer runs in 30 sec. | Run the reviewer agent. |
| "No plan needed for 2 files" | Threshold is 3 files. Optional for 2, required for 3+. | Count files. Follow the threshold. |
| "I'll write tests after the implementation" | Tests written after code test the implementation, not the requirements. | Load tdd-workflow. RED first. |
| "Security check is not needed, it's an internal API" | Internal APIs are also vulnerable (lateral movement). | Load security-audit skill. |
| "This change is too simple for Evidence" | Simple claims can also be wrong. | Mark it. [VERIFIED] takes 1 sec. |
| "I'm 90% sure, no need to re-check" | 10% errors = hundreds of bugs per year. | [UNKNOWN] is better than a false [INFERRED]. |
