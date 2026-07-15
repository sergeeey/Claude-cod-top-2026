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

# Test 8: --target isolation — a custom target must NOT write to the real
# (temp-simulated) ~/.claude/skills/extensions unless --sync-global-skills
# is explicitly passed. WHY: INSTALL-001 — install.sh previously synced
# extension skills to $HOME/.claude regardless of --target, silently
# breaking the isolation a --target caller relies on.
TMP_HOME_ISO=$(mktemp -d)
TMP_TARGET_ISO=$(mktemp -d)
HOME="$TMP_HOME_ISO" bash "$SCRIPT_DIR/install.sh" --profile=standard --target="$TMP_TARGET_ISO" --non-interactive 2>/dev/null >/dev/null || true

if [ -f "$TMP_TARGET_ISO/commands/evolve-solution.md" ]; then
    green "--target isolation: target dir still gets installed (evolve-solution.md)"
else
    red "--target isolation: target dir missing evolve-solution.md"
fi

if [ -f "$TMP_TARGET_ISO/scripts/redact.py" ]; then
    green "--target isolation: target dir still gets installed (redact.py)"
else
    red "--target isolation: target dir missing redact.py"
fi

if [ ! -d "$TMP_HOME_ISO/.claude/skills/extensions" ] || [ -z "$(find "$TMP_HOME_ISO/.claude/skills/extensions" -type f 2>/dev/null)" ]; then
    green "--target isolation: real ~/.claude/skills/extensions untouched"
else
    red "--target isolation: real ~/.claude/skills/extensions was written to (isolation broken)"
fi

rm -rf "$TMP_HOME_ISO" "$TMP_TARGET_ISO"

# Test 9: --target + --sync-global-skills — explicit opt-in must still work.
TMP_HOME_OPT=$(mktemp -d)
TMP_TARGET_OPT=$(mktemp -d)
HOME="$TMP_HOME_OPT" bash "$SCRIPT_DIR/install.sh" --profile=standard --target="$TMP_TARGET_OPT" --sync-global-skills --non-interactive 2>/dev/null >/dev/null || true

if [ -n "$(find "$TMP_HOME_OPT/.claude/skills/extensions" -type f 2>/dev/null)" ]; then
    green "--sync-global-skills: explicit opt-in still syncs to ~/.claude/skills/extensions"
else
    red "--sync-global-skills: explicit opt-in did not sync any files"
fi

rm -rf "$TMP_HOME_OPT" "$TMP_TARGET_OPT"

# Test 10: --non-interactive must NOT clone last30days (external, unpinned
# repo) without explicit --allow-external-skills.
# Regression (HIGH, external security audit 2026-07-07): "install ALL"
# previously included last30days unconditionally in non-interactive mode --
# a silent, unpinned `git clone` of third-party code with zero consent.
TMP_HOME_EXT=$(mktemp -d)
HOME="$TMP_HOME_EXT" bash "$SCRIPT_DIR/install.sh" --profile=standard --non-interactive 2>/dev/null >/dev/null || true

if [ ! -d "$TMP_HOME_EXT/.claude/skills/last30days" ]; then
    green "--non-interactive (no flag): last30days NOT cloned by default"
else
    red "--non-interactive (no flag): last30days was cloned without consent"
fi

rm -rf "$TMP_HOME_EXT"

# Test 11: --allow-external-skills is the explicit opt-in for the same case.
# WHY --dry-run: this only needs to prove the flag reaches install_last30days
# (via its own [dry-run] message), not perform a real network clone in CI.
TMP_HOME_EXT_OPT=$(mktemp -d)
OUTPUT_EXT_OPT=$(HOME="$TMP_HOME_EXT_OPT" bash "$SCRIPT_DIR/install.sh" --profile=standard --non-interactive --allow-external-skills --dry-run 2>&1)

if echo "$OUTPUT_EXT_OPT" | grep -q "last30days"; then
    green "--allow-external-skills: last30days reached (opt-in works)"
else
    red "--allow-external-skills: last30days not reached even with explicit opt-in"
fi

rm -rf "$TMP_HOME_EXT_OPT"

# Test 12: last30days-skill clone must be pinned to a reviewed commit SHA,
# not left tracking whatever the remote's default branch currently is.
# Regression (HIGH residual, external re-audit 2026-07-07): even after the
# opt-in fix (Test 10/11), the SAME opt-in flag could still silently pull
# DIFFERENT upstream code on every future install with zero re-review.
# WHY grep the script text, not a real clone: no network dependency, no
# CI flakiness -- this only needs to prove the pin mechanism exists at all.
if grep -q 'LAST30DAYS_PINNED_SHA=' "$SCRIPT_DIR/install.sh" \
    && grep -q 'git -C "\$target" checkout --quiet "\$LAST30DAYS_PINNED_SHA"' "$SCRIPT_DIR/install.sh"; then
    green "last30days-skill clone is pinned to a commit SHA"
else
    red "last30days-skill clone has no commit-SHA pin"
fi

# Test 13: a checkout failure against the pinned SHA must remove the clone
# (fail-closed), not silently continue installing whatever HEAD resolved to.
# Regression (F-08, external audit 2026-07-15): the previous behavior only
# printed a warning and left the unpinned, unreviewed clone in place.
# WHY a fake `git` on PATH: succeeds `clone` (creates the target dir so the
# script's own -d check passes) but fails `checkout` -- no network needed,
# deterministic in CI.
TMP_HOME_FAILCLOSED=$(mktemp -d)
FAKE_BIN=$(mktemp -d)
cat > "$FAKE_BIN/git" <<'FAKEGIT'
#!/bin/bash
case "$1" in
    clone) mkdir -p "$3"; exit 0 ;;
    -C) [ "$3" = "checkout" ] && exit 1 || exit 0 ;;
    *) exit 0 ;;
esac
FAKEGIT
chmod +x "$FAKE_BIN/git"

PATH="$FAKE_BIN:$PATH" HOME="$TMP_HOME_FAILCLOSED" bash "$SCRIPT_DIR/install.sh" \
    --profile=standard --non-interactive --allow-external-skills 2>/dev/null >/dev/null || true

if [ ! -d "$TMP_HOME_FAILCLOSED/.claude/skills/last30days" ]; then
    green "last30days: checkout failure removes clone (fail-closed)"
else
    red "last30days: checkout failure left an unpinned clone in place (fail-open regression)"
fi

rm -rf "$TMP_HOME_FAILCLOSED" "$FAKE_BIN"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
exit $FAIL
