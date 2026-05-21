# Claude Code v2.1.141+ Features — Wired in This Repo

This config takes advantage of recent Claude Code features. Older versions
(<2.1.141) silently ignore unknown event names and missing fields, so this
file stays backward-compatible.

| Feature | Where wired | Why it matters |
|---------|-------------|----------------|
| `PreCompact` hook | `hooks/pre_compact.py` | Extracts TODO/PENDING from activeContext into goals.md BEFORE /clear loses them; progressive compression of activeContext.md |
| `PostCompact` hook | `hooks/post_compact.py` | Post-compaction state recovery |
| `WorktreeCreate/Remove` | `hooks/worktree_lifecycle.py` | Audit trail of every experiment worktree in `~/.claude/logs/worktrees.jsonl` |
| `worktree.baseRef: "head"` | `hooks/settings.json` | New worktrees branch from local HEAD (preserves unpushed commits) instead of `origin/<default>` (the v2.1.128+ default) |
| `effort.level` payload | `hooks/knowledge_librarian.py` | On `--effort low` skip knowledge injection; saves ~200 tokens per session |
| `claude agents --json` | external tooling | Use for status-line scripts / tmux integration |

## Pending — Not Yet Wired

| Feature | Why deferred |
|---------|--------------|
| Managed Agents `Outcomes` | Could replace `max_iterations=3` reviewer→builder loop with native grader. Requires full refactor of review-squad. |
| `PostToolUse updatedToolOutput` | No concrete point of application yet. |
| `mcp_tool` type in hooks | Needs concrete use case (e.g. `mcp__obsidian__write_note` from a hook). |

## Compatibility Matrix

| Claude Code version | Behaviour |
|---------------------|-----------|
| **v2.1.141+** | All features active |
| v2.1.128–v2.1.140 | `PreCompact`/`PostCompact`/`WorktreeCreate/Remove` hooks active. `worktree.baseRef` honoured (already exists). `effort.level` field absent → knowledge_librarian defaults to medium. |
| v2.1.100–v2.1.127 | `PreCompact` active. `worktree.baseRef` ignored. `WorktreeCreate/Remove` event unknown — silently skipped (resilience update). |
| < v2.1.100 | Unknown event names may break whole settings file. **Upgrade required.** |

**Source:** Claude Code changelog April–May 2026 (audited 2026-05-21).
