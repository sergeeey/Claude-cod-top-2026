# Skill lifecycle tests

Checked by `scripts/skill_lifecycle_check.py` and `tests/test_skill_lifecycle_check.py`.

## What this is (and is not)

A skill is a markdown instruction file, not code. "Testing" it here means:
does its current text still contain the exact phrase a *documented past
regression* proved must survive future edits? This is a content-regression
check against a skill's own changelog, not a claim that it verifies the
skill's real-world behavior when actually invoked (that requires an actual
dogfood run — see `benchmarks/<skill>/` for that separate discipline).

**Provenance note:** the originating idea (mattpocock/skills' `lifecycle.test.js`)
was only ever analyzed via graphify's README+AST-node-degree pass — its own
test source was never fetched or read (`skills=markdown, репо не
клонировалось` per the recorded insight). This implementation is inspired by
the concept only; it does not reproduce their actual test code, which this
project has never seen.

## Fixture format

```yaml
skill: <skill name>
skill_file: <absolute path to that skill's SKILL.md — may be a personal,
  machine-local path outside this repo, same precedent as
  check_global_hooks.py hardcoding a personal path>
required_strings:
  - text: <exact substring that must exist in the file>
    why: <which past regression this guards against, and when it happened>
```

If `skill_file` does not exist on the machine running the check (e.g. CI, or
a different maintainer's machine), the fixture is SKIPPED, not failed —
absence of a personal-only file is not evidence of regression.

## Adding a new fixture

Only add a `required_strings` entry for a phrase whose *absence was a real,
previously-documented problem* (a skill's own changelog/version-history
naming a specific silently-dropped rule) — not for every sentence you'd like
to protect pre-emptively. This keeps the fixture honest as a regression
guard, not a rigid content-freeze on skills that are still actively evolving.
