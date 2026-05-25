# Audit Report — hooks/ + scripts/ — Round 2 (post-fix)
**Date:** 2026-05-25
**Scope:** D:/Claude-cod-top-2026/hooks/ (50 files) + scripts/ (12 files)
**Auditor:** Claude (Opus) via /sci-code-audit skill chain
**Context:** Round 1 fixed 8 bugs (F1-F10). This round looks for what we still missed.

---

## Layer Summary

| Layer | Status | Findings |
|-------|--------|----------|
| L2 — Silent fallbacks | ⚠️ | 11 broad `except Exception: pass` — 3 dangerous, 8 fail-open OK |
| L3 — Thresholds | ✅ | All thresholds named constants, no magic numbers in hot paths |
| L5 — Invariant tests | ⚠️ | 25 structure tests good, but no JSON schema validation tests |
| L6 — Control validity | ✅ | After F3 fix, tests cover positive+negative paths |
| L7 — State provenance | 🔴 | **11 of 13 state files have NO size/rotation limits** |
| L8 — Statistical/scoring | ✅ | EV thresholds documented, formulas consistent |
| L9 — Docs/code drift | ✅ | CLAUDE.md matches code (sys.exit codes verified) |
| L10 — Reproducibility | ✅ | No hardcoded user paths, no open TODOs |
| **L11 — Recursion guards** | 🔴 | **9 of 13 memory-reading hooks MISSING `CLAUDE_INVOKED_BY` guard** |

---

## 🔴 HIGH severity (3 findings)

### F11: Recursion guard missing on 9 hooks that read memory

**Severity:** HIGH — explicitly warned in `hooks/CLAUDE.md`: *"Missing this = infinite loop when Claude Code invokes subagents."*

**Evidence:** Per `hooks/CLAUDE.md`:
> Every hook that calls Claude or reads memory must check:
> ```python
> if os.environ.get("CLAUDE_INVOKED_BY"):
>     sys.exit(0)
> ```

**Hooks reading memory but MISSING the guard:**
1. `knowledge_librarian.py` — runs on SessionStart, reads wiki + raw memory
2. `learning_tips.py` — reads patterns/learning log
3. `learning_tracker.py` — reads/writes learning log
4. `memory_guard.py` — reads memory files
5. `moc_autolink.py` — reads vault structure
6. `pattern_extractor.py` — reads patterns.md
7. `post_commit_memory.py` — reads/writes memory after commits
8. `session_start.py` — reads activeContext
9. `vector_store.py` — reads tfidf_index.json

**Risk:** If any agent (subagent_type=builder/explorer/etc) invokes a session-start path, these hooks fire recursively → infinite loop, runaway tokens, hung CLI.

**Fix:** Add guard to top of `main()`:
```python
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)
```

### F12: State files grow unbounded — 11 files have no rotation

**Severity:** HIGH — long-running setups accumulate state until disk fills or hooks slow down.

**Evidence:**
```
agent_lifecycle.py      NO LIMIT — agent invocation log
elicitation_guard.py    NO LIMIT — elicitation history
input_guard.py          NO LIMIT — block log
instructions_audit.py   NO LIMIT — audit history
post_tool_failure.py    NO LIMIT — failure log
stop_failure.py         NO LIMIT — stop event log
subagent_verify.py      NO LIMIT — verification log
task_audit.py           NO LIMIT — task history
vector_store.py         NO LIMIT — TF index grows per wiki entry
webhook_notify.py       NO LIMIT — notification queue
worktree_lifecycle.py   NO LIMIT — worktree state
```

Compare: `session_end.py` and `utils.py` DO have `MAX_*` constants — proves the pattern is known but not consistently applied.

**Fix:** Add to each: cap JSON arrays at `MAX_ENTRIES = 1000`, trim oldest on write. Or rotate to daily files (`failure-2026-05-25.jsonl`).

### F13: Unprotected `json.load(sys.stdin)` in statusline.py

**Severity:** HIGH — crashes status line silently on malformed input.

