#!/bin/bash
# Run all smoke tests
# Usage: bash tests/test_all.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOTAL_FAIL=0

echo "╔══════════════════════════════════════╗"
echo "║   Claude Code Config — Test Suite    ║"
echo "╚══════════════════════════════════════╝"
echo ""

for test_file in "$SCRIPT_DIR"/test_*.sh; do
    [ -f "$test_file" ] || continue
    [ "$(basename "$test_file")" = "test_all.sh" ] && continue

    echo ""
    bash "$test_file" || TOTAL_FAIL=$((TOTAL_FAIL + 1))
done

echo ""
echo "══════════════════════════════════════"
if [ "$TOTAL_FAIL" -eq 0 ]; then
    echo -e "\033[0;32mAll test suites passed!\033[0m"
else
    echo -e "\033[0;31m$TOTAL_FAIL test suite(s) had failures\033[0m"
fi

exit $TOTAL_FAIL
