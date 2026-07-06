"""
expert_registry.py — Compiled Expert Registry.

Core idea (from Extella architecture analysis, 2026-06-14):
  Traditional agent: pays LLM tokens on EVERY run.
  Compiled Expert:   pays LLM tokens ONCE (to derive solution logic),
                     then runs pure Python forever.

Economic formula:
  Agent:  C = Σ (T_prompt_i * P_in + T_gen_i * P_out)  [every run]
  Expert: C = one_time_reasoning + N * execution_cost    [N >> 1 → huge savings]

Usage:
  1. Claude solves a task → user says "compile this as expert X"
  2. Skill formats solution as expert_main(input_data) function
  3. expert_registry.compile_expert("name", code, description, tags)
  4. Next runs: expert_registry.run_expert("name", input_data) → pure Python

Expert contract:
  - Code MUST define a function named `expert_main(input_data: dict) -> dict`
  - input_data / return value are JSON-serializable dicts
  - Imports are allowed inside the function body (stdlib + installed packages)
  - No side effects unless explicitly tagged with side_effects=True

Registry location: ~/.claude/cache/expert_registry.json
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from utils import file_lock

# WHY (HIGH, cross-model audit): `entry["name"]` is used directly to build a
# vault-note filename with no validation. `compile_expert(name="../x")` --
# or worse, a name shaped like an absolute path -- writes OUTSIDE
# knowledge/experts/ entirely, since pathlib's `/` operator fully REPLACES
# the base path when the right-hand side is itself absolute (e.g.
# `folder / "C:/Windows/x"` on Windows discards `folder` completely). The
# docstring already documents "name: Unique identifier (snake_case)" --
# this enforces that documented contract instead of trusting it.
_SAFE_EXPERT_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

REGISTRY_PATH = Path.home() / ".claude" / "cache" / "expert_registry.json"
VAULT_PATH = Path.home() / ".claude" / "memory"
EXPERT_FUNCTION = "expert_main"
# WHY (MEDIUM, cross-model audit): compile_expert()/run_expert()/rollback()/
# delete() all do a load-mutate-save sequence sharing the same _save() tmp
# path with no locking -- concurrent calls can lose run_count/last_run/
# newly-compiled experts to last-writer-wins.
_LOCK_PATH = REGISTRY_PATH.with_suffix(".lock")


@contextlib.contextmanager
def _locked():
    """Acquire _LOCK_PATH or raise -- never silently proceed unprotected.

    WHY this exists (real bug found by a cross-file concurrency test, not
    just reasoning): file_lock()'s default timeout is 2.0s and, on timeout,
    YIELDS False rather than raising -- a bare `with file_lock(...):` still
    ENTERS the block even when the lock was never acquired. Under real
    multi-file contention, some caller's wait exceeded 2s, so it proceeded
    WITHOUT exclusivity, reintroducing the exact lost-update race the lock
    exists to prevent (confirmed via a deliberately-shortened timeout
    reproducing the corruption). 15s is far more than any realistic
    registry read-modify-write should ever need; raising instead of
    silently proceeding means a genuine timeout surfaces as an error.
    """
    with file_lock(_LOCK_PATH, timeout=15.0) as acquired:
        if not acquired:
            raise TimeoutError(f"Could not acquire expert_registry lock: {_LOCK_PATH}")
        yield


# ── I/O ──────────────────────────────────────────────────────────────────────


def _load() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {}
    try:
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            result: dict[str, Any] = json.load(f)
            return result
    except Exception:
        return {}


def _save(registry: dict[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2, default=str)
    # WHY retry on PermissionError (found by a real 20-thread concurrency
    # test, not just reasoning): the mutating functions above all hold
    # _LOCK_PATH during _save(), but read-only functions (lookup, list_all,
    # search_experts, test_expert) still call _load() WITHOUT the lock, by
    # design, so they don't serialize behind every write. On Windows,
    # os.replace() can transiently fail with PermissionError/WinError 5 if
    # ANY reader has REGISTRY_PATH open at that exact instant -- retrying a
    # few times with a short backoff is standard practice for this specific,
    # well-known Windows os.replace() race and closes it without forcing
    # every read to take the write lock too.
    last_exc: PermissionError | None = None
    for attempt in range(5):
        try:
            os.replace(str(tmp), str(REGISTRY_PATH))
            return
        except PermissionError as exc:
            last_exc = exc
            if attempt < 4:
                time.sleep(0.02 * (attempt + 1))
    raise last_exc  # type: ignore[misc]


# ── Vault sync ───────────────────────────────────────────────────────────────


def _write_vault_note(entry: dict[str, Any]) -> Path | None:
    """
    Write a knowledge card to Obsidian vault at VAULT_PATH/knowledge/experts/{name}.md.

    Returns the path written, or None if vault is unavailable.
    Silently skips — never raises — so compile_expert() is never blocked by vault issues.
    """
    try:
        folder = VAULT_PATH / "knowledge" / "experts"
        folder.mkdir(parents=True, exist_ok=True)

        name = entry["name"]
        if not _SAFE_EXPERT_NAME_RE.match(name):
            # WHY silently skip, not raise: this function's contract is
            # "never blocks compile_expert() on vault issues" -- an invalid
            # name means no vault note, not a failed expert compilation.
            return None
        tags_yaml = ", ".join(f'"{t}"' for t in ["expert"] + entry.get("tags", []))
        updated = (entry.get("updated_at") or "")[:10]
        version = entry.get("version", "—")
        desc = entry.get("description", "")
        schema = entry.get("input_schema", "")
        cases = entry.get("test_cases") or []

        lines = [
            "---",
            f"tags: [{tags_yaml}]",
            f'name: "{name}"',
            f'version: "{version}"',
            f'updated: "{updated}"',
            "---",
            "",
            f"# Expert: {name}",
            "",
            desc or "_No description._",
            "",
        ]

        if schema:
            lines += ["## Input schema", "", f"```\n{schema}\n```", ""]

        if cases:
            lines += ["## Examples", ""]
            for i, tc in enumerate(cases[:3]):
                inp = json.dumps(tc.get("input", {}), ensure_ascii=False)
                exp = json.dumps(tc.get("expected", "?"), ensure_ascii=False)
                lines += [f"**[{i}]** `{inp}` → `{exp}`", ""]

        lines += [
            "## Registry",
            "",
            f"Source: `~/.claude/cache/expert_registry.json` key `{name}`",
            f'Run: `expert_registry.run_expert("{name}", {{...}})`',
            "",
        ]

        note_path = folder / f"{name}.md"
        # WHY defense-in-depth on top of the regex above: verifies the
        # actual resolved write target stays inside `folder`, independent
        # of whether the name-format check above stays correct forever.
        try:
            note_path.resolve().relative_to(folder.resolve())
        except ValueError:
            return None
        note_path.write_text("\n".join(lines), encoding="utf-8")
        return note_path
    except Exception:
        return None


# ── Validation ────────────────────────────────────────────────────────────────


def _validate_code(code: str) -> str | None:
    """
    Validate that code defines expert_main.
    Returns error string, or None if valid.
    """
    if EXPERT_FUNCTION not in code:
        return f"Code must define a function named `{EXPERT_FUNCTION}(input_data)`"
    try:
        compile(code, "<expert>", "exec")
    except SyntaxError as e:
        return f"SyntaxError in expert code: {e}"
    return None


# ── Core ops ──────────────────────────────────────────────────────────────────


def compile_expert(
    name: str,
    code: str,
    *,
    description: str = "",
    tags: list[str] | None = None,
    input_schema: str = "",
    side_effects: bool = False,
    deterministic: bool = True,
    test_input: dict | None = None,
    test_cases: list[dict] | None = None,
    version: str = "",
    save_to_vault: bool | None = None,
) -> dict[str, Any]:
    """
    Crystallize a solution into a compiled expert.

    Args:
        name:          Unique identifier (snake_case).
        code:          Python code defining expert_main(input_data) -> dict.
        description:   What this expert does.
        tags:          Keywords for discovery.
        input_schema:  Plain-text description of expected input_data keys.
        side_effects:  Set True if expert writes files or calls APIs.
        deterministic: False = skip regression check (LLM inside, timestamps, randomness).
        test_input:    Optional dict to run a smoke test immediately (deprecated: use test_cases).
        test_cases:    List of {"input": dict, "expected": dict} for contract validation.
                       On recompile: checked against NEW code to detect regressions.
        version:       Semantic version string (e.g. "1.0", "0.2"). Auto-increments patch if empty.
        save_to_vault: Write Obsidian note to VAULT_PATH/knowledge/experts/{name}.md.
                       None (default) = auto — True if test_cases present, False otherwise.
                       True = always write. False = never write.

    Returns:
        Entry dict.

    Raises:
        ValueError if code is invalid, smoke test fails, or regression detected.
    """
    error = _validate_code(code)
    if error:
        raise ValueError(error)

    # WHY the WHOLE function body under one lock, not just the final save
    # (found by a real concurrency test, not just reasoning): locking only
    # the tail left this function's initial _load() unprotected, so it could
    # read expert_registry.json at the exact moment a DIFFERENT thread's
    # locked _save() was mid os.replace() -- Windows refuses to rename over
    # a file that has any open read handle, raising a genuine (reproducible
    # in a 20-thread test) PermissionError. Every access to the registry
    # file -- read or write -- must go through the same lock to close this
    # at the root. Compiling is a rare/occasional operation by this module's
    # own design (pay LLM tokens once, run pure Python after), so serializing
    # it fully (including the regression-check re-execution below) is an
    # acceptable tradeoff for correctness. See _locked() for why timeout=15
    # + an explicit acquired-check (not a bare `with file_lock(...):`).
    with _locked():
        registry = _load()
        now = datetime.now(UTC).isoformat()
        existing = registry.get(name, {})

        # Regression check: run existing test_cases against the NEW code before saving.
        # Rules:
        #   - Only fires when test_cases is NOT explicitly provided
        #     (new contract = intentional change).
        #   - Skipped for non-deterministic experts (deterministic=False)
        #     -- LLM output, timestamps, etc.
        if (
            existing
            and existing.get("test_cases")
            and test_cases is None
            and existing.get("deterministic", True)
        ):
            candidate_entry = {"code": code}
            for i, tc in enumerate(existing["test_cases"]):
                r = _execute(candidate_entry, tc["input"])  # type: ignore[arg-type]
                hint = "Expert NOT updated. Fix the code or pass test_cases= for a new contract."
                if "error" in r:
                    raise ValueError(
                        f"Regression in '{name}' test_case[{i}]: "
                        f"runtime error — {r['error'][:200]}. {hint}"
                    )
                if "expected" in tc and r.get("output") != tc["expected"]:
                    raise ValueError(
                        f"Regression in '{name}' test_case[{i}]: "
                        f"input={tc['input']!r}, expected={tc['expected']!r}, "
                        f"got={r.get('output')!r}. {hint}"
                    )

        # Auto-version: bump patch if version not provided
        resolved_version = version
        if not resolved_version:
            prev = existing.get("version", "0.0")
            try:
                parts = prev.split(".")
                resolved_version = f"{parts[0]}.{int(parts[-1]) + 1}"
            except (ValueError, IndexError):
                resolved_version = "0.1"

        import hashlib as _hashlib

        entry: dict[str, Any] = {
            "name": name,
            "description": description,
            "code": code,
            "source_sha256": _hashlib.sha256(code.encode()).hexdigest(),
            "version": resolved_version,
            "prev_code": existing.get("code"),  # rollback support
            "prev_version": existing.get("version"),
            "tags": tags or [],
            "input_schema": input_schema,
            "side_effects": side_effects,
            "deterministic": deterministic,
            "test_cases": test_cases if test_cases is not None else existing.get("test_cases", []),
            "compiled_at": existing.get("compiled_at", now),
            "updated_at": now,
            "run_count": existing.get("run_count", 0),
            "last_run": existing.get("last_run"),
            "last_error": None,
        }

        # Smoke test (legacy single-input form)
        if test_input is not None:
            result = _execute(entry, test_input)
            if "error" in result:
                raise ValueError(f"Smoke test failed: {result['error']}")
            entry["test_input"] = test_input
            entry["test_output_preview"] = str(result.get("output", ""))[:200]

        registry[name] = entry
        _save(registry)

    should_save = save_to_vault if save_to_vault is not None else bool(entry.get("test_cases"))
    if should_save:
        _write_vault_note(entry)

    return entry


def run_expert(
    name: str,
    input_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute a compiled expert by name.

    Returns dict with keys:
      output  — whatever expert_main returned
      elapsed — seconds
      error   — present only on failure
    """
    # WHY this initial read under the lock too (found by a real concurrency
    # test): an unlocked read here can hit a Windows PermissionError if it
    # lands mid os.replace() from another thread's locked _save() -- ALL
    # registry.json access, read or write, must share the same lock to
    # avoid that collision. Released immediately after copying `entry` so
    # _execute() below (which can take arbitrary time) does NOT serialize
    # concurrent expert executions -- only the metadata reads/writes do.
    with _locked():
        registry = _load()
        if name not in registry:
            known = list(registry.keys())
            return {"error": f"Expert '{name}' not found. Known: {known}"}
        entry = registry[name]

    # Drift detection: warn if stored code no longer matches source_sha256
    import hashlib as _hl

    stored_sha = entry.get("source_sha256", "")
    actual_sha = _hl.sha256(entry["code"].encode()).hexdigest()
    drift_warning = stored_sha and stored_sha != actual_sha

    result = _execute(entry, input_data)
    if drift_warning:
        result["warning"] = (
            f"source_sha256 mismatch for '{name}' — code may have been edited "
            f"outside compile_expert(). Run compile_expert() to re-register."
        )

    # Update stats
    # WHY lock + re-read (MEDIUM, cross-model audit): _execute() above can
    # take arbitrary time, during which another process may have run/
    # compiled a DIFFERENT expert -- committing the stale outer `registry`
    # would silently discard that other update. Only re-check `name` itself
    # for a rare concurrent-delete race.
    with _locked():
        registry = _load()
        if name in registry:
            registry[name]["run_count"] = registry[name].get("run_count", 0) + 1
            registry[name]["last_run"] = datetime.now(UTC).isoformat()
            registry[name]["last_error"] = result.get("error")
            _save(registry)

    return result