**Evidence:** `hooks/statusline.py:22`
```python
data = json.load(sys.stdin)  # no try/except
```

If Claude Code sends malformed JSON (edge case during transitions, e.g., after compaction), the entire status line dies with no fallback.

**Fix:**
```python
try:
    data = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    data = {}
```

---

## 🟠 MEDIUM severity (3 findings)

### F14: Three `session_save.py` broad excepts swallow real errors

**File:** `hooks/session_save.py:68, 686, 989`
```python
except Exception:
    pass
```

**Assessment:** Lines 68 (git commit time) and 686 (git command) are OK — fail-open is correct when git is unavailable.

**Line 989** is the END of `main()` — it swallows ALL errors from the entire session save logic. If any part fails, you'll never know. At minimum log to stderr:

```python
except Exception as e:
    import traceback
    print(f"session_save error: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
```

### F15: No JSON schema validation for state files on read

**Files:** All hooks that do `json.loads(path.read_text())` then access keys.

**Risk:** Corrupted state file → KeyError → hook dies. The data could come from older hook versions with different schema.

**Fix:** Add a `_validate_state()` helper in `utils.py`:
```python
def load_json_state(path: Path, expected_keys: set[str]) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        # Drop unknown keys, supply defaults for missing
        return {k: data.get(k) for k in expected_keys}
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return {k: None for k in expected_keys}
```

### F16: `vector_store.py` line 113 + `_save_tfidf_index` 123 swallow all errors

**File:** `hooks/vector_store.py:113, 123`

Both load AND save errors are swallowed silently. If the TF index file becomes corrupted, you have no telemetry — the search just silently returns wrong results.

**Fix:** Log to a side-channel (a tiny error log) when corruption is detected:
```python
except Exception as e:
    _log_corruption(f"vector_store load failed: {e}")
    return {}
```

---

## 🟡 LOW severity (2 findings)

### F17: `tfidf_index.json` filename retained after function rename (F10)

**File:** `hooks/vector_store.py` — function renamed `_compute_tfidf` → `_compute_tf_normalized`, but the on-disk filename is still `tfidf_index.json`. Inconsistent with the now-correct function name.

**Fix:** Either rename to `tf_index.json` (and migrate existing file once), or keep filename and add comment: `# WHY: filename kept for backward compat — actual content is L2-normalised TF, not TF-IDF`.

### F18: `cogniml_client.py:59` unprotected json.loads on HTTP response

**File:** `hooks/cogniml_client.py:59`
```python
return cast(dict[str, Any], json.loads(resp.read()))
```

Network response may not be valid JSON (proxy error pages, partial reads). Wrap in try/except returning empty dict.

---

## ✅ What's GOOD (positive findings)

1. **Excellent test coverage** — 1306 passing tests after Round 1
2. **No DRY violations** — utility extraction via `utils.py` works (0 duplicate functions found)
3. **No hardcoded user paths** — repo is portable
4. **No open TODOs/FIXMEs** in production code
5. **Thresholds named** — all magic numbers are constants with docstrings
6. **CLAUDE.md matches code** — sys.exit semantics, recursion guard pattern documented correctly
7. **F8 dismissed correctly** — `sys.exit(1)` in PostToolUse is per protocol, not a bug

---

## Verdict: **NEEDS_WORK → fixable in 1 hour**

The repo has solid architecture and good docs. The remaining gaps are:
- **F11 recursion guards** — critical, prevents infinite loops on subagents
- **F12 state rotation** — prevents long-term disk bloat  
- **F13 statusline crash protection** — prevents UI death on edge cases

After F11-F13 are fixed → **HARDENED**. F14-F18 are nice-to-have.

---

## Rerun policy

No primary results to rerun (this is infrastructure, not research). Just:
1. Apply F11 fix to 9 hooks → verify recursion not triggered
2. Apply F12 to top-3 highest-traffic state files
3. Apply F13 to statusline.py
4. Run full pytest → expect 1306 still passing
