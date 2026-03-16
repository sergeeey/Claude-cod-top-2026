---
name: reference-registry
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-17]
  Systematic external reference lookup. Reads project references.md,
  suggests relevant URLs for current task, fetches on demand.
  Triggers: reference, check external, how others solve, compare with,
  look up, competitor, alternative implementation, benchmark.
---

# Skill: Reference Registry

## When to Load
- User mentions "check how X does it", "compare with", "look up"
- Task involves design decisions that benefit from external examples
- User explicitly says "check references" or "what do our refs say"

## How It Works

Each project can have a `references.md` file in `.claude/memory/` with
structured external links. This skill teaches Claude to use them systematically.

## Workflow

### 1. Check if references exist
```
Read .claude/memory/references.md (project-level)
  OR ~/.claude/memory/references.md (global)
```

### 2. Match current task to reference entries
Each entry has a `WHEN:` field — match it against the current task context.

### 3. Fetch only what's needed
Use WebFetch with a specific `LOOK FOR:` prompt from the entry.
Do NOT fetch entire repos — fetch specific files/sections.

### 4. Report with evidence markers
```
[EXTERNAL-REF] From <source>: <finding>
[EXTERNAL-DIFF] Our approach differs: <comparison>
```

## references.md Format

```markdown
# External References

## Category Name

- [Short Name](https://url/to/specific/file)
  WHEN: <conditions when this reference is relevant>
  LOOK FOR: <what to extract from the URL>
  NOTES: <optional context, caveats, last verified date>
```

### Example

```markdown
## Architecture Patterns

- [Circuit Breaker in Polly](https://github.com/App-vNext/Polly/blob/main/src/Polly.Core/CircuitBreaker/README.md)
  WHEN: modifying circuit breaker logic, adding new states
  LOOK FOR: state transition rules, half-open behavior, success threshold
  NOTES: .NET implementation but patterns are universal

## Competitor Configs

- [Trail of Bits Claude Config](https://github.com/trailofbits/are-we-right)
  WHEN: comparing security approaches, hook architecture
  LOOK FOR: how they handle prompt injection, what hooks they use
  NOTES: Security-focused team, good baseline for comparison
```

## Rules

1. **Never fetch without purpose** — always have a LOOK FOR goal
2. **Cache mentally** — if you fetched a URL this session, don't re-fetch
3. **Prefer specific files** over repo roots (`.../blob/main/src/X.py` > `.../tree/main`)
4. **Mark findings** with [EXTERNAL-REF] so user knows the source
5. **Don't assume freshness** — URLs may be outdated. Note last verified date if available

## Anti-Patterns

| Don't | Why | Do Instead |
|-------|-----|-----------|
| Fetch entire repos | Wastes tokens, imprecise | Fetch specific files |
| Memorize URL content | Content changes | Re-fetch when needed |
| Trust without verification | External code may have bugs | Cross-check with our tests |
| Fetch on every task | Most tasks don't need refs | Only when WHEN matches |
