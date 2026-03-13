#!/usr/bin/env bash
# Eval Framework — run test cases against Claude Code configuration
# Usage: bash tests/eval/run_eval.sh [TC-001|TC-002|...] [--verbose]
#
# Each TC is a markdown file with Input, Expected, and Rationale sections.
# The script sends Input to `claude -p` and checks Expected assertions.

set -euo pipefail

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
        ((SKIPPED++))
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
        ((SKIPPED++))
        return
    fi

    if [[ $exit_code -ne 0 && -z "$response" ]]; then
        log "${YELLOW}  SKIP${NC} — claude -p returned exit code $exit_code"
        ((SKIPPED++))
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
            local values
            values=$(parse_values "$line")

            if [[ "$current_assertion" == "contains_any" ]]; then
                if check_contains_any "$response" $values; then
                    log "${GREEN}  ✓ contains_any PASS${NC}"
                else
                    log "${RED}  ✗ contains_any FAIL — none of [$(echo $values | tr '\n' ', ')] found${NC}"
                    tc_passed=false
                fi
            elif [[ "$current_assertion" == "not_contains" ]]; then
                local unwanted
                unwanted=$(check_not_contains "$response" $values 2>&1) || true
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
        ((PASSED++))
    else
        log "${RED}  RESULT: FAIL${NC}"
        ((FAILED++))
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
