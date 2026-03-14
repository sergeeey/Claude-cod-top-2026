# Testing Rules

## Adaptive requirements
- **MVP / prototype** → tests are NOT written. Make it work first, test later
- **Production** → pytest coverage ≥ 80% for business logic, ≥ 60% for utilities
- Pre-commit gate: `coverage report --fail-under=80` (if coverage is configured in the project)
- The transition from MVP to Production is agreed upon explicitly

## Test Protection (hard rule)
- NEVER edit or delete a test to make it pass for broken code
- A failing test → fix the CODE, not the test. A test = a behavioral specification
- Exception: a test is outdated (tests a removed feature) → delete it with an explanation of WHY
