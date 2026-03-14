# Skills Guide

## What are Skills

Skills are the Progressive Disclosure mechanism in Claude Code.
At startup only `name` + `description` are loaded (~100 tokens for all skills).
The full SKILL.md is read only when a trigger word fires.

## SKILL.md Format

```yaml
---
name: my-skill
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-12]
  Skill description in 1-2 sentences.
  Triggers: keyword1, keyword2, keyword3.
---

# Skill Title

## When to Load
(activation conditions)

## Instructions
(specific actions)

## Anti-Patterns
(what NOT to do)
```

## YAML Frontmatter

### Required Fields
- `name` — unique name (max 64 characters)
- `description` — description + triggers (max 1024 characters)

### Lifecycle Markers (in description)
- `STATUS`: draft → confirmed → review → deprecated
- `CONFIDENCE`: low → medium → high
- `VALIDATED`: date of last verification

## CSO — Claude Search Optimization

**Critically important**: description must start with activation conditions ("Use when..."),
NOT with a workflow description.

Bad: "Step-by-step code review process with 2-stage verification..."
Good: "[STATUS: confirmed] Code review for financial applications. Triggers: audit, review, security."

**Why**: if description describes the workflow, Claude follows the description and skips SKILL.md.

## Lifecycle

1. **draft** — new skill, not tested
2. **confirmed** — tested, works stably
3. **review** — unused for 2+ months, requires verification
4. **deprecated** — outdated, scheduled for removal

Recommendation: check skills once a week, update VALIDATED for current ones.

## Directory Structure

```
skills/
└── my-skill/
    ├── SKILL.md           # Main instructions (required)
    ├── references/        # Reference materials (optional)
    │   └── api_docs.md
    └── scripts/           # Utilities (optional)
        └── helper.py
```

## Our Skills

### archcode-genomics
Chromatin extrusion simulation for variant pathogenicity analysis.
30318 ClinVar variants, 9 validated loci.

### brainstorming
Socratic Design — 2-3 alternatives with trade-offs.
Hard gate: "design approved" before writing code.

### geoscan
GeoScan Gold: Sentinel-2 spectral indices, Isolation Forest, lineament detection.
AUC=0.85, Phase B complete.

### git-worktrees
Isolated working copies for experiments and parallel work.

### mentor-mode
Extended pedagogical mode with analogies from security/finance.

### notebooklm
Query Google NotebookLM notebooks. Browser automation, persistent auth.

### security-audit
Security audit for KZ financial applications. ARRFR compliance, IIN deduplication.

### suno-music
Suno AI prompt engineering for EDM, hardstyle, hyperpop, rap-drill.

## How to Create a New Skill

1. Create directory: `~/.claude/skills/my-skill/`
2. Create `SKILL.md` with YAML frontmatter
3. Set STATUS: draft, CONFIDENCE: low
4. Test: verify that triggers fire
5. Update STATUS: confirmed after successful testing
