# Benchmark — vanilla Claude Code vs this config

> What changes when you add this repo's hooks to a stock Claude Code install?
> Every "this config" verdict below is a **real run of the shipped hook**, not a
> claim. The commands are included so you can reproduce each row yourself.

## Scope (and what this is NOT)

- **Baseline = vanilla Claude Code**: a stock install with no `CLAUDE.md`, no
  hooks, no rules. Its column is "what happens with nothing installed."
- **This config**: the hooks in `hooks/`, exercised directly by piping the exact
  PostToolUse/PreToolUse payload Claude Code would send.

This table deliberately has **no column for other configs** (gstack, etc.).
Benchmarking a tool means running it; we have not run those, so asserting how
they behave would be exactly the unverified claim this repo exists to prevent.
If you want such a column, run the scenarios against that config and add it.

## Results

Each row was produced by piping a payload into the named hook with
`CLAUDE_INVOKED_BY` unset (so the guard actually executes). Verdicts are the
hook's real exit code / stdout decision.

| # | Scenario | Vanilla Claude Code | This config | Enforced by |
|---|----------|---------------------|-------------|-------------|
| 1 | Agent reports `F1=1.000` on synthetic data and marks it verified | accepted — no guard exists | 🛑 **STRONG SIGNAL, post-hoc** (exit 1 — the Bash call already ran; see note below) | `hooks/validation_theater_guard.py` |
| 2 | `Write` a `.py` file containing a syntax error | written to disk, fails at runtime, rewrite cycle | 🚫 **PREVENTED before disk** (`{"decision":"block"}`) | `hooks/syntax_guard.py` |
| 3 | `Edit` a file that was never `Read` this session | silent | ⚠️ **WARNS** (stderr nudge) | `hooks/read_before_edit.py` |

Captured output (verbatim, from the runs):

```
# 1. validation_theater_guard.py  (tool_name=Bash, output has F1=1.000 + [VERIFIED-SYNTHETIC])
exit=1
[validation-theater-guard] 🚫 STOP: Perfect score on synthetic data detected.
The command already ran -- this cannot undo that -- but do NOT treat its result as valid evidence.
Per audit-verification-gate.md: F1=1.000 / 100% on synthetic/mock data is validation theater.

# 2. syntax_guard.py  (tool_name=Write, new_content="def foo(:\n    pass")
{"decision": "block", "reason": "SyntaxError in broken.py: line 1: invalid syntax. Fix the syntax error before writing."}

# 3. read_before_edit.py  (tool_name=Edit, file_path=auth.py)
[read-before-edit] Editing auth.py. Confirm: did you Read this file first?
```

## Reproduce

Row 1 has a self-contained demo that drives the real guard through 3 scenarios
(theater flagged, honest-real allowed, perfect-but-real allowed):

```bash
python examples/validation-theater-trap/run_trap.py
```

Rows 2 and 3 — pipe a payload to the hook directly (PowerShell / bash):

```bash
echo '{"tool_name":"Write","tool_input":{"file_path":"x.py","new_content":"def f(:\n pass"}}' \
  | PYTHONPATH=hooks python hooks/syntax_guard.py        # -> {"decision":"block",...}

echo '{"tool_name":"Edit","tool_input":{"file_path":"auth.py"}}' \
  | PYTHONPATH=hooks python hooks/read_before_edit.py    # -> stderr nudge
```

## Runtime guard vs written policy — an honest distinction

The rows above are all **runtime-enforced** — a deterministic Python hook runs
100% of the time — but not uniformly the same *kind* of enforcement:

- **Row 2 is a true preventive block**: `syntax_guard.py` runs on
  `PreToolUse`, which fires BEFORE the tool executes — `{"decision":"block"}`
  stops the write from ever reaching disk. Vanilla Claude Code has no
  equivalent; this config does.
- **Row 1 is a strong post-hoc signal, not a preventive block**:
  `validation_theater_guard.py` runs on `PostToolUse`, which fires AFTER the
  Bash command already completed. `sys.exit(1)` cannot undo that call or
  erase its output — it surfaces a loud stderr warning the model sees on its
  next turn. Still real value over vanilla (which has nothing here), but not
  the same guarantee as row 2. An earlier version of this table called row 1
  "BLOCKED" without this distinction — corrected (security audit
  2026-07-12, F-03/F-12 finding: `PostToolUse` cannot actually block).
- **Row 3 is a soft nudge**: `read_before_edit.py` only injects an
  `additionalContext` warning; the edit proceeds regardless.

Much of this repo is also **written policy** in `rules/` (evidence markers
`[VERIFIED-REAL]` vs `[VERIFIED-SYNTHETIC]`, the audit-verification gate, the
falsification ladder) — a fourth, even softer category: no hook fires at all,
only text in context the model has to remember and choose to apply.
