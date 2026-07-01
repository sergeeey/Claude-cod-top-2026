# anti-hallucination.md

> **One file. Drop into your `CLAUDE.md` or `~/.claude/`. Costs ~500 tokens. Catches the bug that breaks AI code in production.**

## The Bug

```
Agent writes a test.
Runs it on synthetic data it just generated.
Reports F1=1.000 ✅ SUCCESS.
You deploy.
Real-world data crashes everything.
```

This is **Validation Theater** — the test cannot fail by construction (embedded answers, mock data, circular logic). The "VERIFIED" label is a lie the agent doesn't know it's telling.

A real near-miss in this codebase: agent created 10 niche validators, all returned `100% SUCCESS` on synthetic test cases. User caught it. Estimated cost of deploying it as-is: **$1.4M**.

## The Rules

Drop these four sections into your `CLAUDE.md`. They take ~500 tokens. They prevent the bug above and most of its cousins.

### Rule 1: Evidence markers are mandatory

Mark every factual claim with one of these:

| Marker | Meaning |
|---|---|
| `[VERIFIED-REAL]` | Confirmed with REAL-WORLD data — production URLs, external APIs, dataset names cited |
| `[VERIFIED-SYNTHETIC]` | Confirmed with synthetic / mock data — **valid for unit tests, INVALID for hypothesis validation** |
| `[VERIFIED-INLINE]` | Quick inline check (low confidence, spot-check only) |
| `[DOCS]` / `[CODE]` | From official documentation or source code |
| `[INFERRED]` | Logical conclusion from verified facts. State the chain. |
| `[WEAK]` | Indirect data, analogy, or single source |
| `[UNKNOWN]` | No confirmation. Verification required. |

**Hard rule:** validation claims (F1 scores, success rates, accuracy numbers) **MUST** carry `[VERIFIED-REAL]`. Using `[VERIFIED-SYNTHETIC]` for validation = validation theater. If evidence is synthetic → status = `[NEEDS-REAL-DATA]`, never `SUCCESS`.

### Rule 2: Audit Verification Gate

When a sub-agent or tool returns `[VERIFIED]` — that is **not** your `[VERIFIED]`. That is your `[INFERRED]`.

Before you promote any HIGH/MEDIUM finding to a real claim:

| Claim type | Required verification |
|---|---|
| "Wrong formula" / "wrong sign" | Run `pytest <relevant_test_file>` — if tests pass, downgrade to `[HYPOTHESIS]` |
| "Dangerous default" | `grep -rn '<function_name>('` — find ALL call sites, check if default is ever reached |
| "Missing check / guard" | `grep -rn '<pattern>'` across codebase — may exist elsewhere |
| "Convention mismatch" | Read the FULL call chain, minimum 2 files: caller → function → consumer |
| "Boundary condition wrong" | Run an edge-case test, or write a 3-line numerical check in a shell |

Spot-check 3 random claims after any analysis with 10+ factual items. If any fail → re-verify ALL claims before presenting.

### Rule 3: Validation Theater detector

Before accepting any "SUCCESS" claim, ask these five questions:

1. **Was the test data generated in the same session?** If yes → `[VERIFIED-SYNTHETIC]`, not real validation.
2. **Are the answers embedded in the data?** Look for inline patterns like `test_cases = [(input, label), ...]`. That's circular.
3. **Is the success rate suspiciously round?** F1=1.000 / 100% / "all 10 passed" on noisy real-world tasks is statistically suspicious.
4. **Does the success rate exceed prior base rate by >2.5×?** Industry benchmark 30% → claiming 95% requires extraordinary evidence.
5. **Would I bet $1000 this holds on a different dataset?** If no → status = `[NEEDS-REAL-DATA]`, invoke a skeptic before declaring success.

If any answer is concerning → **stop**. Either find real-world data or downgrade the marker.

### Rule 4: Rationalization Prevention

When you catch yourself thinking these — stop. Each one is a known anti-pattern.

| Excuse | Why it is wrong | What to do |
|---|---|---|
| "I already know this API, no need to read the file" | `[MEMORY]` does not replace `[VERIFIED]`. The API may have changed. | Read the file. Always. |
| "I checked this in a previous message" | Context may have changed after compaction. | Re-verify with a tool. |
| "Sub-agents already verified this" | Agents read docs/READMEs, not code. Their `[VERIFIED]` is actually `[DOCS]`. | Re-verify agent claims with grep/bash. |
| "I wrote the tests and they all pass" | Self-authored tests on self-authored code = circular. A validator that embeds the answer **IS** the answer. | `[VERIFIED]` requires: pre-existing test suite OR independent data source OR test file pre-dating this session. |
| "I'm 90% sure, no need to re-check" | 10% errors = hundreds of bugs per year. | `[UNKNOWN]` is better than a false `[INFERRED]`. |
| "This change is too simple for evidence" | Simple claims can also be wrong. | Mark it. `[VERIFIED]` takes 1 sec. |

## How to measure if this works

The rules above are advisory text. To know whether your agent actually *follows* them, you need telemetry — one log file showing which rule fired and when.

Drop this into a `PostToolUse` hook (or any hook your harness supports):

```python
# ~/.claude/hooks/evidence_telemetry.py — minimum viable measurement
import json, re, sys
from datetime import datetime, UTC
from pathlib import Path

LOG = Path.home() / ".claude" / "logs" / "evidence_triggers.jsonl"
MARKERS = ("[VERIFIED-REAL]", "[VERIFIED-SYNTHETIC]", "[INFERRED]", "[UNKNOWN]")
PERFECT = re.compile(r"F1\s*=\s*1\.0{2,}|100%\s+(?:passed|accuracy)|all\s+\d+\s+tests?\s+passed", re.IGNORECASE)

data = json.load(sys.stdin)
text = str(data.get("tool_response", ""))[:2000]

trigger = None
if PERFECT.search(text) and "[VERIFIED-REAL]" not in text:
    trigger = "perfect_score_no_real_marker"
elif any(m in text for m in MARKERS):
    trigger = "marker_present"

if trigger:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now(UTC).isoformat(),
            "trigger": trigger,
            "sample": text[:200],
        }) + "\n")
sys.exit(0)
```

After 7 days you have data for:
- True positive rate — markers added in next response after warning fires
- False positive rate — idiomatic matches like "always" in poetry
- Drift over time — model updates change behaviour silently

This is the single primitive that turns advisory text into a measurable methodology.

## Why this file is short

Most prompt-engineering "rule packs" are 3000+ tokens of advice the model can ignore. This one is ~500 tokens of **rules** that you also enforce with a hook (telemetry above).

Inspired by Andrej Karpathy's [CLAUDE.md](https://github.com/forrestchang/andrej-karpathy-skills) (4 principles in 65 lines).
Extended specifically for hallucinations in production AI code.

If you want the full enforcement system (84 hooks, 114+ skills, blocking-mode VTG, audit verification gate, [×N] recurring-mistake counter, redact-secrets layer for telemetry logs):

→ **[github.com/sergeeey/Claude-cod-top-2026](https://github.com/sergeeey/Claude-cod-top-2026)**

MIT licensed. Read every hook in 10 minutes before installing.

---

*"Their `[VERIFIED]` is your `[INFERRED]`."*
