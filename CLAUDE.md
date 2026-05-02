<!-- gitnexus:start -->
# GitNexus — Code Intelligence *(optional MCP)*

> **GitNexus not installed?** Skip this section — use `Grep(pattern, path)` and `Read` instead.
> Install: `npm install -g gitnexus && npx gitnexus analyze` → restart Claude Code.

## Always Do *(if GitNexus available)*

- **MUST run impact analysis before editing any symbol:**
  `gitnexus_impact({target: "symbolName", direction: "upstream"})`
  *Fallback:* `Grep("function_name", "hooks/")` — find callers manually.
- **MUST run `gitnexus_detect_changes()` before committing.**
  *Fallback:* `git diff --stat HEAD`
- **MUST warn user** if impact returns HIGH or CRITICAL risk.

## Never Do

- NEVER edit a function without running `gitnexus_impact` first.
- NEVER ignore HIGH/CRITICAL risk warnings.
- NEVER rename with find-and-replace — use `gitnexus_rename` (graph-aware).
- NEVER commit without `gitnexus_detect_changes()`.

## Skills Reference

| Task | Skill file |
|------|-----------|
| Architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Debug / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools & schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |

> After `git commit`: run `npx gitnexus analyze` to refresh index (hook does this automatically).
<!-- gitnexus:end -->
