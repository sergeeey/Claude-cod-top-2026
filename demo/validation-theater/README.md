# Demo: Validation Theater Detection

This demo shows the core detection loop: an agent claims success on synthetic data, the hook flags it via a `PostToolUse` context injection, and the agent is required to downgrade the claim before it reaches the user. This is a strong signal, not a preventive block — see `BENCHMARK.md`'s "Runtime guard vs written policy" section for the full distinction (a `PostToolUse` hook fires after the tool call already happened; it cannot undo it, only flag it loudly).

## The problem

```
Agent trains classifier on synthetic examples
→ Tests on the same synthetic examples
→ Reports F1=1.000 ✅ SUCCESS
→ User deploys
→ Real-world data crashes everything
```

This is **Validation Theater**: the test cannot fail by construction because the answer is embedded in the test data.

## The detection

Run the scenario to see the hook fire:

```bash
# Simulate the agent claim (pipe JSON as stdin, as the hook expects from Claude Code)
cat demo/validation-theater/input.json | python -c "
import json, sys
data = json.load(sys.stdin)
print('Simulating agent claim:', data['agent_claim'])
print('Evidence type:', data['evidence_type'])
print('External URL:', data['external_url'])
print('Test created this session:', data['test_file_created_this_session'])
"
```

Expected hook behavior: see [`expected_hook_output.txt`](expected_hook_output.txt)

> **Note:** `hooks/validation_theater_guard.py` runs as a Claude Code PostToolUse hook —
> it receives tool call data via stdin from the Claude Code harness, not as a CLI command.
> The demo shows the *detection logic and expected output*, not a standalone CLI runner.

## What the hook checks

| Signal | Rule |
|--------|------|
| F1=1.000 or 100% | Round-number flag (Trigger 4) |
| Test file created this session | Synthetic evidence flag (Trigger 5) |
| No external URL / data source | Missing `[VERIFIED-REAL]` evidence |
| "READY FOR PRODUCTION" without real data | High-confidence claim flagged — agent required to downgrade |

## Result

| Before hook | After hook |
|-------------|------------|
| `[VERIFIED] F1=1.000 SUCCESS` | `[VERIFIED-SYNTHETIC] [NEEDS-REAL-DATA]` |
| Agent: "ready for production" | Agent: "real-world validation required" |
| Claim promoted | Claim flagged; agent required to downgrade |

## Evidence marker reference

- `[VERIFIED-REAL]` — tested on real-world data, external sources cited
- `[VERIFIED-SYNTHETIC]` — tested on synthetic/mock data (valid for unit tests only)
- `[NEEDS-REAL-DATA]` — correct status when no real-world source exists

Full protocol: [`rules/integrity.md`](../../rules/integrity.md) · [`rules/audit-verification-gate.md`](../../rules/audit-verification-gate.md)