def _inplacevar(op: str, x: Any, y: Any) -> Any:
    """Augmented assignment handler for RestrictedPython (+=, -= etc.)."""
    ops: dict[str, Any] = {
        "+=": lambda a, b: a + b,
        "-=": lambda a, b: a - b,
        "*=": lambda a, b: a * b,
        "/=": lambda a, b: a / b,
        "//=": lambda a, b: a // b,
        "**=": lambda a, b: a**b,
        "%=": lambda a, b: a % b,
        "&=": lambda a, b: a & b,
        "|=": lambda a, b: a | b,
        "^=": lambda a, b: a ^ b,
    }
    if op in ops:
        return ops[op](x, y)
    raise NotImplementedError(f"In-place operator {op!r} not supported in sandboxed expert")


def _compile_expert_code(code: str) -> tuple[Any, bool]:
    """
    Compile expert code. Returns (compiled, sandboxed).
    sandboxed=True  → RestrictedPython (blocks dunder escapes at compile time).
    sandboxed=False → plain compile (RestrictedPython rejected valid code or not installed).
    """
    try:
        from RestrictedPython import compile_restricted_exec  # noqa: PLC0415

        result = compile_restricted_exec(code)
        if not result.errors:
            return result.code, True
        # RP rejected the code — fall through to plain compile
    except ImportError:
        pass
    return compile(code, "<expert>", "exec"), False


