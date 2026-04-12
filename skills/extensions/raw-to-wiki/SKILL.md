---
name: raw-to-wiki
description: >
  USE when capturing learnings, retrospectives, or quick notes for persistence.
  ALWAYS drop .md files into ~/.claude/memory/raw/ — auto-converts to wiki entries.
  Triggers: raw note, capture, inbox, quick note, wiki, raw to wiki.
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-04-09]
effort: minimal
tokens: ~200
---

# Raw → Wiki Pipeline

## Concept

**Raw folder** = capture inbox. Low friction. Dump thoughts, links, snippets — no structure required.

**Wiki folder** = structured knowledge base. Auto-generated from raw notes at session end.

**session_save.py** = conveyor belt. Runs automatically on `Stop` hook.

## How to Use

### Capture (during session)

Create any `.md` file in `~/.claude/memory/raw/`:

```bash
# Quick note
echo "# Idea: add retry logic to MCP calls\n\nSee circuit breaker pattern. #architecture #mcp" \
  > ~/.claude/memory/raw/mcp-retry-idea.md

# Or ask Claude to write it
# "save this to raw notes: ..."
```

Tags `#tag` in the file become wiki metadata. Tag `#raw` is stripped automatically.

### Processing (automatic)

At session end (`Stop` event), `session_save.py` runs:

1. Finds all `.md` files in `~/.claude/memory/raw/`
2. Converts each → structured wiki entry in `~/.claude/memory/wiki/`
3. Moves original to `~/.claude/memory/raw/processed/` (audit trail)
4. Prints: `[session-save] Raw→Wiki: N note(s) processed`

### Wiki entry format

```markdown
# Idea: add retry logic to MCP calls

**Date:** 2026-04-09
**Source:** raw/mcp-retry-idea.md
**Tags:** architecture, mcp

---

See circuit breaker pattern. #architecture #mcp
```

## Directory Structure

```
~/.claude/memory/
├── raw/                    ← drop notes here
│   ├── my-note.md
│   └── processed/          ← auto-moved after processing
│       └── my-note.md
└── wiki/                   ← structured output
    └── 2026-04-09_my_note.md
```

## Manual Trigger

To process raw notes immediately (without waiting for session end):

```python
cd <project>
python -c "
from pathlib import Path
from hooks.session_save import process_raw_to_wiki
n = process_raw_to_wiki(
    Path.home() / '.claude/memory/raw',
    Path.home() / '.claude/memory/wiki'
)
print(f'{n} notes processed')
"
```

## Gotchas

- Files without `#raw` tag are still processed — location in `raw/` is enough signal
- Existing wiki file on same day → gets `_2`, `_3` suffix (no overwrites)
- Processed originals kept in `raw/processed/` forever — delete manually if needed
- Hook runs fail-open: one bad file doesn't stop others
