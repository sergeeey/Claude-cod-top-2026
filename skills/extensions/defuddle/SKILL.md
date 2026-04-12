---
name: defuddle
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-04-12]
  Defuddle — web page extraction and clipping tool. Strips boilerplate,
  ads, navigation from HTML → clean Markdown for Obsidian/knowledge base.
  Triggers: defuddle, web clip, web clipping, extract article, clean html,
  article extraction, readability, import webpage, save article, clip page.
effort: minimal
tokens: ~200
---

# Defuddle — Web Article Extraction

## What It Is

Defuddle is a JavaScript library (also available as CLI) that extracts the **main content** from web pages — removes ads, navigation, sidebars, cookie banners — and returns clean Markdown. Used for web clipping into Obsidian.

## CLI Usage

```bash
# Install
npm install -g defuddle-cli

# Extract article from URL → stdout
defuddle https://example.com/article

# Save directly to Obsidian vault
defuddle https://example.com/article \
  --output ~/.obsidian-vault/clippings/article-title.md

# With metadata (title, author, date, url)
defuddle https://example.com/article --metadata

# Batch from file of URLs
cat urls.txt | xargs -I{} defuddle {} --output clippings/
```

## Output Format

```markdown
---
title: "Article Title"
author: "Author Name"
date: "2026-04-12"
url: "https://example.com/article"
tags: [clipping]
---

# Article Title

Cleaned body content here...
```

## Programmatic (Node.js)

```javascript
import { defuddle } from 'defuddle';

const html = await fetch('https://example.com/article').then(r => r.text());
const result = defuddle(document, html, {
  url: 'https://example.com/article',
  markdown: true,    // convert to markdown
  debug: false
});

console.log(result.title);    // article title
console.log(result.content);  // clean markdown
console.log(result.author);   // author if found
console.log(result.date);     // publication date
```

## Python Wrapper (via subprocess)

```python
import subprocess
import json

def clip_to_obsidian(url: str, vault_path: str) -> str:
    """Clip webpage to Obsidian vault using defuddle."""
    result = subprocess.run(
        ["defuddle", url, "--metadata", "--json"],
        capture_output=True, text=True, timeout=30
    )
    data = json.loads(result.stdout)
    title = data["title"].replace("/", "-")[:80]
    content = data["content"]
    
    out_path = f"{vault_path}/clippings/{title}.md"
    with open(out_path, "w") as f:
        f.write(content)
    return out_path
```

## Integration with populate_vault.py

```python
# Add to populate_vault.py sources:
def clip_reading_list(reading_list_path: str, wiki_dir: Path) -> int:
    """Clip all URLs from reading list → wiki entries."""
    urls = Path(reading_list_path).read_text().splitlines()
    count = 0
    for url in urls:
        try:
            result = subprocess.run(["defuddle", url], capture_output=True, text=True)
            if result.returncode == 0:
                # Save to raw/ for processing by session_save.py
                (Path.home() / ".claude/memory/raw" / f"clip-{count}.md").write_text(result.stdout)
                count += 1
        except Exception:
            pass
    return count
```

## vs Alternatives

| Tool | Best for |
|------|----------|
| **Defuddle** | Clean markdown, Obsidian integration |
| Readability.js | Browser extension context |
| Jina Reader | API-first, cloud |
| MarkDownload | Browser extension, manual |

## Tips
- Combine with Obsidian Local REST API to clip directly into vault
- Tag clippings with `#clipping #to-read` for easy filtering in Bases/Dataview
- defuddle handles paywalled content only if you're already authenticated
- Use `--simplify` flag for even cleaner output on complex pages
