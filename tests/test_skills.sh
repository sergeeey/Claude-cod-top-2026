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

# Test 1: skills directory structure
for dir in "$SKILLS_DIR/core" "$SKILLS_DIR/extensions"; do
    if [ -d "$dir" ]; then
        green "$(basename "$dir")/ directory exists"
    else
        red "$(basename "$dir")/ directory missing"
    fi
done

# Test 2: Count skills in core (expect 4+) and extensions (expect 3+)
for section in core extensions; do
    SKILL_COUNT=0
    section_dir="$SKILLS_DIR/$section"
    [ -d "$section_dir" ] || continue
    for skill_dir in "$section_dir"/*/; do
        [ -d "$skill_dir" ] || continue
        SKILL_COUNT=$((SKILL_COUNT + 1))
    done
    min=3
    [ "$section" = "core" ] && min=4
    if [ "$SKILL_COUNT" -ge "$min" ]; then
        green "$section: $SKILL_COUNT skills (expected ${min}+)"
    else
        red "$section: only $SKILL_COUNT skills (expected ${min}+)"
    fi
done

# Test 3-5: Validate SKILL.md in both core and extensions
for section in core extensions; do
    section_dir="$SKILLS_DIR/$section"
    [ -d "$section_dir" ] || continue

    for skill_dir in "$section_dir"/*/; do
        [ -d "$skill_dir" ] || continue
        skill_name=$(basename "$skill_dir")
        skill_file="$skill_dir/SKILL.md"

        # Test 3: Every skill has SKILL.md
        if [ -f "$skill_file" ]; then
            green "$section/$skill_name — has SKILL.md"
        else
            red "$section/$skill_name — missing SKILL.md"
            continue
        fi

        # Test 4: YAML frontmatter with required fields
        if head -1 "$skill_file" | grep -q "^---"; then
            green "$section/$skill_name — has YAML frontmatter"
        else
            red "$section/$skill_name — missing YAML frontmatter"
            continue
        fi

        if grep -q "^name:" "$skill_file"; then
            green "$section/$skill_name — has 'name' field"
        else
            red "$section/$skill_name — missing 'name' field"
        fi

        if grep -q "^description:" "$skill_file"; then
            green "$section/$skill_name — has 'description' field"
        else
            red "$section/$skill_name — missing 'description' field"
        fi

        # Test 5: CSO compliance
        desc=$(sed -n '/^description:/,/^---/p' "$skill_file" | head -5)
        if echo "$desc" | grep -qiE "(USE when|MUST|ALWAYS|Triggers:|ESPECIALLY)"; then
            green "$section/$skill_name — CSO-optimized description"
        else
            red "$section/$skill_name — description may not follow CSO format"
        fi
    done
done

# Test 6: Extension skills have plugin.json
for skill_dir in "$SKILLS_DIR/extensions"/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name=$(basename "$skill_dir")
    if [ -f "$skill_dir/plugin.json" ]; then
        green "extensions/$skill_name — has plugin.json"
    else
        red "extensions/$skill_name — missing plugin.json"
    fi
done

# Test 7: Registry exists
if [ -f "$SKILLS_DIR/registry.yaml" ]; then
    green "registry.yaml exists"
else
    red "registry.yaml missing"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
exit $FAIL
