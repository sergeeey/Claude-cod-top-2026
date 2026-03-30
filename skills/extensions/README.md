# Extension Skills

These are **example** domain-specific skills demonstrating how to create skills for your own domain.

They are not part of the core framework — install only what you need, or use them as templates to build your own.

| Skill | Domain | Use as template for |
|-------|--------|---------------------|
| `project-audit` | Repository audit & due diligence | Any project evaluation (scientific, SaaS, open-source) |
| `security-audit` | Financial compliance | Any regulatory domain (healthcare, legal, etc.) |
| `archcode-genomics` | Genomics research | Any scientific simulation workflow |
| `geoscan` | Satellite remote sensing | Any geospatial / Earth observation pipeline |
| `notebooklm` | Google NotebookLM | Any browser-automated knowledge tool |
| `suno-music` | Music generation | Any creative AI prompt engineering |
| `python-geodata` | Geospatial Python | Any domain-specific Python patterns |

## Creating Your Own

See [Skills Guide](../../docs/skills-guide.md) for the full tutorial.

Quick template:
```
skills/extensions/your-skill/
  SKILL.md       # Frontmatter + instructions (loaded on trigger)
  plugin.json    # Metadata for skill-manager.sh
```
