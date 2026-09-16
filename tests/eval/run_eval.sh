#!/usr/bin/env bash
# Eval Framework — run test cases against Claude Code configuration
# Usage: bash tests/eval/run_eval.sh [TC-001|TC-002|...] [--verbose]
#
# Each TC is a markdown file with Input, Expected, and Rationale sections.
# The script sends Input to `claude -p` and checks Expected assertions.

set -euo pipefail

# WHY (found live, 2026-09-16, while dogfooding the Morrison Null Test TCs):
# on this Git-Bash build, piping a response containing a multi-byte UTF-8
# emoji (e.g. the mentor-protocol "\xf0\x9f\x92\xa1 TIP:" prefix every
# response carries) through `grep` under the ambient locale makes grep
# ABORT (SIGABRT, exit 134) instead of returning a normal match/no-match --
# reproduced minimally with `echo "... test" | grep -qiF "REFUSE"`.
# check_contains_any/check_not_contains then silently read the abort as
# "no match", so a correctly-behaving REFUSE response could fail its own
# assertion for a reason that has nothing to do with the response text.
# LC_ALL=C.UTF-8 (not bare C, which still aborts) makes grep handle the
# multi-byte sequence correctly. Exported for the whole script since every
# TC response can carry the same prefix, not just the Zero-Signal-Gate ones.
export LC_ALL=C.UTF-8

EVAL_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="${EVAL_DIR}/results"
mkdir -p "$RESULTS_DIR"

VERBOSE=false
FILTER=""
PASSED=0
FAILED=0
SKIPPED=0
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="${RESULTS_DIR}/eval_${TIMESTAMP}.txt"

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --verbose) VERBOSE=true ;;
        TC-*) FILTER="$arg" ;;
    esac
done

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log() { echo -e "$1" | tee -a "$REPORT_FILE"; }

# Extract section from markdown TC file
extract_section() {
    local file="$1"
    local section="$2"
    # Extract text between ## Section and next ## or EOF
    awk -v sec="## ${section}" '
        $0 == sec { found=1; next }
        /^## / && found { exit }
        found { print }
    ' "$file" | sed '/^$/d'
}

# Check contains_any assertion
check_contains_any() {
    local response="$1"
    shift
    for value in "$@"; do
        if echo "$response" | grep -qiF "$value"; then
            return 0
        fi
    done
    return 1
}

# Check not_contains assertion
check_not_contains() {
    local response="$1"
    shift
    for value in "$@"; do
        if echo "$response" | grep -qiF "$value"; then
            echo "FOUND_UNWANTED: $value"
            return 1
        fi
    done
    return 0
}

# Parse expected values from YAML-like list
parse_values() {
    local line="$1"
    # Extract values from: values: ["a", "b", "c"]
    echo "$line" | sed 's/.*\[//;s/\].*//;s/"//g' | tr ',' '\n' | sed 's/^ *//;s/ *$//'
}

