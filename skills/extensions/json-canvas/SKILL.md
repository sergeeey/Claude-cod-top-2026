---
name: json-canvas
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-04-12]
  JSON Canvas — open spec for infinite canvas apps (Obsidian Canvas, Heptabase, etc.).
  Create, parse, and manipulate .canvas files programmatically.
  Triggers: canvas, json canvas, obsidian canvas, visual board, mind map,
  infinite canvas, whiteboard, node graph, .canvas file.
effort: minimal
tokens: ~200
---

# JSON Canvas — Open Specification

## What It Is

JSON Canvas is an **open file format** for infinite canvas tools. Obsidian uses `.canvas` files. The spec is at https://jsoncanvas.org — any tool can read/write it.

## File Structure

```json
{
  "nodes": [...],
  "edges": [...]
}
```

## Node Types

### Text Node
```json
{
  "id": "node1",
  "type": "text",
  "text": "# Hello\n\nMarkdown content here.",
  "x": 0, "y": 0,
  "width": 300, "height": 200,
  "color": "1"
}
```

### File Node (links to vault note)
```json
{
  "id": "node2",
  "type": "file",
  "file": "projects/my-note.md",
  "x": 400, "y": 0,
  "width": 400, "height": 300
}
```

### Link Node (web URL)
```json
{
  "id": "node3",
  "type": "link",
  "url": "https://example.com",
  "x": 0, "y": 300,
  "width": 400, "height": 200
}
```

### Group Node
```json
{
  "id": "group1",
  "type": "group",
  "label": "Sprint 1",
  "x": -50, "y": -50,
  "width": 800, "height": 600,
  "color": "5"
}
```

## Edge (connection between nodes)
```json
{
  "id": "edge1",
  "fromNode": "node1", "fromSide": "right",
  "toNode": "node2",   "toSide": "left",
  "label": "leads to",
  "color": "2",
  "toEnd": "arrow"
}
```

`fromSide` / `toSide`: `"top"` `"right"` `"bottom"` `"left"`
`toEnd`: `"none"` `"arrow"`

## Colors

| Value | Color |
|-------|-------|
| `"1"` | Red |
| `"2"` | Orange |
| `"3"` | Yellow |
| `"4"` | Green |
| `"5"` | Cyan |
| `"6"` | Purple |
| Custom | `"#ff6b6b"` (hex) |

## Generate Canvas Programmatically

```python
import json

canvas = {
    "nodes": [
        {"id": "n1", "type": "text", "text": "Start", "x": 0, "y": 0, "width": 200, "height": 100},
        {"id": "n2", "type": "text", "text": "End",   "x": 300, "y": 0, "width": 200, "height": 100},
    ],
    "edges": [
        {"id": "e1", "fromNode": "n1", "fromSide": "right",
                     "toNode": "n2",   "toSide": "left", "toEnd": "arrow"}
    ]
}

with open("my-flow.canvas", "w") as f:
    json.dump(canvas, f, indent=2)
```

## Tips
- Canvas files live in your Obsidian vault alongside notes
- Use groups to visually cluster related nodes
- File nodes auto-update when the linked note changes
- Canvas is great for: architecture diagrams, sprint boards, mind maps, decision trees
