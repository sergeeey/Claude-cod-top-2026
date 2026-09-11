---
# Path-scoped: FILE-triggered (activates when writing/editing tests), so scoping is safe.
# See coding-style.md's note on why file-triggered rules are scopable but keyword-triggered
# ones (research, evidence) are not.
paths:
  - "tests/**"
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/*.test.ts"
  - "**/*.spec.ts"
  - "**/conftest.py"
---

# Testing Rules

## Adaptive requirements
- **MVP / prototype** → tests are NOT written. Make it work first, test later
- **Production** → pytest coverage ≥ 80% for business logic, ≥ 60% for utilities
- Pre-commit gate: `coverage report --fail-under=80` (if coverage is configured in the project)
- The transition from MVP to Production is agreed upon explicitly

## Test Protection (hard rule)
- NEVER edit or delete a test to make it pass for broken code
- A failing test → fix the CODE, not the test. A test = a behavioral specification
- Exception: a test is outdated (tests a removed feature) → delete it with an explanation of WHY

## Observability Test Isolation (hard rule)

**Source:** found live (2026-09-12) in this exact repo, not hypothetical. A hook's
subprocess-based test suite (`tests/test_routing_floor_classifier.py`'s `_run()` helper,
spawning `python hooks/routing_floor_classifier.py` as a real child process) inherited the
parent test process's real environment — including `HOME`/`USERPROFILE` — so the hook's own
telemetry write (`Path.home() / ".claude" / "logs" / "routing_events.jsonl"`) resolved to this
machine's ACTUAL live log on every one of ~50 test invocations. Confirmed by inspecting the
polluted file directly: 722 lines, every one carrying the test's own synthetic `session_id`
values, none of them real — the hook wasn't even deployed live yet, so there was no genuine
telemetry to lose this time, but the mechanism would have silently corrupted real production
data if it had been.

**The rule:** any test that exercises a hook/script writing to a path derived from the real
machine's identity (`Path.home()`, `~/.claude/...`, an env-var-resolved location) MUST prove
isolation from that real path before the test is trusted — not just "it probably doesn't write
there," an explicit check.

- **In-process calls** (the test imports and calls a function directly): `monkeypatch.setattr`
  the module's own path constant (e.g. `monkeypatch.setattr("lib.state.HOOK_TRIGGERS_LOG",
  tmp_path / "log.jsonl")`) — see `tests/test_hook_triggers_telemetry.py`'s `tmp_log` fixture
  for the established pattern. A monkeypatch on the parent test process has NO effect on a
  child subprocess's own re-imported module state — this is the exact gap the incident above
  exploited.
- **Subprocess-based calls** (the test spawns the hook as a real child process via
  `subprocess.run`): override `HOME`/`USERPROFILE` (Windows reads `USERPROFILE`, not `HOME`, for
  `Path.home()`) in that subprocess's own `env=` mapping to a per-test-session temp directory —
  see `tests/test_routing_floor_classifier.py`'s `_FAKE_HOME` module-level fixture (created once
  via `tempfile.mkdtemp()`, cleaned up via `atexit.register(shutil.rmtree, ...)`) for the fix
  applied after this incident.
- **Verification, not assumption:** after adding isolation, confirm it actually worked by
  checking the REAL path's state before and after the test run (line count, mtime) — don't just
  trust that the env override "should" work. This is how the incident above was both found and
  confirmed fixed.
