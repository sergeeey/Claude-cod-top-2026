#!/bin/bash
# Smoke tests for install.sh
# Usage: bash tests/test_install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0
FAIL=0

green() { echo -e "\033[0;32m  PASS\033[0m $1"; PASS=$((PASS + 1)); }
red()   { echo -e "\033[0;31m  FAIL\033[0m $1"; FAIL=$((FAIL + 1)); }

echo "=== install.sh smoke tests ==="
echo ""

# Test 1: install.sh exists and is executable-compatible
if [ -f "$SCRIPT_DIR/install.sh" ]; then
    green "install.sh exists"
else
    red "install.sh not found"
fi

# Test 2: --help works
if bash "$SCRIPT_DIR/install.sh" --help 2>/dev/null | grep -q "Usage:"; then
    green "--help prints usage"
else
    red "--help does not print usage"
fi

# Test 3: All 3 profiles mentioned in help
HELP=$(bash "$SCRIPT_DIR/install.sh" --help 2>/dev/null)
for profile in minimal standard full; do
    if echo "$HELP" | grep -q "$profile"; then
        green "--help mentions '$profile' profile"
    else
        red "--help missing '$profile' profile"
    fi
done

# Test 4: --link mentioned in help
if echo "$HELP" | grep -q "\-\-link"; then
    green "--help mentions --link"
else
    red "--help missing --link"
fi

# Test 5: Source files exist for minimal profile
for f in claude-md/CLAUDE.md rules/integrity.md rules/security.md; do
    if [ -f "$SCRIPT_DIR/$f" ]; then
        green "Source file exists: $f"
    else
        red "Source file missing: $f"
    fi
done

# Test 6: Install to tmpdir (minimal, copy mode)
TMPDIR_TEST=$(mktemp -d)
export HOME="$TMPDIR_TEST"
echo "1" | bash "$SCRIPT_DIR/install.sh" 2>/dev/null >/dev/null || true

if [ -f "$TMPDIR_TEST/.claude/CLAUDE.md" ]; then
    green "Minimal install creates CLAUDE.md"
else
    red "Minimal install did not create CLAUDE.md"
fi

if [ -f "$TMPDIR_TEST/.claude/rules/integrity.md" ]; then
    green "Minimal install creates rules/integrity.md"
else
    red "Minimal install did not create rules/integrity.md"
fi

rm -rf "$TMPDIR_TEST"

# Test 7: Install to tmpdir (standard, copy mode)
TMPDIR_TEST=$(mktemp -d)
export HOME="$TMPDIR_TEST"
echo "2" | bash "$SCRIPT_DIR/install.sh" 2>/dev/null >/dev/null || true

if [ -d "$TMPDIR_TEST/.claude/hooks" ]; then
    green "Standard install creates hooks/"
else
    red "Standard install did not create hooks/"
fi

if [ -d "$TMPDIR_TEST/.claude/skills" ] || [ -L "$TMPDIR_TEST/.claude/skills" ]; then
    green "Standard install creates skills/"
else
    red "Standard install did not create skills/"
fi

rm -rf "$TMPDIR_TEST"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
exit $FAIL
