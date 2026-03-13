#!/bin/bash
# Smoke tests for skills
# Usage: bash tests/test_skills.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS_DIR="$SCRIPT_DIR/skills"
PASS=0
FAIL=0

green() { echo -e "\033[0;32m  PASS\033[0m $1"; PASS=$((PASS + 1)); }
red()   { echo -e "\033[0;31m  FAIL\033[0m $1"; FAIL=$((FAIL + 1)); }

echo "=== Skills smoke tests ==="
echo ""

# Test 1: skills directory exists
if [ -d "$SKILLS_DIR" ]; then
    green "skills/ directory exists"
else
    red "skills/ directory missing"
    exit 1
fi

# Test 2: Count skills (expect 5+)
SKILL_COUNT=0
for skill_dir in "$SKILLS_DIR"/*/; do
    [ -d "$skill_dir" ] || continue
    SKILL_COUNT=$((SKILL_COUNT + 1))
done

if [ "$SKILL_COUNT" -ge 5 ]; then
    green "Found $SKILL_COUNT skills (expected 5+)"
else
    red "Found only $SKILL_COUNT skills (expected 5+)"
fi

# Test 3: Every skill has SKILL.md
for skill_dir in "$SKILLS_DIR"/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name=$(basename "$skill_dir")
    if [ -f "$skill_dir/SKILL.md" ]; then
        green "$skill_name/ has SKILL.md"
    else
        red "$skill_name/ missing SKILL.md"
    fi
done

# Test 4: Every SKILL.md has YAML frontmatter with required fields
for skill_dir in "$SKILLS_DIR"/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name=$(basename "$skill_dir")
    skill_file="$skill_dir/SKILL.md"
    [ -f "$skill_file" ] || continue

    # Check frontmatter exists (starts with ---)
    if head -1 "$skill_file" | grep -q "^---"; then
        green "$skill_name — has YAML frontmatter"
    else
        red "$skill_name — missing YAML frontmatter"
        continue
    fi

    # Check 'name:' field
    if grep -q "^name:" "$skill_file"; then
        green "$skill_name — has 'name' field"
    else
        red "$skill_name — missing 'name' field"
    fi

    # Check 'description:' field
    if grep -q "^description:" "$skill_file"; then
        green "$skill_name — has 'description' field"
    else
        red "$skill_name — missing 'description' field"
    fi
done

# Test 5: CSO compliance — descriptions should contain trigger words
for skill_dir in "$SKILLS_DIR"/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name=$(basename "$skill_dir")
    skill_file="$skill_dir/SKILL.md"
    [ -f "$skill_file" ] || continue

    # Extract description block (between first --- and second ---)
    desc=$(sed -n '/^description:/,/^---/p' "$skill_file" | head -5)
    if echo "$desc" | grep -qiE "(USE when|MUST|ALWAYS|Triggers:|ESPECIALLY)"; then
        green "$skill_name — CSO-optimized description"
    else
        red "$skill_name — description may not follow CSO format"
    fi
done

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
exit $FAIL
