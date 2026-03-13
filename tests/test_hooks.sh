#!/bin/bash
# Smoke tests for hooks
# Usage: bash tests/test_hooks.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS_DIR="$SCRIPT_DIR/hooks"
PASS=0
FAIL=0

green() { echo -e "\033[0;32m  PASS\033[0m $1"; PASS=$((PASS + 1)); }
red()   { echo -e "\033[0;31m  FAIL\033[0m $1"; FAIL=$((FAIL + 1)); }

echo "=== Hooks smoke tests ==="
echo ""

# Test 1: hooks directory exists
if [ -d "$HOOKS_DIR" ]; then
    green "hooks/ directory exists"
else
    red "hooks/ directory missing"
    exit 1
fi

# Test 2: settings.json exists and is valid JSON
if [ -f "$HOOKS_DIR/settings.json" ]; then
    green "settings.json exists"
else
    red "settings.json missing"
fi

PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
fi

if [ -n "$PYTHON_CMD" ]; then
    if $PYTHON_CMD -c "import json, sys, pathlib; json.loads(pathlib.Path(sys.argv[1]).read_text())" "$HOOKS_DIR/settings.json" 2>/dev/null; then
        green "settings.json is valid JSON"
    else
        red "settings.json is invalid JSON"
    fi
else
    red "Python not found — cannot validate JSON"
fi

# Test 3: All Python hooks have valid syntax
HOOK_COUNT=0
for hook in "$HOOKS_DIR"/*.py; do
    [ -f "$hook" ] || continue
    HOOK_COUNT=$((HOOK_COUNT + 1))
    bname=$(basename "$hook")
    if [ -n "$PYTHON_CMD" ]; then
        if $PYTHON_CMD -c "import py_compile, sys; py_compile.compile(sys.argv[1], doraise=True)" "$hook" 2>/dev/null; then
            green "$bname — valid Python syntax"
        else
            red "$bname — syntax error"
        fi
    else
        green "$bname — skipped (no Python)"
    fi
done

if [ "$HOOK_COUNT" -ge 5 ]; then
    green "Found $HOOK_COUNT hook scripts (expected 5+)"
else
    red "Found only $HOOK_COUNT hook scripts (expected 5+)"
fi

# Test 4: Critical hooks exist
for hook in session_start.py pre_commit_guard.py read_before_edit.py mcp_locality_guard.py; do
    if [ -f "$HOOKS_DIR/$hook" ]; then
        green "Critical hook exists: $hook"
    else
        red "Critical hook missing: $hook"
    fi
done

# Test 5: No external imports in hooks (stdlib only)
for hook in "$HOOKS_DIR"/*.py; do
    [ -f "$hook" ] || continue
    basename=$(basename "$hook")
    # Check for non-stdlib imports (rough check: anything not in standard lib)
    if grep -E "^(import|from) (requests|httpx|aiohttp|flask|django|numpy|pandas)" "$hook" >/dev/null 2>&1; then
        red "$basename — has external dependency import"
    else
        green "$basename — no external dependencies"
    fi
done

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
exit $FAIL
