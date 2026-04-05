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

## Verify-Output Principle
Give yourself a way to CHECK your output: browser for UI, pytest for code, Read for files.
Iterate until the result passes verification. Do not present unverified output as done.

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
| "Sub-agents already verified this" | Agents read docs/READMEs, not code. Their [VERIFIED] is actually [DOCS]. | Re-verify agent claims with grep/bash. Always. |

## Spot-Check Rule
After any analysis with 10+ factual claims, randomly pick 3 and verify them
with a tool (Read, Grep, Bash). If any fail → re-verify ALL claims before presenting.
This catches the "docs ≠ code" drift that sub-agents miss.

## Causal Debugging (stuck >5 min)
When stuck on a problem for more than 5 minutes, ask these 5 questions in order:
1. **What changed?** — last working state vs current state (git diff, recent edits)
2. **What does the error actually say?** — read the full traceback, not just the last line
3. **What assumptions am I making?** — list them, then verify each with a tool
4. **What is the simplest reproduction?** — minimal example that triggers the issue
5. **What would I tell someone else to check?** — fresh perspective on your own problem
