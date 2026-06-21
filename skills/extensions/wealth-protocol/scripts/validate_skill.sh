#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.claude/skills/wealth-protocol}"

required_files=(
  "SKILL.md"
  "README.md"
  "intake-template.md"
  "scoring-rubric.md"
  "validation-playbook.md"
  "output-templates.md"
  "golden-cases.md"
  "red-team-cases.md"
  "best-practices-audit.md"
  "hooks.md"
  "subagents.md"
  "prompt-delta.md"
  "goal.md"
)

for f in "${required_files[@]}"; do
  if [[ ! -f "$ROOT/$f" ]]; then
    echo "Missing required file: $ROOT/$f"
    exit 1
  fi
done

if [[ ! -f "$ROOT/scripts/validate_skill.sh" ]]; then
  echo "Missing required file: $ROOT/scripts/validate_skill.sh"
  exit 1
fi

grep -qi "not financial advice" "$ROOT/SKILL.md"
grep -qi "guarantee" "$ROOT/SKILL.md"
grep -qi "hypothesis" "$ROOT/SKILL.md"
grep -qi "kill criterion" "$ROOT/SKILL.md"
grep -qi "excavate" "$ROOT/SKILL.md"
grep -qi "audit" "$ROOT/SKILL.md"
grep -qi "productize" "$ROOT/SKILL.md"
grep -qi "escape" "$ROOT/SKILL.md"
grep -qi "full" "$ROOT/SKILL.md"
grep -qi "validate" "$ROOT/SKILL.md"

golden_count=$(grep -c '^## Case ' "$ROOT/golden-cases.md" || true)
red_count=$(grep -c '^## Attack ' "$ROOT/red-team-cases.md" || true)

if [[ "$golden_count" -lt 8 ]]; then
  echo "Expected at least 8 golden cases, found $golden_count"
  exit 1
fi

if [[ "$red_count" -lt 10 ]]; then
  echo "Expected at least 10 red-team attacks, found $red_count"
  exit 1
fi

echo "WEALTH_PROTOCOL_SKILL_VALIDATION: PASS"
echo "Files checked: ${#required_files[@]} + scripts/validate_skill.sh"
echo "Golden cases: $golden_count"
echo "Red-team attacks: $red_count"