def _build_restricted_globals() -> dict[str, Any]:
    """Restricted globals for RestrictedPython exec.

    Allows stdlib/pip imports, blocks dunder attribute access patterns.
    """
    from RestrictedPython.Guards import (  # noqa: PLC0415
        full_write_guard,
        safe_builtins,
        safer_getattr,
    )

    return {
        "__builtins__": safe_builtins,
        "_getattr_": safer_getattr,
        "_getitem_": lambda obj, key: obj[key],
        "_getiter_": iter,
        "_write_": full_write_guard,
        "_inplacevar_": _inplacevar,
    }


def _execute(entry: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
    """
    Run expert_main in a sandboxed namespace.

    Uses RestrictedPython when available (blocks dunder-escape at compile time).
    Falls back to plain exec if RestrictedPython rejects the code or is not installed.
    """
    code = entry["code"]
    t0 = time.monotonic()
    try:
        compiled, sandboxed = _compile_expert_code(code)
        namespace: dict[str, Any] = {}
        g = _build_restricted_globals() if sandboxed else {}
        exec(compiled, g, namespace)  # noqa: S102
        fn = namespace.get(EXPERT_FUNCTION)
        if fn is None:
            return {"error": "expert_main not found after exec — check indentation"}
        output = fn(input_data)
        elapsed = round(time.monotonic() - t0, 3)
        result: dict[str, Any] = {"output": output, "elapsed": elapsed}
        if not sandboxed:
            result["sandbox"] = "plain"  # RP not used — caller may choose to log
        return result
    except Exception:
        elapsed = round(time.monotonic() - t0, 3)
        return {"error": traceback.format_exc(), "elapsed": elapsed}


def rollback(name: str) -> dict[str, Any]:
    """
    Restore previous version of an expert (one level of undo).

    Raises:
        KeyError if expert not found.
        ValueError if no previous version stored.
    """
    with _locked():
        registry = _load()
        if name not in registry:
            raise KeyError(f"Expert '{name}' not found")
        entry = registry[name]
        prev_code = entry.get("prev_code")
        if not prev_code:
            raise ValueError(f"No previous version for expert '{name}'")
        # Swap current ↔ prev
        entry["code"], entry["prev_code"] = prev_code, entry["code"]
        entry["version"], entry["prev_version"] = (
            entry.get("prev_version", "?"),
            entry.get("version"),
        )
        entry["updated_at"] = datetime.now(UTC).isoformat()
        registry[name] = entry
        _save(registry)
        result: dict[str, Any] = entry
    return result


def test_expert(name: str) -> dict[str, Any]:
    """
    Run all test_cases for an expert. Returns results summary.

    Returns:
        {"passed": int, "failed": int, "errors": list[str]}
    """
    registry = _load()
    if name not in registry:
        return {"passed": 0, "failed": 0, "errors": [f"Expert '{name}' not found"]}
    entry = registry[name]
    cases = entry.get("test_cases") or []
    if not cases:
        return {"passed": 0, "failed": 0, "errors": [], "note": "no test_cases defined"}

    passed, failed, errors = 0, 0, []
    for i, tc in enumerate(cases):
        r = _execute(entry, tc["input"])
        if "error" in r:
            failed += 1
            errors.append(f"[{i}] runtime error: {r['error'][:100]}")
        elif "expected" in tc and r.get("output") != tc["expected"]:
            failed += 1
            errors.append(f"[{i}] expected {tc['expected']!r}, got {r.get('output')!r}")
        else:
            passed += 1

    return {"passed": passed, "failed": failed, "errors": errors}


def search_experts(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """
    Full-text search over name + description + test_cases.

    Uses BM25 (bm25s) when available; falls back to substring match.
    Install: pip install bm25s
    """
    registry = _load()
    if not registry:
        return []
    entries = list(registry.values())

    try:
        import bm25s  # noqa: PLC0415

        corpus = [
            f"{e['name']} {e.get('description', '')} "
            f"{' '.join(str(tc.get('input', '')) for tc in e.get('test_cases', []))}"
            for e in entries
        ]
        retriever = bm25s.BM25()
        retriever.index(bm25s.tokenize(corpus, stopwords="en"))
        results, _ = retriever.retrieve(bm25s.tokenize([query]), k=min(top_k, len(corpus)))
        return [entries[i] for i in results[0]]
    except ImportError:
        q = query.lower()
        matched = [
            e
            for e in entries
            if q in e.get("name", "").lower() or q in e.get("description", "").lower()
        ]
        return matched[:top_k]


def lookup(name: str) -> dict[str, Any] | None:
    """Return expert entry by name, or None."""
    return _load().get(name)


def list_all() -> list[dict[str, Any]]:
    """All experts sorted by run_count desc (most-used first)."""
    return sorted(_load().values(), key=lambda e: e.get("run_count", 0), reverse=True)


def delete(name: str) -> bool:
    """Remove an expert from registry. Returns True if existed."""
    with _locked():
        registry = _load()
        if name not in registry:
            return False
        del registry[name]
        _save(registry)
    return True


# ── Formatting ────────────────────────────────────────────────────────────────


def format_summary(entry: dict[str, Any]) -> str:
    """One-line summary for display."""
    runs = entry.get("run_count", 0)
    updated = (entry.get("updated_at") or "?")[:10]
    tags = ", ".join(entry.get("tags", [])) or "—"
    ok = "⚠️" if entry.get("last_error") else "✅"
    desc = entry.get("description", "")
    return f"{ok} [{entry['name']}] {desc} | runs={runs} tags={tags} updated={updated}"


def format_detail(entry: dict[str, Any]) -> str:
    """Full detail block for a single expert."""
    version = entry.get("version", "—")
    prev_version = entry.get("prev_version")
    version_str = f"{version}" + (f" (prev: {prev_version})" if prev_version else "")
    lines = [
        f"## Expert: {entry['name']} v{version_str}",
        f"Description: {entry.get('description', '—')}",
        f"Tags: {', '.join(entry.get('tags', []))}",
        f"Input schema: {entry.get('input_schema', '—')}",
        f"Side effects: {entry.get('side_effects', False)}",
        f"Compiled: {(entry.get('compiled_at') or '?')[:10]}",
        f"Updated:  {(entry.get('updated_at') or '?')[:10]}",
        f"Runs: {entry.get('run_count', 0)}",
        f"Last run: {(entry.get('last_run') or 'never')}",
    ]
    if entry.get("last_error"):
        lines.append(f"Last error: {entry['last_error'][:200]}")
    cases = entry.get("test_cases") or []
    if cases:
        lines.append(f"Test cases: {len(cases)} defined")
        for i, tc in enumerate(cases[:3]):  # show first 3
            lines.append(f"  [{i}] input={tc.get('input')} expected={tc.get('expected', '?')}")
    if entry.get("test_input"):
        lines.append(f"Smoke input: {entry['test_input']}")
    if entry.get("test_output_preview"):
        lines.append(f"Smoke output: {entry['test_output_preview']}")
    lines += ["", "```python", entry.get("code", ""), "```"]
    return "\n".join(lines)
