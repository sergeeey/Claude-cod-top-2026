---
id: TC-003
name: TDD Test-First Order
category: testing-discipline
severity: high
---

## Input
Add email validation function with tests to utils.py

## Expected
- assertion: first_edit_matches
  pattern: "test_*.py|*_test.py|*spec*"
  description: "First Write/Edit should target a test file, not implementation"
- assertion: contains_any
  values: ["test", "assert", "RED", "failing test"]

## Rationale
TDD order (Red → Green → Refactor) — если Claude пишет реализацию
до тестов, tdd-workflow skill не загрузился или проигнорирован.
Проверяется порядок файловых операций.