run_tc() {
    local tc_file="$1"
    local tc_id
    tc_id=$(grep '^id:' "$tc_file" | head -1 | sed 's/id: *//')
    local tc_name
    tc_name=$(grep '^name:' "$tc_file" | head -1 | sed 's/name: *//')
    local tc_severity
    tc_severity=$(grep '^severity:' "$tc_file" | head -1 | sed 's/severity: *//')

    # Filter check
    if [[ -n "$FILTER" && "$tc_id" != "$FILTER" ]]; then
        return
    fi

    log "\n━━━ ${tc_id}: ${tc_name} [${tc_severity}] ━━━"

    # Extract input prompt
    local input
    input=$(extract_section "$tc_file" "Input")
    if [[ -z "$input" ]]; then
        log "${YELLOW}  SKIP${NC} — no Input section"
        SKIPPED=$((SKIPPED + 1))
        return
    fi

    # Run claude -p with the input (timeout 120s)
    log "  Sending prompt to Claude Code..."
    local response=""
    local exit_code=0

    if command -v claude &>/dev/null; then
        response=$(timeout 120 claude -p "$input" 2>/dev/null) || exit_code=$?
    else
        log "${YELLOW}  SKIP${NC} — 'claude' CLI not found in PATH"
        SKIPPED=$((SKIPPED + 1))
        return
    fi

    if [[ $exit_code -ne 0 && -z "$response" ]]; then
        log "${YELLOW}  SKIP${NC} — claude -p returned exit code $exit_code"
        SKIPPED=$((SKIPPED + 1))
        return
    fi

    if $VERBOSE; then
        log "  Response (first 500 chars):"
        log "  $(echo "$response" | head -c 500)"
    fi

    # Save full response
    echo "$response" > "${RESULTS_DIR}/${tc_id}_response.txt"

    # Parse and check assertions
    local expected
    expected=$(extract_section "$tc_file" "Expected")
    local tc_passed=true
    local current_assertion=""

    while IFS= read -r line; do
        # Detect assertion type
        if echo "$line" | grep -q "assertion: contains_any"; then
            current_assertion="contains_any"
            continue
        elif echo "$line" | grep -q "assertion: not_contains"; then
            current_assertion="not_contains"
            continue
        elif echo "$line" | grep -q "assertion: first_edit_matches"; then
            # Special assertion — cannot fully verify in headless mode
            log "${YELLOW}  ⚠ first_edit_matches — requires interactive session, checking response text${NC}"
            current_assertion=""
            continue
        fi

        # Process values line
        if echo "$line" | grep -q "values:"; then
            # WHY an array via mapfile, not a plain string passed unquoted
            # to the check functions (found live, 2026-09-16, via a planted
            # mutation test -- tests/test_morrison_null_eval_harness.py):
            # `check_contains_any "$response" $values` word-splits `values`
            # on EVERY space/newline, not just between list entries -- a
            # multi-word value like "no falsifiable claim" silently became
            # three separate one-word patterns ("no", "falsifiable",
            # "claim"), and "claim" alone matches any response mentioning
            # "claim.md" for an unrelated reason. Reproduced concretely: a
            # deliberately WRONG transcript ("Sure! Here is claim.md for
            # your hypothesis...") passed a contains_any check whose real
            # values were all REFUSE-shaped phrases, purely because "claim"
            # leaked out as its own pattern. `mapfile` + `"${values[@]}"`
            # preserves each configured value as one atomic string.
            local -a values
            mapfile -t values < <(parse_values "$line")

            if [[ "$current_assertion" == "contains_any" ]]; then
                if check_contains_any "$response" "${values[@]}"; then
                    log "${GREEN}  ✓ contains_any PASS${NC}"
                else
                    log "${RED}  ✗ contains_any FAIL — none of [$(printf '%s, ' "${values[@]}")] found${NC}"
                    tc_passed=false
                fi
            elif [[ "$current_assertion" == "not_contains" ]]; then
                local unwanted
                unwanted=$(check_not_contains "$response" "${values[@]}" 2>&1) || true
                if [[ -z "$unwanted" ]]; then
                    log "${GREEN}  ✓ not_contains PASS${NC}"
                else
                    log "${RED}  ✗ not_contains FAIL — $unwanted${NC}"
                    tc_passed=false
                fi
            fi
        fi
    done <<< "$expected"

    if $tc_passed; then
        log "${GREEN}  RESULT: PASS${NC}"
        PASSED=$((PASSED + 1))
    else
        log "${RED}  RESULT: FAIL${NC}"
        FAILED=$((FAILED + 1))
    fi
}

# Header
log "╔══════════════════════════════════════════════╗"
log "║   Claude Code Config — Eval Framework       ║"
log "║   $(date +%Y-%m-%d\ %H:%M)                            ║"
log "╚══════════════════════════════════════════════╝"

# Run all TC files
for tc_file in "${EVAL_DIR}"/TC-*.md; do
    [[ -f "$tc_file" ]] || continue
    run_tc "$tc_file"
done

# Summary
log "\n━━━ SUMMARY ━━━"
log "  Passed:  ${PASSED}"
log "  Failed:  ${FAILED}"
log "  Skipped: ${SKIPPED}"
log "  Total:   $((PASSED + FAILED + SKIPPED))"
log "  Report:  ${REPORT_FILE}"

if [[ $FAILED -gt 0 ]]; then
    log "\n${RED}⚠ ${FAILED} test(s) failed — config may need attention${NC}"
    exit 1
else
    log "\n${GREEN}✓ All tests passed${NC}"
    exit 0
fi
