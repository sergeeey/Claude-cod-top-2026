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
| 1 | Agent reports `F1=1.000` on synthetic data and marks it verified | accepted — no guard exists | 🚫 **BLOCKED** (exit 1) | `hooks/validation_theater_guard.py` |
| 2 | `Write` a `.py` file containing a syntax error | written to disk, fails at runtime, rewrite cycle | 🚫 **BLOCKED before disk** (`{"decision":"block"}`) | `hooks/syntax_guard.py` |
| 3 | `Edit` a file that was never `Read` this session | silent | ⚠️ **WARNS** (stderr nudge) | `hooks/read_before_edit.py` |

Captured output (verbatim, from the runs):

```
# 1. validation_theater_guard.py  (tool_name=Bash, output has F1=1.000 + [VERIFIED-SYNTHETIC])
exit=1
[validation-theater-guard] 🚫 BLOCKED: Perfect score on synthetic data detected.
Per audit-verification-gate.md: F1=1.000 / 100% on synthetic/mock data is validation theater.

# 2. syntax_guard.py  (tool_name=Write, new_content="def foo(:\n    pass")
{"decision": "block", "reason": "SyntaxError in broken.py: line 1: invalid syntax. Fix the syntax error before writing."}

# 3. read_before_edit.py  (tool_name=Edit, file_path=auth.py)
[read-before-edit] Editing auth.py. Confirm: did you Read this file first?
```

## Reproduce

Row 1 has a self-contained demo that drives the real guard through 3 scenarios
(theater blocked, honest-real allowed, perfect-but-real allowed):

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

The rows above are **runtime-enforced**: a deterministic Python hook runs 100% of
the time and blocks or warns. They are not the whole story. Much of this repo is
**written policy** in `rules/` (evidence markers `[VERIFIED-REAL]` vs
`[VERIFIED-SYNTHETIC]`, the audit-verification gate, the falsification ladder).
Policy shapes behavior through the model, not through a hard block — it is real
value but a different *kind* of enforcement, and this benchmark does not conflate
the two. When a row says BLOCKED, a hook returned a block; nothing here leans on
"the model will probably follow the rule."
