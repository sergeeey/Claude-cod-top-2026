---
name: obsidian-bases
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-04-12]
  Obsidian Bases — native database tables built into Obsidian 1.8+.
  Create structured views of notes using properties. No plugins needed.
  Triggers: obsidian bases, bases, database view, property table,
  structured notes, note database, obsidian table, filter notes.
effort: minimal
tokens: ~200
---

# Obsidian Bases — Native Database Views

## What It Is

Obsidian Bases (v1.8+) lets you create **database-like tables** from note properties — no Dataview plugin needed. A `.base` file defines which notes to show and how.

## Create a Base File

Create `projects.base` in your vault:

```json
{
  "filters": {
    "operator": "and",
    "conditions": [
      { "field": "tags", "operator": "contains", "value": "project" }
    ]
  },
  "columns": [
    { "field": "file.name", "label": "Project" },
    { "field": "status", "label": "Status" },
    { "field": "deadline", "label": "Due" },
    { "field": "priority", "label": "Priority" }
  ],
  "sort": [
    { "field": "deadline", "direction": "asc" }
  ],
  "groupBy": "status"
}
```

## Filter Operators

| Operator | Meaning |
|----------|---------|
| `contains` | field contains value |
| `equals` | exact match |
| `not_equals` | negation |
| `is_empty` | field missing/blank |
| `is_not_empty` | field has value |
| `greater_than` | numeric/date |
| `less_than` | numeric/date |

Combine with `"operator": "and"` or `"operator": "or"`.

## Column Field Types

```json
{ "field": "file.name" }       // note title (link)
{ "field": "file.ctime" }      // created time
{ "field": "file.mtime" }      // modified time
{ "field": "file.path" }       // vault path
{ "field": "tags" }            // tags array
{ "field": "status" }          // any frontmatter key
```

## Inline Editing

Click any cell in the Bases view to edit the underlying frontmatter property directly — no need to open the note.

## Recipes

**Active projects dashboard:**
```json
{
  "filters": { "operator": "and", "conditions": [
    { "field": "status", "operator": "not_equals", "value": "done" },
    { "field": "tags", "operator": "contains", "value": "project" }
  ]},
  "sort": [{ "field": "priority", "direction": "desc" }]
}
```

**Weekly review — notes modified this week:**
```json
{
  "filters": { "operator": "and", "conditions": [
    { "field": "file.mtime", "operator": "greater_than", "value": "{{now - 7d}}" }
  ]}
}
```

## Tips
- `.base` files open as table views in Obsidian
- Properties defined in frontmatter become filterable columns automatically
- Combine with Templater to auto-fill properties on note creation
- Bases ≠ Dataview: Bases is native, faster, but less expressive
