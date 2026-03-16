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
├── core/                      ← installed by default (universal)
│   ├── routing-policy/
│   ├── brainstorming/
│   ├── tdd-workflow/
│   ├── git-worktrees/
│   ├── mentor-mode/
│   └── mcp-installer.md
│
├── extensions/                ← installed on demand (domain-specific)
│   ├── security-audit/        [finance]
│   ├── archcode-genomics/     [science]
│   ├── geoscan/               [science]
│   ├── notebooklm/            [productivity]
│   ├── suno-music/            [creative]
│   └── python-geodata.md      [science]
│
├── registry.yaml              ← central index of all skills
│
└── my-skill/                  ← standard skill layout
    ├── SKILL.md               # Main instructions (required)
    ├── references/            # Reference materials (optional)
    │   └── api_docs.md
    └── scripts/               # Utilities (optional)
        └── helper.py
```

## Core vs Extensions

**Core skills** are universal and installed automatically with standard/full profiles.
Any developer benefits from these regardless of domain.

**Extension skills** are domain-specific. During installation, users pick which
extensions to install. Extensions can also be managed after installation:

```bash
bash skill-manager.sh list              # show installed + available
bash skill-manager.sh search finance    # search by keyword
bash skill-manager.sh install notebooklm
bash skill-manager.sh remove suno-music
```

## Core Skills

### routing-policy
Task→skill→agent routing matrix. Determines optimal execution path.

### brainstorming
Socratic Design — 2-3 alternatives with trade-offs.
Hard gate: "design approved" before writing code.

### tdd-workflow
Test-Driven Development. RED→GREEN→REFACTOR cycle.

### git-worktrees
Isolated working copies for experiments and parallel work.

### mentor-mode
Extended pedagogical mode with analogies.

### mcp-installer
Step-by-step MCP server installation guide.

## Extension Skills

### security-audit `[finance]`
Security audit for financial applications. ARRFR compliance, IIN, fraud detection.

### archcode-genomics `[science]`
Chromatin extrusion simulation for variant pathogenicity analysis.
30318 ClinVar variants, 9 validated loci.

### geoscan `[science]`
Satellite gold prospecting. Sentinel-2 spectral indices, Isolation Forest.
AUC=0.85, Phase B complete.

### notebooklm `[productivity]`
Query Google NotebookLM notebooks. Browser automation, persistent auth.

### suno-music `[creative]`
Suno AI prompt engineering for EDM, hardstyle, hyperpop, rap-drill.

### python-geodata `[science]`
Python geospatial data processing patterns.

## How to Create a New Skill

1. Create directory: `skills/extensions/my-skill/` (or `skills/core/` if universal)
2. Create `SKILL.md` with YAML frontmatter
3. Set STATUS: draft, CONFIDENCE: low
4. Add entry to `skills/registry.yaml`
5. Test: verify that triggers fire
6. Update STATUS: confirmed after successful testing
